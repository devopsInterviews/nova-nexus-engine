"""
Database clients package - Exports PostgreSQL and MSSQL clients

This __init__.py file is necessary to:
1. Make the databases/ folder a proper Python package
2. Enable imports from parent: `from .databases import PostgresClient, MSSQLClient`
3. Aggregate all database clients in one place for easy maintenance
4. Control exports via __all__ to keep the API clean
5. Allow the parent clients package to import from here

The structure enables these import patterns:
- From server.py: `from app.clients import PostgresClient, MSSQLClient`
- From clients.py: `from .clients.databases.postgres_client import PostgresClient`
- Direct: `from app.clients.databases import PostgresClient`

Without this file, Python wouldn't recognize databases/ as a package and
imports would fail.
"""

from .postgres_client import PostgresClient
from .mssql_client import MSSQLClient

__all__ = ['PostgresClient', 'MSSQLClient']