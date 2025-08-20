import os
import re
import json
import logging
import difflib

from dotenv import load_dotenv
from typing import List, Any

from ollama import AsyncClient, ChatResponse, Tool
from app.prompts import DEVOPS_SYSTEM_PROMPT

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Configuration
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434")
LLM_MODEL   = os.getenv("LLM_MODEL",   "llama3.2")

logger = logging.getLogger("uvicorn.error")

class LLMClient:
    """
    Async wrapper around Ollama's AsyncClient for chat + tool-calling.
    Uses dynamic MCP-discovered Tool objects.
    """

    def __init__(self, base_url: str = LLM_API_URL, model: str = LLM_MODEL):
        # Initialize AsyncClient pointing at remote Ollama server
        self.client = AsyncClient(host=base_url)
        self.model  = model
        logger.info("LLMClient initialized (model=%s @ %s)", model, base_url)

    async def query_llm(self, usr_prompt: str, sys_prompt: str = None) -> str:
        """
        Simple one-shot chat without tools. Returns generated text.
        """
        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": usr_prompt})

        resp: ChatResponse = await self.client.chat(
            model=self.model,
            messages=messages
        )
        return re.sub(r"<think>.*?</think>", "", resp.message.content, flags=re.DOTALL).strip()

    async def get_mcp_functions(self, session: Any) -> List[Tool]:
        """
        Retrieve MCP tools and convert to Ollama Tool objects.
        Wrap JSON-schema under a 'function' field as expected by the SDK.
        """
        result = await session.list_tools()
        tools: List[Tool] = []
        for t in result.tools:
            # Build the OpenAI-style function spec and wrap under 'function'
            func_spec = {
                "name":        t.name,
                "description": t.description,
                "parameters":  t.inputSchema,
            }
            tool_dict = {
                "type":     "function",
                "function": func_spec
            }
            tools.append(Tool.model_validate(tool_dict))
        logger.info("🔧 Retrieved %d Tool objects from MCP server", len(tools))
        return tools

    async def process_query(
        self,
        user_query: str,
        session: Any,
        system_prompt: str = DEVOPS_SYSTEM_PROMPT,
    ) -> str:
        """
        Loop: call chat() with dynamic tools until a final text answer.
        1) Dynamically fetch and validate tools
        2) Build conversation with generic system prompt
        3) Await response, execute any tool_calls, append results, repeat
        """
        logger.info("Starting to process a new query...\nQuery:\n\n %s", user_query)

        # 1) Fetch and validate Tool objects
        tools = await self.get_mcp_functions(session)
        tool_names: List[str] = [t.function.name for t in tools]
        logger.debug(tools)

        # 2) Prepare conversation
        generic = (
        "You have access to a dynamic set of tools provided by the MCP server via the `tools` parameter. "
        "Each tool has a name, description, and input schema. Use the precise names, do not make up functions that does not exist."
        "When the user’s request requires external data or actions, return a tool_calls entry. "
        "When invoking subsequent tools, you must use the output of previous function calls (role 'function') present in the conversation to populate argument values, rather than re-extracting or hallucinating them."
        )


        conversation = [
            {"role": "system", "content": generic + "\n" + system_prompt},
            {"role": "user",   "content": user_query},
        ]

        iteration = 0
        while True:
            iteration += 1
            logger.info("🔄 Iteration %d: sending conversation of %d messages to LLM", iteration, len(conversation))

            # 3) Call chat with dynamic Tool objects
            resp: ChatResponse = await self.client.chat(
                model=self.model,
                messages=conversation,
                #options={"temperature": 0.5},
                tools=tools
            )
            logger.debug(f"\n\n {resp} \n\n")
            msg = resp.message

            # 4) Handle tool_calls
            calls = msg.tool_calls or []
            if calls:
                for call in calls:
                    name = call.function.name
                    args = call.function.arguments
                    logger.info("🛠  Tool requested: %s with %s", name, args)

                    # Record the tool call
                    conversation.append({"role": "assistant", "tool_calls": [call]})

                    logger.debug("\n\nThe conversation was now added with the assistant role and the chosen tool to run:")
                    logger.debug(f"\n\n{conversation}")

                    name = self._closest_tool_name(name, tool_names)

                    # Invoke MCP tool and append result
                    tool_res = await session.call_tool(name, arguments=args)
                    text     = tool_res.content[0].text

                    logger.debug("\n\nThe mcp server ran the requested tool and returned:")
                    logger.debug(f"\n\n{text}")

                    logger.info("📥 Tool %s returned %d chars", name, len(text))
                    conversation.append({"role": "tool", "name": name, "content": text})

                    logger.debug("\n\nThe conversation was now added with the result of function")
                    logger.debug(f"\n\n{conversation}")

                # Continue loop after handling calls
                continue

            # 5) No tool calls → final answer
            final = re.sub(r"<think>.*?</think>", "", msg.content, flags=re.DOTALL).strip()
            logger.info("✅ Final response at iteration %d", iteration)
            logger.debug(f"The final llm response is:\n\n{final}")
            return final
        
        
    def _closest_tool_name(
        self,
        requested: str,
        valid_names: List[str],
        n: int = 1,
        cutoff: float = 0.6
    ) -> str:
        """
        This function inspects the desired tool name against the list of actually available
        tool names, and if it isn’t found exactly, uses fuzzy matching to pick the nearest
        valid tool before calling it. (In case the llm hallucinating)


        Args:
            requested:   The tool name the LLM tried to call.
            valid_names: List of actual tool names from MCP.
            n:           How many top matches to consider (default 1).
            cutoff:      Similarity threshold 0–1 (default 0.6).

        Returns:
            A name from `valid_names` (either exactly `requested` if it was valid,
            or the closest match). Raises KeyError if no match ≥ cutoff.
        """
        if requested in valid_names:
            return requested

        matches = difflib.get_close_matches(requested, valid_names, n=n, cutoff=cutoff)
        if matches:
            logger.warning("Remapped hallucinated tool '%s' → '%s'", requested, matches[0])
            return matches[0]

        raise KeyError(f"Tool '{requested}' not found in {valid_names}")


    async def close(self) -> None:
        """
        Clean up AsyncClient (close underlying connections).
        """
        await self.client.aclose()
        logger.info("🛑 LLMClient closed.")
