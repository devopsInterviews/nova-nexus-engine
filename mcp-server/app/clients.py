from typing import List, Dict, Any, Optional, Tuple, Set
import asyncpg
import asyncio
import logging
import re
try:
    import pytds
    import pytds.tds_base
except ImportError:
    pytds = None
from atlassian import Confluence

logger = logging.getLogger(__name__)


class ConfluenceClient:
    """
    Wraps basic operations for reading and updating Confluence pages.
    """

    # Matches @{anything with spaces or prefixes}
    MENTION_BRACED = re.compile(r'@\{([^}]+)\}')
    # Matches plain @username (start-of-line or whitespace before @, avoids emails)
    MENTION_PLAIN  = re.compile(r'(?<!\S)@([A-Za-z0-9._-]+)')

    def __init__(self, url: str, username: str, password: str, ssl_verify: bool = True):

        # Initialize the Confluence API client
        self.client = Confluence(
            url=url,
            username=username,
            password=password,
            verify_ssl=ssl_verify
        )
        logger.info("Username: " + username)
        logger.info("Password: " + password)
    async def get_page_id(self, space: str, title: str) -> str:
        """
        Return the numeric ID of a Confluence page given its space and title.
        """
        return self.client.get_page_id(space, title)

    async def get_page_content(self, page_id: str, expand: str = "body.storage,version") -> dict:
        """
        Fetch the content payload for a page, including its storage-format body and version.
        """
        return self.client.get_page_by_id(page_id, expand=expand)

    async def update_page(self,
                    page_id: str,
                    title: str,
                    new_body: str,
                    minor_edit: bool = True) -> dict:
        """
        Update an existing Confluence page’s body (storage format) and bump its version.

        :param page_id:    ID of the page to update
        :param title:      Title of the page (must match existing)
        :param new_body:   The HTML/storage-format content to write
        :param minor_edit: If True, flags this as a minor edit
        """
        # Retrieve current version
        page = await self.get_page_content(page_id, expand="version")
        current_version = page["version"]["number"]

        # Perform the update
        return self.client.update_page(
            page_id,
            title,
            new_body,
            parent_id=None,
            type="page",
            representation="storage",
            minor_edit=minor_edit,
            version_comment="Automated update via ConfluenceClient"
        )

    async def append_to_page(self, page_id: str, html_fragment: str) -> dict:
        """
        Append HTML storage-format content to the end of an existing page.
        """
        page = await self.get_page_content(page_id, expand="body.storage,version")
        current_body = page["body"]["storage"]["value"]
        new_body = current_body + html_fragment
        return self.update_page(
            page_id,
            page["title"],
            new_body
        )

    async def _get_userkey_dc(self, username: str) -> Optional[str]:
        """Resolve Confluence username -> userKey (DC REST via atlassian-python-api)."""
        try:
            logger.debug("DC resolve username -> userKey: %r", username)
            data = await asyncio.to_thread(self.client.get_user_details_by_username, username)
            if not isinstance(data, dict):
                logger.warning("get_user_details_by_username returned non-dict for %r: %r", username, type(data))
                return None
            userkey = data.get("userKey") or data.get("key")
            if userkey:
                logger.debug("Resolved %r to userKey=%r", username, userkey)
            else:
                logger.warning("No userKey found for username=%r; keys=%r", username, list(data.keys()))
            return userkey
        except Exception as e:
            logger.exception("Failed DC user lookup for username=%r: %s", username, e)
            return None

    def _build_user_mention_dc(self, userkey: str) -> str:
        """Return DC storage-format user mention macro."""
        return f'<ac:link><ri:user ri:userkey="{userkey}"/></ac:link>'

    async def _inject_mentions(self, text: str) -> Tuple[str, bool]:
        """
        Replace @{...} and plain @username with storage-format mentions.
        Returns (new_text, any_replaced)
        """
        if not text:
            return text, False

        replaced_any = False
        new_text = text

        # 1) Handle @{...}
        for m in list(self.MENTION_BRACED.finditer(new_text)):
            token = m.group(1).strip()
            logger.debug("Found braced mention token=%r", token)
            try:
                macro = None
                if token.startswith("userkey:"):
                    macro = self._build_user_mention_dc(token.split(":", 1)[1].strip())
                else:
                    # "username:<name>" or just a name -> resolve to userKey
                    if token.startswith("username:"):
                        username = token.split(":", 1)[1].strip()
                    else:
                        username = token
                    userkey = await self._get_userkey_dc(username)
                    if userkey:
                        macro = self._build_user_mention_dc(userkey)

                if macro:
                    new_text = new_text.replace(m.group(0), macro)
                    replaced_any = True
                    logger.debug("Braced mention resolved -> macro inserted")
                else:
                    logger.warning("Could not resolve braced token=%r; leaving as text", token)
            except Exception as e:
                logger.exception("Error resolving braced token=%r: %s", token, e)

        # 2) Handle plain @username
        for m in list(self.MENTION_PLAIN.finditer(new_text)):
            username = m.group(1)
            logger.debug("Found plain @username mention: %r", username)
            try:
                userkey = await self._get_userkey_dc(username)
                if not userkey:
                    logger.warning("Username %r not found; will rely on wiki conversion fallback", username)
                    continue
                macro = self._build_user_mention_dc(userkey)
                new_text = new_text.replace(m.group(0), macro)
                replaced_any = True
                logger.debug("Plain @%s resolved -> macro inserted", username)
            except Exception as e:
                logger.exception("Error resolving plain @%s: %s", username, e)

        logger.debug("mention injection: replaced_any=%s", replaced_any)
        return new_text, replaced_any

    async def _wiki_conversion_fallback_dc(self, text: str) -> Optional[str]:
        """
        If injection failed, try converting wiki mentions [~username] -> storage via Confluence converter.
        """
        try:
            def repl(m: re.Match) -> str:
                return f"[~{m.group(1)}]"
            wiki_candidate = self.MENTION_PLAIN.sub(repl, text)
            if wiki_candidate == text:
                return None
            logger.debug("Attempting wiki->storage conversion fallback")
            storage = await asyncio.to_thread(self.client.convert_wiki_to_storage, wiki_candidate)
            logger.debug("Wiki conversion produced %d chars", len(storage) if storage else -1)
            return storage
        except Exception as e:
            logger.exception("Wiki conversion fallback failed: %s", e)
            return None

    async def post_comment(self, page_id: str, comment: str) -> dict:
        """
        Add a comment. Supports @{...} and @username mentions (DC).
        """
        logger.debug("post_comment: start page_id=%s len(comment)=%d", page_id, len(comment))
        try:
            prepared, replaced_any = await self._inject_mentions(comment)

            if not replaced_any:
                # DC fallback: try wiki -> storage conversion for [~username]
                converted = await self._wiki_conversion_fallback_dc(comment)
                if converted:
                    prepared = converted
                    replaced_any = True
                    logger.debug("Using wiki->storage converted body")

            # Wrap in <p> if there's no block-level tag; DC renders comments more consistently
            if "<ac:" not in prepared and "<p>" not in prepared:
                prepared = f"<p>{prepared}</p>"

            logger.debug("post_comment: final length=%d, replaced_any=%s", len(prepared), replaced_any)
            return await asyncio.to_thread(self.client.add_comment, page_id, prepared)
        except Exception as e:
            logger.exception("post_comment: failed posting comment to page_id=%s: %s", page_id, e)
            raise


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
        logger.info("🔍 Listing all schemas in database")
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
        schemas = [r["schema_name"] for r in rows]
        logger.info("📋 Found %d schemas: %s", len(schemas), schemas)
        return schemas
    
    async def list_tables(self, schema: str = None) -> List[str]:
        """
        Return a list of all user-defined tables and views.
        
        If schema is provided, returns tables and views from that specific schema.
        If schema is None (default), returns tables and views from all schemas except system schemas.

        This queries the standard INFORMATION_SCHEMA.TABLES view, filtering on
        table_type IN ('BASE TABLE', 'VIEW') to include both tables and views.
        """
        assert self._pool is not None, "Connection pool is not initialized"
        
        if schema:
            logger.info("🔍 Listing tables and views from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Listing tables and views from ALL user schemas")
            
        async with self._pool.acquire() as conn:
            if schema:
                # Get tables and views from specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_name, table_type
                      FROM information_schema.tables
                     WHERE table_schema = $1
                       AND table_type IN ('BASE TABLE', 'VIEW')
                     ORDER BY table_type, table_name;
                    """,
                    schema
                )
                # Separate tables and views for logging
                base_tables = [r["table_name"] for r in rows if r["table_type"] == "BASE TABLE"]
                views = [r["table_name"] for r in rows if r["table_type"] == "VIEW"]
                tables = [r["table_name"] for r in rows]
                
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
                # Get tables and views from all user schemas (excluding system schemas)
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, table_type
                      FROM information_schema.tables
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                       AND table_type IN ('BASE TABLE', 'VIEW')
                     ORDER BY table_schema, table_type, table_name;
                    """
                )
                # Group by schema and type for logging
                schema_objects = {}
                for row in rows:
                    schema_name = row["table_schema"]
                    table_name = row["table_name"]
                    table_type = row["table_type"]
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
                
                tables = [r["table_name"] for r in rows]
                
        return tables

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
        
        if schema:
            logger.info("🔍 Listing keys from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Listing keys from ALL user schemas")
            
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
                     ORDER BY table_schema, table_name, ordinal_position;
                    """
                )
        
        result: Dict[str, List[str]] = {}
        schema_info: Dict[str, str] = {}  # Track which schema each table belongs to for logging
        schema_stats: Dict[str, int] = {}  # Track column count per schema
        
        for row in rows:
            table_schema = row["table_schema"]
            tbl = row["table_name"]
            col = row["column_name"]
            
            # Store schema info for logging
            if tbl not in schema_info:
                schema_info[tbl] = table_schema
                
            # Count columns per schema
            schema_stats[table_schema] = schema_stats.get(table_schema, 0) + 1
            
            # Use just table name (no schema prefix) as the key
            result.setdefault(tbl, []).append(col)
        
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
        Find the schema for a given table or view name.
        
        :param table: The table or view name to search for
        :returns: The schema name where the table/view exists, defaults to 'public' if not found
        """
        assert self._pool, "Postgres pool not initialized"
        logger.info("🔍 Looking up schema for table/view: '%s'", table)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT table_schema, table_type
                  FROM information_schema.tables
                 WHERE table_name = $1
                   AND table_schema NOT IN ('information_schema', 'pg_catalog')
                   AND table_schema NOT LIKE 'pg_temp_%'
                   AND table_schema NOT LIKE 'pg_toast_temp_%'
                   AND table_type IN ('BASE TABLE', 'VIEW')
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
            table_type = rows[0]["table_type"]
            type_icon = "📊" if table_type == "BASE TABLE" else "👁️"
            
            if len(rows) > 1:
                all_schemas_types = [(r["table_schema"], r["table_type"]) for r in rows]
                logger.warning("⚠️  Object '%s' found in multiple schemas: %s - using '%s' (%s, public preferred)", 
                             table, all_schemas_types, schema, table_type.lower())
            else:
                logger.info("✅ Found %s '%s' (%s) in schema '%s'", table_type.lower(), table, type_icon, schema)
            return schema
        else:
            logger.warning("❌ Table/view '%s' not found in any schema, defaulting to 'public'", table)
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
        logger.info("🔍 Getting %d sample values from column '%s' in table/view '%s.%s'", 
                   limit, column, schema, table)
        
        async with self._pool.acquire() as conn:
            # Use schema-qualified table name and parameter binding for safety
            sql = f"SELECT DISTINCT {column} FROM {schema}.{table} LIMIT $1"
            logger.debug("📝 Executing query: %s", sql)
            records = await conn.fetch(sql, limit)
        
        values = [r[column] for r in records]
        logger.info("✅ Retrieved %d distinct values from '%s.%s.%s'", 
                   len(values), schema, table, column)
        return values

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
        assert self._pool is not None, "Connection pool is not initialized"
        
        if schema:
            logger.info("🔍 Getting column metadata from specific schema: '%s'", schema)
        else:
            logger.info("🔍 Getting column metadata from ALL user schemas")
            
        async with self._pool.acquire() as conn:
            if schema:
                # Get column metadata from specific schema
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name, data_type, 
                           is_nullable, column_default, character_maximum_length,
                           ordinal_position
                      FROM information_schema.columns
                     WHERE table_schema = $1
                     ORDER BY table_name, ordinal_position;
                    """,
                    schema
                )
            else:
                # Get column metadata from all user schemas
                rows = await conn.fetch(
                    """
                    SELECT table_schema, table_name, column_name, data_type,
                           is_nullable, column_default, character_maximum_length,
                           ordinal_position
                      FROM information_schema.columns
                     WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
                       AND table_schema NOT LIKE 'pg_temp_%'
                       AND table_schema NOT LIKE 'pg_toast_temp_%'
                     ORDER BY table_schema, table_name, ordinal_position;
                    """
                )
        
        result: Dict[str, Dict[str, Any]] = {}
        schema_stats: Dict[str, int] = {}  # Track column count per schema
        
        for row in rows:
            table_schema = row["table_schema"]
            table_name = row["table_name"]
            column_name = row["column_name"]
            
            # Create fully qualified column key
            full_key = f"{table_schema}.{table_name}.{column_name}"
            
            # Store comprehensive metadata
            result[full_key] = {
                "table_name": table_name,
                "column_name": column_name,
                "data_type": row["data_type"],
                "table_schema": table_schema,
                "is_nullable": row["is_nullable"],
                "column_default": row["column_default"],
                "character_maximum_length": row["character_maximum_length"]
            }
            
            # Count columns per schema for logging
            schema_stats[table_schema] = schema_stats.get(table_schema, 0) + 1
        
        total_columns = len(result)
        logger.info("📊 Retrieved metadata for %d columns across %d schemas:", 
                   total_columns, len(schema_stats))
        
        for schema_name, column_count in schema_stats.items():
            logger.info("  📂 Schema '%s': %d columns with metadata", schema_name, column_count)
        
        logger.info("✅ Column metadata collection complete")
        return result

class MSSQLClient:
    """
    Async client for Microsoft SQL Server, with dynamic connection parameters
    and methods to list databases, tables, columns, and execute arbitrary queries.
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
        self._conn = await asyncio.to_thread(pytds.connect, **self._conn_args)

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

    async def list_tables(self) -> List[str]:
        """
        Return a list of all user tables in the current database’s dbo schema
        using INFORMATION_SCHEMA.TABLES.
        """
        assert self._conn, "Connection not initialized"

        def _sync_list_tables():
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT TABLE_NAME
                  FROM INFORMATION_SCHEMA.TABLES
                 WHERE TABLE_TYPE = 'BASE TABLE'
                   AND TABLE_SCHEMA = 'dbo';
                """
            )
            rows = cur.fetchall()
            cur.close()
            return [r[0] for r in rows]

        return await asyncio.to_thread(_sync_list_tables)

    async def list_keys(self) -> Dict[str, List[str]]:
        """
        Return a mapping of each table to its list of column names
        by querying INFORMATION_SCHEMA.COLUMNS.
        """
        assert self._conn, "Connection not initialized"

        def _sync_list_keys():
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME
                  FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA = 'dbo'
                 ORDER BY TABLE_NAME, ORDINAL_POSITION;
                """
            )
            result: Dict[str, List[str]] = {}
            for table, column in cur.fetchall():
                result.setdefault(table, []).append(column)
            cur.close()
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
        """
        assert self._conn, "Connection not initialized"
        def _sync():
            cur = self._conn.cursor()
            # First, try DISTINCT TOP
            distinct_sql = f"SELECT DISTINCT TOP {limit} [{column}] FROM [{table}]"
            try:
                logger.debug("Executing DISTINCT query: %s", distinct_sql)
                cur.execute(distinct_sql)
                rows = cur.fetchall()
                return [row[0] for row in rows]

            except pytds.tds_base.OperationalError as e:
                msg = str(e)
                logger.warning(
                    "DISTINCT failed on %s.%s: %s. Falling back to plain TOP or CAST",
                    table, column, msg
                )
                # Fallback: plain TOP N
                try:
                    plain_sql = f"SELECT TOP {limit} [{column}] FROM [{table}]"
                    logger.debug("Executing fallback SQL: %s", plain_sql)
                    cur.execute(plain_sql)
                    rows = cur.fetchall()
                    return [row[0] for row in rows]
                except pytds.tds_base.OperationalError:
                    # Last resort: cast XML to NVARCHAR(MAX)
                    cast_sql = (
                        f"SELECT TOP {limit} "
                        f"CAST([{column}] AS NVARCHAR(MAX)) "
                        f"FROM [{table}]"
                    )
                    logger.debug("Executing CAST fallback SQL: %s", cast_sql)
                    cur.execute(cast_sql)
                    rows = cur.fetchall()
                    return [row[0] for row in rows]
            finally:
                cur.close()

        # Run the blocking DB work in a thread so the event loop stays responsive
        return await asyncio.to_thread(_sync)

    async def get_column_metadata(self, schema: str = None) -> Dict[str, Dict[str, Any]]:
        """Get MSSQL column metadata - not implemented."""
        raise NotImplementedError("MSSQL client not implemented yet")