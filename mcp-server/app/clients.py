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
    
    async def list_tables(self) -> List[str]:
        """
        Return a list of all user-defined tables in the connected database's public schema.

        This queries the standard INFORMATION_SCHEMA.TABLES view, filtering on
        table_schema = 'public' to exclude system catalogs and internal schemas.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT table_name
                  FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_type = 'BASE TABLE';
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

