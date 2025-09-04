import asyncpg
import logging
from typing import List, Dict, Any, Optional

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
        Return a list of all schemas in the connected database.
        Excludes system schemas like information_schema and pg_* schemas.
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
        Return a list of all user-defined tables in the connected database.
        
        Args:
            schema: If specified, only return tables from this schema.
                   If None, return tables from all non-system schemas.

        This queries the standard INFORMATION_SCHEMA.TABLES view.
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
                return [r["table_name"] for r in rows]
            else:
                # Get tables from all non-system schemas - return simple table names
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT table_name
                      FROM information_schema.tables
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                       AND table_type = 'BASE TABLE'
                     ORDER BY table_name;
                    """
                )
                return [r["table_name"] for r in rows]

    async def list_tables_with_schema(self, schema: str = None) -> List[str]:
        """
        Return a list of all user-defined tables with their schema prefix.
        
        Args:
            schema: If specified, only return tables from this schema.
                   If None, return tables from all non-system schemas.

        Returns table names in format "schema.table_name"
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # Get tables from specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name
                      FROM information_schema.tables
                     WHERE table_schema = $1
                       AND table_type = 'BASE TABLE'
                     ORDER BY table_name;
                    """,
                    schema
                )
            else:
                # Get tables from all non-system schemas
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name
                      FROM information_schema.tables
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                       AND table_type = 'BASE TABLE'
                     ORDER BY table_schema, table_name;
                    """
                )
        return [f"{r['table_schema']}.{r['table_name']}" for r in rows]

    async def list_keys(self, schema: str = None) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names
        in table.column format.

        Args:
            schema: If specified, only return keys for tables in this schema.
                   If None, return keys for tables in all non-system schemas.

        :returns: Dict where each key is a table name and the value is 
                  a list of "table.column" formatted strings.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # fetch table + column combos for specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema = $1
                     ORDER BY table_name, ordinal_position;
                    """,
                    schema
                )
            else:
                # fetch table + column combos for all non-system schemas
                rows = await conn.fetch(
                    """
                    SELECT table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                     ORDER BY table_name, ordinal_position;
                    """
                )
            
            # Group by table and format as table.column
            result: Dict[str, List[str]] = {}
            for row in rows:
                table_name = row["table_name"]
                column_name = row["column_name"]
                table_column = f"{table_name}.{column_name}"
                result.setdefault(table_name, []).append(table_column)
            
            return result

    async def list_keys_display_format(self, schema: str = None) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names
        formatted for UI display (clean table.column format).

        Args:
            schema: If specified, only return keys for tables in this schema.
                   If None, return keys for tables in all non-system schemas.
                   
        Returns clean table names as keys (without schema prefix) for UI display.

        :returns: Dict where each key is a clean table name and 
                  the value is the ordered list of that table's column names.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # fetch table + column combos for specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema = $1
                     ORDER BY table_name, ordinal_position;
                    """,
                    schema
                )
                # Use just table name as key when querying specific schema
                result: Dict[str, List[str]] = {}
                for row in rows:
                    tbl = row["table_name"]
                    col = row["column_name"]
                    result.setdefault(tbl, []).append(col)
            else:
                # fetch table + column combos for all non-system schemas
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                     ORDER BY table_schema, table_name, ordinal_position;
                    """
                )
                # Use clean table_name as key, merge columns from different schemas
                result: Dict[str, List[str]] = {}
                for row in rows:
                    tbl_key = row["table_name"]  # Clean table name without schema
                    col = row["column_name"]
                    if tbl_key not in result:
                        result[tbl_key] = []
                    if col not in result[tbl_key]:  # Avoid duplicates if same column exists in multiple schemas
                        result[tbl_key].append(col)
        
        return result

    async def list_keys_with_schema_info(self, schema: str = None) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names,
        with schema information preserved for backend operations.

        Args:
            schema: If specified, only return keys for tables in this schema.
                   If None, return keys for tables in all non-system schemas.
                   
        Returns schema.table names as keys (with schema prefix) for backend operations.
        This method is used internally where schema information is needed.

        :returns: Dict where each key is schema.table_name and 
                  the value is the ordered list of that table's column names.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            if schema:
                # fetch table + column combos for specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema = $1
                     ORDER BY table_name, ordinal_position;
                    """,
                    schema
                )
                # Use just table name as key when querying specific schema
                result: Dict[str, List[str]] = {}
                for row in rows:
                    tbl = row["table_name"]
                    col = row["column_name"]
                    result.setdefault(tbl, []).append(col)
            else:
                # fetch table + column combos for all non-system schemas
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name
                      FROM information_schema.columns
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                     ORDER BY table_schema, table_name, ordinal_position;
                    """
                )
                # Use schema.table_name as key for backend operations
                result: Dict[str, List[str]] = {}
                for row in rows:
                    tbl_key = f"{row['table_schema']}.{row['table_name']}"
                    col = row["column_name"]
                    result.setdefault(tbl_key, []).append(col)
        
        return result

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Run the given SQL statement and return rows as a list of dicts.
        """
        assert self._pool, "Pool not initialized"
        async with self._pool.acquire() as conn:
            records = await conn.fetch(sql)
        return [dict(r) for r in records]

    async def get_column_values(
        self,
        table: str,
        column: str,
        limit: int
    ) -> list:
        """
        Return up to `limit` distinct values for `column` in `table`.
        """
        assert self._pool, "Postgres pool not initialized"
        async with self._pool.acquire() as conn:
            # Use parameter binding for safety
            sql = f"SELECT DISTINCT {column} FROM {table} LIMIT $1"
            records = await conn.fetch(sql, limit)
        # Extract the single column from each record
        return [r[column] for r in records]
