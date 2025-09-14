from typing import List, Dict, Any, Optional
import asyncio
import logging

try:
    import pytds
    import pytds.tds_base
except ImportError:
    pytds = None

logger = logging.getLogger(__name__)


class MSSQLClient:
    """
    Async client for Microsoft SQL Server, with dynamic connection parameters
    and methods to list databases, schemas, tables, columns, and execute arbitrary queries.
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str = "master"
    ):
        """
        :param host:      SQL Server hostname or IP.
        :param port:      SQL Server port (default: 1433).
        :param user:      Username for authentication.
        :param password:  Password for authentication.
        :param database:  Initial database to connect to (default: 'master').
        """
        self._conn_args = {
            "server": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password
        }
        self._conn: Optional[Any] = None

    async def init(self) -> None:
        """
        Initialize the connection to SQL Server.

        This uses pytds.connect() synchronously under the hood,
        offloading to a worker thread so the event loop remains responsive.
        """
        if pytds is None:
            raise ImportError("pytds library is required for MSSQL client. Install with: pip install python-tds")
        self._conn = await asyncio.to_thread(pytds.connect, **self._conn_args)
        logger.info("MSSQL connection established successfully")

    async def close(self) -> None:
        """
        Close the SQL Server connection.

        The synchronous .close() call is wrapped in to_thread() to prevent blocking.
        """
        if self._conn:
            await asyncio.to_thread(self._conn.close)

    async def list_databases(self) -> List[str]:
        """
        Return a list of all user databases on the server,
        excluding system DBs (database_id > 4).
        """
        assert self._conn, "Connection not initialized"

        def _sync_list_dbs():
            cur = self._conn.cursor()
            cur.execute(
                "SELECT name "
                "FROM sys.databases "
                "WHERE database_id > 4;"
            )
            rows = cur.fetchall()
            cur.close()
            return [r[0] for r in rows]

        return await asyncio.to_thread(_sync_list_dbs)

    async def list_schemas(self) -> List[str]:
        """
        Return a list of all user-defined schemas in the connected database.
        
        This queries sys.schemas, excluding system schemas.
        """
        assert self._conn, "Connection not initialized"
        logger.info("🔍 Listing all schemas in database")

        def _sync_list_schemas():
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT name
                  FROM sys.schemas
                 WHERE schema_id BETWEEN 5 AND 16383
                   AND name NOT IN ('guest', 'sys', 'INFORMATION_SCHEMA')
                 ORDER BY name;
                """
            )
            rows = cur.fetchall()
            cur.close()
            return [r[0] for r in rows]

        schemas = await asyncio.to_thread(_sync_list_schemas)
        logger.info("📋 Found %d schemas: %s", len(schemas), schemas)
        return schemas

    async def list_tables(self, schema: str = None) -> List[str]:
        """
        Return a list of all user tables and views.

        If schema is provided, returns tables and views from that specific schema.
        If schema is None (default), returns tables and views from all user schemas.

        This queries INFORMATION_SCHEMA.TABLES, filtering on 
        table_type IN ('BASE TABLE', 'VIEW') to include both tables and views.
        """
        assert self._conn, "Connection not initialized"
        
        if schema:
            logger.info("🔍 Listing tables and views from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Listing tables and views from ALL user schemas")

        def _sync_list_tables():
            cur = self._conn.cursor()
            if schema:
                # Get tables and views from specific schema
                cur.execute(
                    """
                    SELECT TABLE_NAME, TABLE_TYPE
                      FROM INFORMATION_SCHEMA.TABLES
                     WHERE TABLE_SCHEMA = ?
                       AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                     ORDER BY TABLE_TYPE, TABLE_NAME;
                    """,
                    schema
                )
                rows = cur.fetchall()
                
                # Separate tables and views for logging
                base_tables = [r[0] for r in rows if r[1] == "BASE TABLE"]
                views = [r[0] for r in rows if r[1] == "VIEW"]
                tables = [r[0] for r in rows]
                
                logger.info("📋 Found %d objects in schema '%s': %d base tables, %d views", 
                           len(tables), schema, len(base_tables), len(views))
                if base_tables:
                    logger.info("  📊 Base tables: %s", base_tables[:10] if len(base_tables) > 10 else base_tables)
                    if len(base_tables) > 10:
                        logger.info("    ... and %d more base tables", len(base_tables) - 10)
                if views:
                    logger.info("  👁️  Views: %s", views[:10] if len(views) > 10 else views)
                    if len(views) > 10:
                        logger.info("    ... and %d more views", len(views) - 10)
            else:
                # Get tables and views from all user schemas
                cur.execute(
                    """
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                      FROM INFORMATION_SCHEMA.TABLES
                     WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'sys')
                       AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                     ORDER BY TABLE_SCHEMA, TABLE_TYPE, TABLE_NAME;
                    """
                )
                rows = cur.fetchall()
                
                # Group by schema and type for logging
                schema_objects = {}
                for row in rows:
                    schema_name = row[0]
                    table_name = row[1]
                    table_type = row[2]
                    if schema_name not in schema_objects:
                        schema_objects[schema_name] = {"BASE TABLE": [], "VIEW": []}
                    schema_objects[schema_name][table_type].append(table_name)
                
                # Log schema breakdown with table types
                total_objects = len(rows)
                total_tables = sum(len(objects["BASE TABLE"]) for objects in schema_objects.values())
                total_views = sum(len(objects["VIEW"]) for objects in schema_objects.values())
                
                logger.info("📊 Found %d total objects across %d schemas: %d base tables, %d views", 
                           total_objects, len(schema_objects), total_tables, total_views)
                
                for schema_name, objects in schema_objects.items():
                    base_tables = objects["BASE TABLE"]
                    views = objects["VIEW"]
                    total_schema_objects = len(base_tables) + len(views)
                    
                    logger.info("  📂 Schema '%s': %d objects (%d tables, %d views)", 
                              schema_name, total_schema_objects, len(base_tables), len(views))
                    
                    if base_tables:
                        logger.info("    📊 Tables: %s", 
                                  ', '.join(base_tables[:3]) + ('...' if len(base_tables) > 3 else ''))
                    if views:
                        logger.info("    👁️  Views: %s", 
                                  ', '.join(views[:3]) + ('...' if len(views) > 3 else ''))
                
                tables = [r[1] for r in rows]
            
            cur.close()
            return tables

        return await asyncio.to_thread(_sync_list_tables)

    async def list_keys(self, schema: str = None) -> Dict[str, List[str]]:
        """
        Return a mapping of each table name to its list of column names
        by querying INFORMATION_SCHEMA.COLUMNS.

        If schema is provided, returns keys from tables in that specific schema.
        If schema is None (default), returns keys from tables in all user schemas.

        :param schema: Optional schema name to filter by. If None, includes all user schemas.
        :returns: Dict where each key is a table name and the value is the
                  ordered list of that table's column names.
        """
        assert self._conn, "Connection not initialized"
        
        if schema:
            logger.info("🔍 Listing keys from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Listing keys from ALL user schemas")

        def _sync_list_keys():
            cur = self._conn.cursor()
            if schema:
                # fetch table + column combos from specific schema
                cur.execute(
                    """
                    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
                      FROM INFORMATION_SCHEMA.COLUMNS
                     WHERE TABLE_SCHEMA = ?
                     ORDER BY TABLE_NAME, ORDINAL_POSITION;
                    """,
                    schema
                )
            else:
                # fetch table + column combos from all user schemas
                cur.execute(
                    """
                    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
                      FROM INFORMATION_SCHEMA.COLUMNS
                     WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'sys')
                     ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
                    """
                )
            
            result: Dict[str, List[str]] = {}
            schema_info: Dict[str, str] = {}  # Track which schema each table belongs to for logging
            schema_stats: Dict[str, int] = {}  # Track column count per schema
            
            for table_schema, table_name, column_name in cur.fetchall():
                # Store schema info for logging
                if table_name not in schema_info:
                    schema_info[table_name] = table_schema
                    
                # Count columns per schema
                schema_stats[table_schema] = schema_stats.get(table_schema, 0) + 1
                
                # Use just table name (no schema prefix) as the key
                result.setdefault(table_name, []).append(column_name)
            
            cur.close()
            
            # Log comprehensive schema information
            total_columns = sum(len(cols) for cols in result.values())
            logger.info("📊 Found %d columns across %d tables in %d schemas:", 
                       total_columns, len(result), len(schema_stats))
            
            for schema_name, column_count in schema_stats.items():
                schema_tables = [table for table, table_schema in schema_info.items() if table_schema == schema_name]
                logger.info("  📂 Schema '%s': %d tables, %d columns (%s)", 
                           schema_name, len(schema_tables), column_count,
                           ', '.join(schema_tables[:3]) + ('...' if len(schema_tables) > 3 else ''))
            
            # Log potential table name conflicts across schemas
            table_schemas = {}
            for table, table_schema in schema_info.items():
                if table not in table_schemas:
                    table_schemas[table] = []
                table_schemas[table].append(table_schema)
            
            conflicts = {table: schemas for table, schemas in table_schemas.items() if len(schemas) > 1}
            if conflicts:
                logger.warning("⚠️  Found %d table names that exist in multiple schemas:", len(conflicts))
                for table, schemas in conflicts.items():
                    logger.warning("  🔄 Table '%s' exists in schemas: %s", table, ', '.join(schemas))
            else:
                logger.info("✅ No table name conflicts between schemas")
            
            return result

        return await asyncio.to_thread(_sync_list_keys)

    async def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Run an arbitrary SQL statement and return rows as list of dicts.
        """
        assert self._conn, "Connection not initialized"

        def _sync_execute():
            cur = self._conn.cursor()
            cur.execute(sql)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            cur.close()
            return [dict(zip(cols, row)) for row in rows]

        return await asyncio.to_thread(_sync_execute)

    async def get_table_schema(self, table: str) -> str:
        """
        Find the schema for a given table or view name.
        
        :param table: The table or view name to search for
        :returns: The schema name where the table/view exists, defaults to 'dbo' if not found
        """
        assert self._conn, "MSSQL connection not initialized"
        logger.info("🔍 Looking up schema for table/view: '%s'", table)

        def _sync_get_schema():
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT TABLE_SCHEMA, TABLE_TYPE
                  FROM INFORMATION_SCHEMA.TABLES
                 WHERE TABLE_NAME = ?
                   AND TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'sys')
                   AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
                 ORDER BY 
                   CASE TABLE_SCHEMA 
                     WHEN 'dbo' THEN 1 
                     ELSE 2 
                   END;
                """,
                table
            )
            rows = cur.fetchall()
            cur.close()
            return rows

        rows = await asyncio.to_thread(_sync_get_schema)
        
        if rows:
            schema = rows[0][0]
            table_type = rows[0][1]
            type_icon = "📊" if table_type == "BASE TABLE" else "👁️"
            
            if len(rows) > 1:
                all_schemas_types = [(r[0], r[1]) for r in rows]
                logger.warning("⚠️  Object '%s' found in multiple schemas: %s - using '%s' (%s, dbo preferred)", 
                             table, all_schemas_types, schema, table_type.lower())
            else:
                logger.info("✅ Found %s '%s' (%s) in schema '%s'", table_type.lower(), table, type_icon, schema)
            return schema
        else:
            logger.warning("❌ Table/view '%s' not found in any schema, defaulting to 'dbo'", table)
            return 'dbo'

    async def get_column_values(
        self,
        table: str,
        column: str,
        limit: int
    ) -> List[Any]:
        """
        Return up to `limit` distinct values for `column` in `table`.
        For XML-typed columns (which can't be DISTINCT-ed), falls back
        to a plain TOP query or casts the column to NVARCHAR(MAX).
        Automatically finds the correct schema for the table.
        """
        assert self._conn, "Connection not initialized"
        
        # Find the correct schema for this table
        schema = await self.get_table_schema(table)
        logger.info("🔍 Getting %d sample values from column '%s' in table/view '%s.%s'", 
                   limit, column, schema, table)

        def _sync():
            cur = self._conn.cursor()
            # First, try DISTINCT TOP
            distinct_sql = f"SELECT DISTINCT TOP {limit} [{column}] FROM [{schema}].[{table}]"
            try:
                logger.debug("Executing DISTINCT query: %s", distinct_sql)
                cur.execute(distinct_sql)
                rows = cur.fetchall()
                values = [row[0] for row in rows]
                logger.info("✅ Retrieved %d distinct values from '%s.%s.%s'", 
                           len(values), schema, table, column)
                return values

            except pytds.tds_base.OperationalError as e:
                msg = str(e)
                logger.warning(
                    "DISTINCT failed on %s.%s: %s. Falling back to plain TOP or CAST",
                    table, column, msg
                )
                # Fallback: plain TOP N
                try:
                    plain_sql = f"SELECT TOP {limit} [{column}] FROM [{schema}].[{table}]"
                    logger.debug("Executing fallback SQL: %s", plain_sql)
                    cur.execute(plain_sql)
                    rows = cur.fetchall()
                    values = [row[0] for row in rows]
                    logger.info("✅ Retrieved %d values (non-distinct) from '%s.%s.%s'", 
                               len(values), schema, table, column)
                    return values
                except pytds.tds_base.OperationalError:
                    # Last resort: cast XML to NVARCHAR(MAX)
                    cast_sql = (
                        f"SELECT TOP {limit} "
                        f"CAST([{column}] AS NVARCHAR(MAX)) "
                        f"FROM [{schema}].[{table}]"
                    )
                    logger.debug("Executing CAST fallback SQL: %s", cast_sql)
                    cur.execute(cast_sql)
                    rows = cur.fetchall()
                    values = [row[0] for row in rows]
                    logger.info("✅ Retrieved %d casted values from '%s.%s.%s'", 
                               len(values), schema, table, column)
                    return values
            finally:
                cur.close()

        # Run the blocking DB work in a thread so the event loop stays responsive
        return await asyncio.to_thread(_sync)

    async def get_column_metadata(self, schema: str = None) -> Dict[str, Dict[str, Any]]:
        """
        Return detailed metadata for all columns including data types and schema information.
        
        If schema is provided, returns metadata from that specific schema.
        If schema is None (default), returns metadata from all user schemas.
        
        :param schema: Optional schema name to filter by. If None, includes all user schemas.
        :returns: Dict where each key is "schema.table.column" and value contains metadata:
                 {
                     "table_name": str,
                     "column_name": str, 
                     "data_type": str,
                     "table_schema": str,
                     "is_nullable": str,
                     "column_default": str or None,
                     "character_maximum_length": int or None
                 }
        """
        assert self._conn, "Connection not initialized"
        
        if schema:
            logger.info("🔍 Getting column metadata from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Getting column metadata from ALL user schemas")

        def _sync_get_metadata():
            cur = self._conn.cursor()
            if schema:
                # Get column metadata from specific schema
                cur.execute(
                    """
                    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, 
                           IS_NULLABLE, COLUMN_DEFAULT, CHARACTER_MAXIMUM_LENGTH,
                           ORDINAL_POSITION
                      FROM INFORMATION_SCHEMA.COLUMNS
                     WHERE TABLE_SCHEMA = ?
                     ORDER BY TABLE_NAME, ORDINAL_POSITION;
                    """,
                    schema
                )
            else:
                # Get column metadata from all user schemas
                cur.execute(
                    """
                    SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE,
                           IS_NULLABLE, COLUMN_DEFAULT, CHARACTER_MAXIMUM_LENGTH,
                           ORDINAL_POSITION
                      FROM INFORMATION_SCHEMA.COLUMNS
                     WHERE TABLE_SCHEMA NOT IN ('INFORMATION_SCHEMA', 'sys')
                     ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION;
                    """
                )
            
            result: Dict[str, Dict[str, Any]] = {}
            schema_stats: Dict[str, int] = {}  # Track column count per schema
            
            for row in cur.fetchall():
                table_schema = row[0]
                table_name = row[1]
                column_name = row[2]
                
                # Create fully qualified column key
                full_key = f"{table_schema}.{table_name}.{column_name}"
                
                # Store comprehensive metadata
                result[full_key] = {
                    "table_name": table_name,
                    "column_name": column_name,
                    "data_type": row[3],
                    "table_schema": table_schema,
                    "is_nullable": row[4],
                    "column_default": row[5],
                    "character_maximum_length": row[6]
                }
                
                # Count columns per schema for logging
                schema_stats[table_schema] = schema_stats.get(table_schema, 0) + 1
            
            cur.close()
            return result, schema_stats

        result, schema_stats = await asyncio.to_thread(_sync_get_metadata)
        
        total_columns = len(result)
        logger.info("📊 Retrieved metadata for %d columns across %d schemas:", 
                   total_columns, len(schema_stats))
        
        for schema_name, column_count in schema_stats.items():
            logger.info("  📂 Schema '%s': %d columns with metadata", schema_name, column_count)
        
        logger.info("✅ Column metadata collection complete")
        return result