from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.adk.models.lite_llm import LiteLlm 
from google.adk.agents import Agent

from oidcAuth import get_headers
from appConfig import AppConfig, config

class BitbucketAgentFactory:
    """Responsible for building and configuring the Bitbucket Agent."""

    SYSTEM_INSTRUCTION = (
        "You are an autonomous agent with deep expertise in Bitbucket and source control workflows.\n"
        "Your goal is to fully understand and resolve any Bitbucket-related request you are given.\n"
        "Always use your available tools to investigate, gather the necessary information, and deliver "
        "a complete and accurate answer.\n"
        "Think step by step — break complex requests into smaller actions and work through them "
        "methodically before presenting your final response.\n"
        "If a request is beyond what you can do with your available tools, say so clearly."
    )

    AGENT_DESCRIPTION = (
        "An autonomous Bitbucket AI assistant with broad knowledge of source control, repositories, "
        "and development workflows. Use this agent to investigate, analyse, and resolve any request "
        "related to the internal Bitbucket server or the projects and code hosted on it."
    )

    @classmethod
    def create_agent(cls, config: AppConfig) -> Agent:
        """Assembles the toolset, model, and agent."""
        
        bitbucket_toolset = McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=config.MCP_URL),
            header_provider=get_headers,
        )

        custom_model = LiteLlm(
            model=config.LITELLM_MODEL, 
            api_base=config.LITELLM_URL,
            api_key=config.LITELLM_API_KEY,
        )

        return Agent(
            name="Bitbucket_Agent",
            model=custom_model,
            description=cls.AGENT_DESCRIPTION,
            instruction=cls.SYSTEM_INSTRUCTION,
            tools=[bitbucket_toolset],
        )
    
AGENT_NAME = "Bitbucket_Agent"
AGENT_DESCRIPTION = BitbucketAgentFactory.AGENT_DESCRIPTION
agent = BitbucketAgentFactory.create_agent(config)
