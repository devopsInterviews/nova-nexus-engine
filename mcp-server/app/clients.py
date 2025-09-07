from typing import List, Dict, Any, Optional
import asyncpg
import logging

logger = logging.getLogger(__name__)


class PostgresClient:
    """
    Async client for PostgreSQL, with dynamic connection parameters
    and a method to list all non-template databases.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str = "postgres",
        min_size: int = 1,
        max_size: int = 10
    ):
        """
        :param host:      PostgreSQL server hostname or IP
        :param port:      PostgreSQL server port (e.g., 5432)
        :param user:      Username for authentication
        :param password:  Password for authentication
        :param database:  Initial database to connect to (default: 'postgres')
        :param min_size:  Minimum connections in the pool
        :param max_size:  Maximum connections in the pool
        """
        self._dsn = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        """
        Initialize the asyncpg connection pool.
        """
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size
        )
        logger.info("Postgres pool created successfuly")

    async def close(self) -> None:
        """
        Close the connection pool and release all connections.
        """
        if self._pool:
            await self._pool.close()

    async def list_databases(self) -> List[str]:
        """
        Return a list of all non-template database names on the server.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT datname "
                "FROM pg_database "
                "WHERE datistemplate = false;"
            )
        # Extract 'datname' field from each Record
        return [r["datname"] for r in rows]
    
    async def list_schemas(self) -> List[str]:
        """
        Return a list of all user-defined schemas in the connected database.
        
        This queries the standard INFORMATION_SCHEMA.SCHEMATA view, excluding
        system schemas like information_schema and pg_* schemas.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT schema_name
                  FROM information_schema.schemata
                 WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                   AND schema_name NOT LIKE 'pg_temp_%'
                   AND schema_name NOT LIKE 'pg_toast_temp_%'
                 ORDER BY schema_name;
                """
            )
        return [r["schema_name"] for r in rows]
    
    async def list_tables(self, schema: str = None) -> List[str]:
        """
        Return a list of all user-defined tables.
        
        If schema is provided, returns tables from that specific schema.
        If schema is None (default), returns tables from all schemas except system schemas.

        This queries the standard INFORMATION_SCHEMA.TABLES view, filtering on
        table_type = 'BASE TABLE' to exclude views and system tables.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # Get tables from specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema = $1
                       AND table_type = 'BASE TABLE'
                     ORDER BY table_name;
                    """,
                    schema
                )
            else:
                # Get tables from all user schemas (excluding system schemas)
                rows = await conn.fetch(
                    """
                    SELECT table_name
                      FROM information_schema.tables
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                       AND table_type = 'BASE TABLE'
                     ORDER BY table_name;
                    """
                )
        return [r["table_name"] for r in rows]

    async def list_keys(self) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names
        (i.e. “keys”) in the connected database’s public schema.

        Queries information_schema.columns for all columns in schema 'public',
        then groups them by table_name.

        :returns: Dict where each key is a table name and the value is the
                  ordered list of that table’s column names.
        :raises: AssertionError if the pool isn’t initialized, or asyncpg errors
                 for connection/query issues.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            # fetch table + column combos
            rows = await conn.fetch(
                """
                SELECT table_name, column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                 ORDER BY table_name, ordinal_position;
                """
            )
        result: Dict[str, List[str]] = {}
        for row in rows:
            tbl = row["table_name"]
            col = row["column_name"]
            result.setdefault(tbl, []).append(col)
        return result

    async def list_keys(self, schema: str = None) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names
        (i.e. "keys") in the connected database.

        If schema is provided, returns keys from tables in that specific schema.
        If schema is None (default), returns keys from tables in all schemas except system schemas.

        Queries information_schema.columns for all columns, then groups them by table_name.
        Note: The table names in the result will NOT include schema prefixes, but schema
        information will be logged for debugging purposes.

        :param schema: Optional schema name to filter by. If None, includes all user schemas.
        :returns: Dict where each key is a table name and the value is the
                  ordered list of that table's column names.
        :raises: AssertionError if the pool isn't initialized, or asyncpg errors
                 for connection/query issues.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # fetch table + column combos from specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema = $1
                     ORDER BY table_name, ordinal_position;
                    """,
                    schema
                )
            else:
                # fetch table + column combos from all user schemas
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                     ORDER BY table_name, ordinal_position;
                    """
                )
        
        result: Dict[str, List[str]] = {}
        schema_info: Dict[str, str] = {}  # Track which schema each table belongs to for logging
        
        for row in rows:
            table_schema = row["table_schema"]
            tbl = row["table_name"]
            col = row["column_name"]
            
            # Store schema info for logging
            if tbl not in schema_info:
                schema_info[tbl] = table_schema
            
            # Use just table name (no schema prefix) as the key
            result.setdefault(tbl, []).append(col)
        
        # Log schema information for debugging
        if schema_info:
            logger.debug("Table schema mapping: %s", schema_info)
        
        return result

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Run the given SQL statement and return rows as a list of dicts.
        """
        assert self._pool, "Pool not initialized"
        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql)
        return [dict(r) for r in records]

    async def get_table_schema(self, table: str) -> str:
        """
        Find the schema for a given table name.
        
        :param table: The table name to search for
        :returns: The schema name where the table exists, defaults to 'public' if not found
        """
        assert self._pool, "Postgres pool not initialized"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT table_schema
                  FROM information_schema.tables
                 WHERE table_name = $1
                   AND table_schema NOT IN ('information_schema', 'pg_catalog')
                   AND table_schema NOT LIKE 'pg_temp_%'
                   AND table_schema NOT LIKE 'pg_toast_temp_%'
                 ORDER BY 
                   CASE table_schema 
                     WHEN 'public' THEN 1 
                     ELSE 2 
                   END;
                """,
                table
            )
        if rows:
            schema = rows[0]["table_schema"]
            logger.debug("Found table '%s' in schema '%s'", table, schema)
            return schema
        else:
            logger.warning("Table '%s' not found, defaulting to 'public' schema", table)
            return 'public'

    async def get_column_values(
        self,
        table: str,
        column: str,
        limit: int
    ) -> list:
        """
        Return up to `limit` distinct values for `column` in `table`.
        Automatically finds the correct schema for the table.
        """
        assert self._pool, "Postgres pool not initialized"
        
        # Find the correct schema for this table
        schema = await self.get_table_schema(table)
        
        async with self._pool.acquire() as conn:
            # Use schema-qualified table name and parameter binding for safety
            sql = f"SELECT DISTINCT {column} FROM {schema}.{table} LIMIT $1"
            records = await conn.fetch(sql, limit)
        # Extract the single column from each record
        return [r[column] for r in records]


class MSSQLClient:
    """
    Placeholder MSSQL client. 
    
    This is a stub implementation to support the existing server.py structure
    that expects both PostgreSQL and MSSQL clients. The actual MSSQL implementation
    would need to be added here with proper SQL Server connection handling.
    """
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str = "master"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        
    async def init(self) -> None:
        """Initialize MSSQL connection - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def close(self) -> None:
        """Close MSSQL connection - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def list_databases(self) -> List[str]:
        """List MSSQL databases - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def list_schemas(self) -> List[str]:
        """List MSSQL schemas - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def list_tables(self, schema: str = None) -> List[str]:
        """List MSSQL tables - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def list_keys(self, schema: str = None) -> Dict[str, List[str]]:
        """List MSSQL table keys - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute MSSQL query - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")
        
    async def get_column_values(self, table: str, column: str, limit: int) -> list:
        """Get MSSQL column values - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")

