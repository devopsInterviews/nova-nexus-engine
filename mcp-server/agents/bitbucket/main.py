import uuid
import asyncio
import uvicorn
from starlette.responses import JSONResponse
from fastmcp import FastMCP, Context
from fastmcp.server.dependencies import get_access_token
from google.adk.runners import Runner
from google.adk.agents.run_config import RunConfig
from google.adk.sessions import InMemorySessionService
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.genai import types

from oidcAuth import create_oidc_proxy
from agentFactory import agent, AGENT_NAME, AGENT_DESCRIPTION
from appConfig import config
from usageTracker import AgentUsageTrackingMiddleware


session_service = InMemorySessionService()

# ── A2A ──
a2a_app = to_a2a(agent=agent, host=config.BASE_URL, port=config.A2A_EXTERNAL_PORT, protocol=config.PROTOCOL)

# ── MCP (OAuth-protected) ──
mcp = FastMCP(AGENT_NAME, auth=create_oidc_proxy(config.base_url_with_port))

@mcp.tool()
async def run_agent(task: str, ctx: Context) -> str:
    """
    Invoke the autonomous Bitbucket AI agent to investigate and resolve Bitbucket-related requests.

    Use this tool whenever a task involves the internal Bitbucket server or anything hosted on it.
    Describe what you need in natural language and the agent will figure out the steps required,
    use its available tools to gather the necessary information, and return a complete answer.
    """
    token_obj = get_access_token()
    raw_token = getattr(token_obj, "token", None) if token_obj else None
    access_token = f"Bearer {raw_token}" if raw_token else None

    run_config = RunConfig(
        custom_metadata={
            "a2a_metadata": {
                "headers": {
                    "Authorization": access_token,
                }
            }
        }
    ) if access_token else RunConfig()

    current_session_id = str(uuid.uuid4())
    runner = Runner(
        agent=agent,
        app_name=AGENT_NAME,
        session_service=session_service,
    )
    await session_service.create_session(
        app_name=AGENT_NAME,
        user_id="mcp_client",
        session_id=current_session_id,
    )

    content = types.Content(role="user", parts=[types.Part(text=task)])
    events = runner.run_async(
        user_id="mcp_client",
        session_id=current_session_id,
        new_message=content,
        run_config=run_config,
    )

    final_response = "Agent did not return a response."
    async for event in events:
        if event.is_final_response():
            final_response = event.content.parts[0].text
    return final_response


run_agent.description = AGENT_DESCRIPTION


# ── Health checks on both apps ──
@mcp.custom_route("/health", methods=["GET"])
async def mcp_health(request):
    return JSONResponse({"status": "healthy", "protocol": "mcp"})

mcp_app = mcp.http_app()

if config.PORTAL_BASE_URL and config.AGENT_MARKETPLACE_NAME:
    _portal_ping_url = f"{config.PORTAL_BASE_URL.rstrip('/')}/api/marketplace/ping"
    mcp_app = AgentUsageTrackingMiddleware(
        mcp_app,
        portal_ping_url=_portal_ping_url,
        entity_name=config.AGENT_MARKETPLACE_NAME,
        ssl_verify=config.PORTAL_SSL_VERIFY,
    )
else:
    import logging as _logging
    _logging.getLogger(__name__).info(
        "Agent usage tracking disabled "
        "(set PORTAL_BASE_URL and AGENT_MARKETPLACE_NAME to enable)"
    )


@a2a_app.route("/health")
async def a2a_health(request):
    return JSONResponse({"status": "healthy", "protocol": "a2a"})


# ── Run both on separate ports ──
async def main():
    a2a_server = uvicorn.Server(
        uvicorn.Config(a2a_app, host=config.HOST, port=config.A2A_INTERNAL_PORT)
    )
    mcp_server = uvicorn.Server(
        uvicorn.Config(mcp_app, host=config.HOST, port=config.MCP_INTERNAL_PORT)
    )
    await asyncio.gather(a2a_server.serve(), mcp_server.serve())


if __name__ == "__main__":
    asyncio.run(main())
