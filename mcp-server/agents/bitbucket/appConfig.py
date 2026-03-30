import os


class AppConfig:
    """Holds configuration and environment variables."""
    HOST = os.getenv("HOST", "0.0.0.0")
    A2A_INTERNAL_PORT = int(os.getenv("A2A_INTERNAL_PORT", 8081))
    A2A_EXTERNAL_PORT = int(os.getenv("A2A_EXTERNAL_PORT", 443))
    MCP_INTERNAL_PORT = int(os.getenv("MCP_INTERNAL_PORT", 8080))
    MCP_EXTERNAL_PORT = int(os.getenv("MCP_EXTERNAL_PORT", 443))
    LITELLM_URL = os.getenv("LITELLM_URL", "")
    LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
    LITELLM_MODEL = os.getenv("LITELLM_MODEL", "hosted_vllm/gpt-oss")
    MCP_URL = os.getenv("MCP_URL")
    BASE_URL = os.getenv("BASE_URL", "127.0.0.1")
    PROTOCOL = os.getenv("PROTOCOL", "https")

    # ── Usage tracking (optional) ──────────────────────────────────────────────
    PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "")
    AGENT_MARKETPLACE_NAME = os.getenv("AGENT_MARKETPLACE_NAME", "")
    PORTAL_SSL_VERIFY = os.getenv("PORTAL_SSL_VERIFY", "true").strip().lower() in {
        "true", "1", "yes", "y", "on",
    }

    @property
    def base_url_with_port(self):
        default_ports = {"https": 443, "http": 80}
        if self.MCP_EXTERNAL_PORT == default_ports.get(self.PROTOCOL):
            return f"{self.PROTOCOL}://{self.BASE_URL}"
        return f"{self.PROTOCOL}://{self.BASE_URL}:{self.MCP_EXTERNAL_PORT}"

config = AppConfig()
