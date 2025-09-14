"""
Clients package - Main entry point for all client classes

This __init__.py file is necessary to:
1. Enable clean imports in server.py: `from app.clients import PostgresClient, MSSQLClient`
2. Maintain proper Python package structure for the clients module
3. Control what gets exported from the package via __all__
4. Allow both package-style and direct imports to work:
   - Package style: `from app.clients import PostgresClient`
   - Direct style: `from app.clients.databases.postgres_client import PostgresClient`

Without this file, the package-style imports would fail and server.py would need
to use longer, more verbose import statements.
"""

from .databases import PostgresClient, MSSQLClient

__all__ = ['PostgresClient', 'MSSQLClient']