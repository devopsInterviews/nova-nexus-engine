from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field

import logging
import logging.config

class Settings(BaseSettings):
    """Holds configuration and environment variables."""
    mcp_server_host:          str        = Field(..., validation_alias="MCP_SERVER_HOST")
    mcp_server_port:          int        = Field(..., validation_alias="MCP_SERVER_PORT")
    log_level:                str        = Field("INFO", validation_alias="LOG_LEVEL")
    bitbucket_base_url:       str        = Field(..., validation_alias="BITBUCKET_BASE_URL")
    bitbucket_ssl_verify:     str        = Field(..., validation_alias="BITBUCKET_SSL_VERIFY")

    # ── AI Portal usage tracking (optional) ──────────────────────────────────
    # Set both variables to enable per-tool call reporting to the marketplace.
    #
    # PORTAL_BASE_URL              — base URL of the AI Portal
    #                                e.g. https://portal.company.internal
    # MCP_SERVER_MARKETPLACE_NAME  — exact name of this MCP server as
    #                                registered in the marketplace DB
    # PORTAL_SSL_VERIFY            — set to "false" to skip TLS verification
    #                                when calling the portal (default: true)
    portal_base_url:              Optional[str] = Field(None, validation_alias="PORTAL_BASE_URL")
    mcp_server_marketplace_name:  Optional[str] = Field(None, validation_alias="MCP_SERVER_MARKETPLACE_NAME")
    portal_ssl_verify:            str           = Field("true", validation_alias="PORTAL_SSL_VERIFY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": settings.log_level
        }
    },
    "root": {
        "handlers": ["console"],
        "level": settings.log_level
    }
}

def configure_logging():
    """Initialize logging configuration at startup."""
    logging.config.dictConfig(LOGGING_CONFIG)
