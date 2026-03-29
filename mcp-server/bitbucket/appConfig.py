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
