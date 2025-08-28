"""
Utility functions for MCP session management and status checking.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_mcp_session_status() -> Dict[str, Any]:
    """
    Get the current MCP session status.
    
    Returns:
        Dict containing status information:
        - is_connected: bool
        - url: str
        - session_info: dict (if available)
    """
    try:
        from app.client import _mcp_session
        
        if _mcp_session is None:
            return {
                'is_connected': False,
                'url': 'Not Connected',
                'session_info': None
            }
        
        # Check if session has required attributes/methods
        session_url = getattr(_mcp_session, '_url', None)
        if session_url is None:
            # Try to get URL from transport or other sources
            try:
                from app.client import MCP_SERVER_URL
                session_url = MCP_SERVER_URL
            except:
                session_url = 'localhost'
        
        return {
            'is_connected': True,
            'url': str(session_url),
            'session_info': {
                'type': type(_mcp_session).__name__,
                'initialized': hasattr(_mcp_session, 'initialize')
            }
        }
        
    except ImportError:
        logger.warning("Could not import MCP session")
        return {
            'is_connected': False,
            'url': 'Import Error',
            'session_info': None
        }
    except Exception as e:
        logger.error(f"Error checking MCP session status: {e}")
        return {
            'is_connected': False,
            'url': f'Error: {str(e)}',
            'session_info': None
        }


def is_mcp_connected() -> bool:
    """
    Simple check if MCP is connected.
    
    Returns:
        bool: True if MCP session is active, False otherwise
    """
    status = get_mcp_session_status()
    return status['is_connected']


def get_mcp_url() -> str:
    """
    Get the MCP server URL.
    
    Returns:
        str: The MCP server URL or error message
    """
    status = get_mcp_session_status()
    return status['url']
