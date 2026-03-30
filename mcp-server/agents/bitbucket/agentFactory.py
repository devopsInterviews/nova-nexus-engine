from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
from google.adk.models.lite_llm import LiteLlm 
from google.adk.agents import Agent

from oidcAuth import get_headers
from appConfig import AppConfig, config

class BitbucketAgentFactory:
    """Responsible for building and configuring the Bitbucket Agent."""
    
    SYSTEM_INSTRUCTION = (
        "You are an autonomous agent that is capable of solving all matter of bitbucket requests.\n"
        "When tasked with a request about bitbucket, use your available tools in order to solve it,\n"
        "if you dont have the right tool for the task, return that you are not capable of it."
    )
    
    AGENT_DESCRIPTION = (
        "A bitbucket AI assistant, ready to help and solve bitbucket related issues. use this agent "
        "in order to gather data about the internal bitbucket, about repos, files inside those repos "
        "and everything that could be related to the upstream server of bitbucket."
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
