import json
import logging
import re
import asyncio
from typing import List, Dict, Any, Set, Tuple
from bs4 import BeautifulSoup

# Import client classes (these should be available from the app directory)
from app.clients import PostgresClient, MSSQLClient
from app import confluence, llm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import MCP framework (this should be available in the environment)
# Note: The actual import will depend on your MCP setup
# This is a placeholder that represents the MCP framework
import mcp

@mcp.tool()
async def get_confluence_page_content(space: str, title: str) -> str:
    """
    Fetches the HTML storage-format body of a Confluence page.

    Args:
      space (str): The Confluence space key (e.g. "PROJ").
      title (str): The title of the page to fetch.

    Returns:
      str: The storage-format HTML content of the page body.
    """

    # Resolve the page ID
    page_id = await confluence.get_page_id(space, title)
    # Fetch full page content (including storage body)
    page = await confluence.get_page_content(page_id, expand="body.storage")
    # Return the raw HTML/storage value
    return page["body"]["storage"]["value"]

@mcp.tool()
async def append_to_confluence_page(space: str, title: str, html_fragment: str) -> str:
    """
    Appends an HTML fragment to the end of an existing Confluence page.

    Args:
      space (str): The Confluence space key.
      title (str): The title of the page to update.
      html_fragment (str): A snippet of HTML (storage format) to append.

    Returns:
      str: Confirmation message including the page ID.
    """
    # Resolve the page ID
    page_id = await confluence.get_page_id(space, title)
    # Append the fragment and update the page
    await confluence.append_to_page(page_id, html_fragment)
    logger.info(f"Appended content to Confluence page '{title}' (ID: {page_id})")

@mcp.tool()
async def update_confluence_table(
    space: str,
    title: str,
    data: list[dict]
) -> dict:
    """
    Replace the contents of the first <table class="relative-table"> in a Confluence page
    with new rows generated from a list of column metadata.

    Args:
        space (str):    Confluence space key (e.g., "PROJ").
        title (str):    Title of the Confluence page to update.
        data (list[dict]):
            A list of dictionaries, each with keys:
                "column" (str):     Column identifier (e.g., "shops.id").
                "description" (str): Text description of the column.
                "type" (str):       Data type of the column (e.g., "integer", "varchar").
                "schema" (str):     Schema name where the table/view resides.
                "owner" (str):      Owner information (optional, defaults to empty).

    Returns:
        dict: The full response from Confluence API's update_page call, containing
              updated page metadata and version information.

    Raises:
        ValueError: If the target table (<table class="relative-table">) is not found on the page.
        Exception: Propagates any errors from the Confluence API client.

    Example:
        >>> new_rows = [
        ...     {
        ...         "column": "shops.id", 
        ...         "description": "Unique shop ID",
        ...         "type": "integer",
        ...         "schema": "public",
        ...         "owner": ""
        ...     }
        ... ]
        >>> updated = await update_confluence_table("MALL", "Shop Catalog", new_rows)
        >>> print(updated["version"]["number"])
    """
    logger.info("🔍 Updating Confluence table in %s/%s with %d rows", space, title, len(data))
    
    # 1) Fetch existing page content in storage format (HTML)
    page_id = await confluence.get_page_id(space, title)
    page = await confluence.get_page_content(page_id, expand="body.storage,version")
    html = page["body"]["storage"]["value"]

    # 2) Parse with BeautifulSoup and locate or create the target table
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="relative-table")
    
    if not table:
        logger.info("📋 No existing table found, creating new table structure")
        # Create new table if none exists
        table = soup.new_tag("table", **{"class": "relative-table"})
        tbody = soup.new_tag("tbody")
        
        # Create header row
        header_row = soup.new_tag("tr")
        headers = ["Name", "Description", "Type", "Schema", "Owner"]
        for header_text in headers:
            th = soup.new_tag("th")
            th.string = header_text
            header_row.append(th)
        tbody.append(header_row)
        
        table.append(tbody)
        
        # Add table to the end of the page content
        if soup.body:
            soup.body.append(table)
        else:
            soup.append(table)
        
        logger.info("✅ Created new table with 5-column structure")
    else:
        logger.info("📋 Found existing table, updating structure if needed")
        # Check if table has the right number of columns in header
        header_row = table.find("tr")
        if header_row:
            headers = header_row.find_all(["th", "td"])
            if len(headers) < 5:
                logger.info("🔄 Updating table header to 5-column structure")
                # Clear existing headers and rebuild
                header_row.clear()
                header_texts = ["Name", "Description", "Type", "Schema", "Owner"]
                for header_text in header_texts:
                    th = soup.new_tag("th")
                    th.string = header_text
                    header_row.append(th)

    # 2a) Remove all old rows except the header
    rows = table.find_all("tr")
    for old_row in rows[1:]:
        old_row.extract()

    # 2b) Append new rows from 'data'
    for entry in data:
        col_val = entry.get("column", "")
        desc_val = entry.get("description", "")
        type_val = entry.get("type", "")
        schema_val = entry.get("schema", "")
        owner_val = entry.get("owner", "")
        
        new_tr = soup.new_tag("tr")
        
        # Create all 5 columns
        td_col = soup.new_tag("td"); td_col.string = col_val
        td_desc = soup.new_tag("td"); td_desc.string = desc_val
        td_type = soup.new_tag("td"); td_type.string = type_val
        td_schema = soup.new_tag("td"); td_schema.string = schema_val
        td_owner = soup.new_tag("td"); td_owner.string = owner_val
        
        new_tr.extend([td_col, td_desc, td_type, td_schema, td_owner])
        table.tbody.append(new_tr)

    # 2c) Serialize modified HTML back to a string
    updated_html = str(soup)
    logger.debug("Updated HTML length: %d characters", len(updated_html))

    # 3) Push update via Confluence API (auto-bumps version)
    updated = await confluence.update_page(
        page_id,
        title,
        updated_html,
        minor_edit=True
    )
    
    logger.info("✅ Successfully updated Confluence table with %d rows", len(data))
    return updated

@mcp.tool()
async def sync_confluence_table_delta(
    space: str,
    title: str,
    data: list[dict]
) -> dict:
    """
    Read the existing <table class="relative-table"> from a Confluence page,
    compute which entries in `data` are not already present (by column key),
    append only those delta rows to the table, and push the update.

    Args:
        space (str):    Confluence space key (e.g., "PROJ").
        title (str):    Title of the Confluence page to update.
        data (list[dict]):
            List of dicts with keys "column", "description", "type", "schema", "owner".

    Returns:
        dict: Full Confluence API response for the update_page call, or
              an empty dict if no delta rows to append.

    Raises:
        ValueError: If the target table (<table class="relative-table">) is not found.
        Exception: Propagates errors from the Confluence client.
    """
    logger.info("🔍 sync_confluence_table_delta called for %s/%s", space, title)
    logger.info("📊 Received %d data entries to process", len(data))
    
    # Log the structure of received data for debugging
    if data:
        logger.info("📋 Sample data entry: %s", data[0])
        logger.info("📋 Data entry keys: %s", list(data[0].keys()) if data else "No data")
    else:
        logger.warning("⚠️  No data provided to sync_confluence_table_delta - will create empty table if none exists")
    
    logger.info("🔍 Syncing Confluence table delta in %s/%s with %d potential rows", 
               space, title, len(data))
    
    # 1) Fetch current page HTML and version
    page_id = await confluence.get_page_id(space, title)
    page = await confluence.get_page_content(page_id, expand="body.storage,version")
    html = page["body"]["storage"]["value"]

    # 2) Parse HTML and extract existing keys or create table if needed
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="relative-table")
    
    if not table:
        logger.info("📋 No existing table found, creating new table structure")
        # Create new table if none exists
        table = soup.new_tag("table", **{"class": "relative-table"})
        tbody = soup.new_tag("tbody")
        
        # Create header row with 5 columns
        header_row = soup.new_tag("tr")
        headers = ["Name", "Description", "Type", "Schema", "Owner"]
        for header_text in headers:
            th = soup.new_tag("th")
            th.string = header_text
            header_row.append(th)
        tbody.append(header_row)
        
        table.append(tbody)
        
        # Add table to the end of the page content
        if soup.body:
            soup.body.append(table)
        else:
            soup.append(table)
        
        existing = set()  # No existing keys since table was just created
        logger.info("✅ Created new table with 5-column structure")
        
        # If no data provided, just create the table and return
        if not data:
            updated_html = str(soup)
            updated = await confluence.update_page(
                page_id,
                title,
                updated_html,
                minor_edit=True
            )
            logger.info("✅ Created empty table structure on Confluence page")
            return {"delta": [], "updated": updated, "message": "Created empty table structure"}
    else:
        # Extract existing keys from first <td> in each <tr> (skip header)
        existing = set()
        rows = table.find_all('tr')
        
        # Check and update header if needed
        if rows:
            header_row = rows[0]
            headers = header_row.find_all(["th", "td"])
            if len(headers) < 5:
                logger.info("🔄 Updating table header to 5-column structure")
                header_row.clear()
                header_texts = ["Name", "Description", "Type", "Schema", "Owner"]
                for header_text in header_texts:
                    th = soup.new_tag("th")
                    th.string = header_text
                    header_row.append(th)
        
        # Extract existing keys from data rows
        for tr in rows[1:]:
            td = tr.find('td')
            if td and td.text:
                existing.add(td.text.strip())

    # Handle case where no data provided but table exists
    if not data:
        logger.info("✅ No data to sync, but table structure is confirmed to exist")
        return {"delta": [], "updated": None, "message": "No data to sync"}

    logger.debug("📋 Existing keys in table: %s", existing)
    logger.debug("📋 Incoming data columns: %s", [item.get("column", "<missing>") for item in data])

    # 3) Determine delta rows
    delta = [entry for entry in data if entry.get("column", "") not in existing]
    
    logger.info("📊 Delta analysis: %d existing keys, %d incoming items, %d delta rows", 
               len(existing), len(data), len(delta))
    
    if not delta:
        logger.info("✅ No delta rows to add - table is up to date")
        if not existing and data:
            logger.warning("⚠️  Strange: no existing keys but incoming data didn't create delta. Data format issue?")
            logger.debug("🔍 First data item structure: %s", data[0] if data else "None")
        return {"delta": [], "updated": None, "message": "No new columns to sync"}
    
    logger.info("📊 Found %d delta rows to add", len(delta))
    logger.debug("📋 Delta columns: %s", [item.get("column", "<missing>") for item in delta])

    # 4) Append delta rows to the table in the soup
    for entry in delta:
        col_val = entry.get("column", "")
        desc_val = entry.get("description", "")
        type_val = entry.get("type", "")
        schema_val = entry.get("schema", "")
        owner_val = entry.get("owner", "")
        
        new_tr = soup.new_tag("tr")
        
        # Create all 5 columns
        td_col = soup.new_tag("td"); td_col.string = col_val
        td_desc = soup.new_tag("td"); td_desc.string = desc_val
        td_type = soup.new_tag("td"); td_type.string = type_val
        td_schema = soup.new_tag("td"); td_schema.string = schema_val
        td_owner = soup.new_tag("td"); td_owner.string = owner_val
        
        new_tr.extend([td_col, td_desc, td_type, td_schema, td_owner])
        table.tbody.append(new_tr)

    updated_html = str(soup)

    # 5) Push update via Confluence API (auto-version)
    updated = await confluence.update_page(
        page_id,
        title,
        updated_html,
        minor_edit=True
    )

    logger.info("✅ Successfully synced %d delta rows to Confluence table", len(delta))
    return {
        "delta":   delta,   # list of {column,description,type,schema,owner}
        "updated": updated  # full API response
    }

@mcp.tool()
async def get_confluence_page_id(
    space: str,
    title: str
) -> str:
    """
    Retrieve the numeric ID of a Confluence page by space and title.
    """
    logger.debug("get_confluence_page_id called with space=%s, title=%s", space, title)
    page_id = await asyncio.to_thread(
        confluence.get_page_id,
        space,
        title
    )
    logger.debug("get_confluence_page_id result: page_id=%s", page_id)
    return page_id

@mcp.tool()
async def post_confluence_comment(
    space: str,
    title: str,
    comment: str
) -> Dict[str, Any]:
    """
    Add a comment to a Confluence page by ID.
    Returns the Confluence API response.
    """
    page_id = await confluence.get_page_id(space=space,title=title)
    logger.debug("post_confluence_comment called with page_id=%s, comment=%s", page_id, comment)
    resp = await confluence.post_comment(page_id,comment)
    logger.debug("post_confluence_comment result: %s", resp)
    return resp

@mcp.tool()
async def collect_db_confluence_key_descriptions(
    space: str,
    title: str,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> Dict[str, str]:
    """
    Return a mapping of keys that exist BOTH in Confluence and in the DB schema,
    with their descriptions taken from Confluence.
    """
    # --- helpers for safe logging ---
    def _mask_secret(s: str, show: int = 2) -> str:
        if s is None:
            return "None"
        s = str(s)
        return (s[:show] + "..." + s[-show:]) if len(s) > (show * 2) else "***"

    def _sample_dict(d: Dict[str, str], n: int = 15) -> Dict[str, str]:
        keys = list(d.keys())[:n]
        return {k: d[k] for k in keys}

    def _sample_schema(schema: Dict[str, List[str]], n_tables: int = 10, n_cols: int = 10) -> Dict[str, List[str]]:
        out = {}
        for i, (tbl, cols) in enumerate(schema.items()):
            if i >= n_tables:
                break
            out[tbl] = cols[:n_cols]
        return out

    try:
        logger.info(
            "collect_db_confluence_key_descriptions: start space=%r title=%r host=%s port=%s db=%s user=%s",
            space, title, host, port, database, user
        )

        # --- 1) Confluence: read storage HTML and pull key->desc from the table ---
        logger.debug("Confluence: resolving page_id for space=%r title=%r …", space, title)
        page_id = await confluence.get_page_id(space, title)
        logger.info("Confluence: got page_id=%s", page_id)

        logger.debug("Confluence: fetching page content expand='body.storage,version' …")
        page = await confluence.get_page_content(page_id, expand="body.storage,version")
        html = page["body"]["storage"]["value"]
        logger.debug("Confluence: storage HTML length=%d chars", len(html))

        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="relative-table")
        if not table:
            logger.error("Confluence: <table class='relative-table'> not found on page=%r space=%r", title, space)
            raise ValueError(f"relative-table not found on page '{title}' in space '{space}'")

        rows = table.find_all("tr")
        logger.debug("Confluence: found %d <tr> rows in relative-table", len(rows))

        conf_map: Dict[str, str] = {}
        for tr in rows[1:]:  # skip header
            tds = tr.find_all("td")
            if not tds:
                continue
            key = tds[0].get_text(" ", strip=True) if len(tds) >= 1 else ""
            desc = tds[1].get_text(" ", strip=True) if len(tds) >= 2 else ""
            if key:
                conf_map[key] = desc

        logger.info("Confluence: parsed %d key(s) from table", len(conf_map))
        logger.debug("Confluence: sample key→desc: %s", _sample_dict(conf_map))

        # --- 2) DB schema: build canonical key set and helpers ---
        logger.info("DB: connecting to %s:%s db=%s user=%s", host, port, database, user)
        pg = PostgresClient(host=host, port=port, user=user, password=password, database=database)
        await pg.init()
        try:
            logger.debug("DB: calling list_keys() …")
            schema: Dict[str, List[str]] = await pg.list_keys()  # {table: [col,...]}
        finally:
            logger.debug("DB: closing connection pool …")
            await pg.close()

        total_tables = len(schema or {})
        total_cols = sum(len(v) for v in (schema or {}).values())
        logger.info("DB: schema loaded tables=%d total_columns=%d", total_tables, total_cols)
        logger.debug("DB: sample schema: %s", _sample_schema(schema or {}))

        db_full_keys: Set[str] = set()
        lower_to_canonical: Dict[str, str] = {}
        col_to_tables: Dict[str, Set[str]] = {}

        for tbl, cols in (schema or {}).items():
            for col in cols:
                full = f"{tbl}.{col}"
                db_full_keys.add(full)
                lower_to_canonical[full.lower()] = full
                col_to_tables.setdefault(col, set()).add(tbl)
                col_to_tables.setdefault(col.lower(), set()).add(tbl)

        logger.debug(
            "DB: canonical keys built count=%d unique_columns=%d",
            len(db_full_keys), len({c for c in col_to_tables.keys() if isinstance(c, str) and c.islower()})
        )

        # --- 3) Intersect: keep keys that exist in both sources, prefer canonical table.col ---
        result: Dict[str, str] = {}
        matched_exact = 0
        matched_by_unique_column = 0
        skipped_ambiguous = 0

        for raw_key, desc in conf_map.items():
            k = (raw_key or "").strip()
            if not k:
                continue

            # a) Exact table.column form (case-insensitive)
            if "." in k:
                canon = lower_to_canonical.get(k.lower())
                if canon:
                    result[canon] = desc
                    matched_exact += 1
                continue

            # b) Column-only form: include only if column is unique across all tables
            candidates = col_to_tables.get(k) or col_to_tables.get(k.lower()) or set()
            if len(candidates) == 1:
                only_tbl = next(iter(candidates))
                canon = lower_to_canonical.get(f"{only_tbl}.{k}".lower())
                if canon:
                    result[canon] = desc
                    matched_by_unique_column += 1
            else:
                if candidates:
                    skipped_ambiguous += 1  # present in multiple tables

        logger.info(
            "Intersect: result=%d (exact=%d, unique-col=%d, ambiguous-skipped=%d)",
            len(result), matched_exact, matched_by_unique_column, skipped_ambiguous
        )
        logger.debug("Intersect: sample result: %s", _sample_dict(result))
        return result

    except Exception as e:
        logger.exception(
            "collect_db_confluence_key_descriptions failed for space=%r title=%r host=%s port=%s db=%s user=%s err=%s",
            space, title, host, port, database, user, e
        )
        raise


@mcp.tool()
async def list_databases(
    host: str,
    port: int,
    user: str,
    password: str,
    database_type: str = "postgres"
) -> List[str]:
    """
    Retrieve all database names from a server, for Postgres or MSSQL.

    This tool connects to the specified host/port with the given credentials,
    then lists all non-system databases. For Postgres it uses the "postgres"
    maintenance database; for MSSQL it uses "master".

    Args:
      host (str):          IP or hostname of the DB server.
      port (int):          TCP port (Postgres default 5432, MSSQL default 1433).
      user (str):          Username with list-permissions.
      password (str):      Password for the user.
      database_type (str): Either "postgres" or "mssql".

    Returns:
      List[str]:           List of database names.

    Raises:
      ValueError:
        If `database_type` is unsupported.
      asyncpg.PostgresError:
        On any Postgres connection or query failure.
      mssql_python.Error:
        On any MSSQL connection or query failure.  # DB-API base exception :contentReference[oaicite:2]{index=2}:contentReference[oaicite:3]{index=3}
    """
    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database="postgres", min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database="master")
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    await client.init()
    logger.info("Connected to %s at %s:%s as %s", database_type, host, port, user)

    try:
        dbs = await client.list_databases()
        logger.info("Databases found: %s", dbs)
        return dbs
    finally:
        await client.close()


@mcp.tool()
async def list_database_schemas(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    database_type: str = "postgres"
) -> List[str]:
    """
    List all schemas in the specified database, for Postgres or MSSQL.

    This tool connects to the specified database and returns all user-defined
    schemas, excluding system schemas like information_schema, pg_catalog, etc.

    Args:
      host (str):          IP or hostname of the DB server.
      port (int):          TCP port (Postgres default 5432, MSSQL default 1433).
      user (str):          Username with list-permissions.
      password (str):      Password for the user.
      database (str):      Database name to inspect for schemas.
      database_type (str): Either "postgres" or "mssql".

    Returns:
      List[str]:           List of schema names.

    Raises:
      ValueError:
        If `database_type` is unsupported.
      asyncpg.PostgresError:
        On any Postgres connection or query failure.
      mssql_python.Error:
        On any MSSQL connection or query failure.
    """
    logger.info(
        "list_database_schemas called against %s:%s/%s as %s (%s)",
        host, port, database, user, database_type
    )

    if database_type == "postgres":
        client = PostgresClient(
            host, port, user, password,
            database=database, min_size=1, max_size=5
        )
    elif database_type == "mssql":
        client = MSSQLClient(
            host, port, user, password,
            database=database
        )
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    await client.init()
    try:
        schemas_list: List[str] = await client.list_schemas()
        logger.debug("Raw schemas_list for %s: %r", database_type, schemas_list)
        return schemas_list
    except Exception as e:
        logger.error(
            "❌ list_database_schemas failed for %s://%s:%s/%s as %s",
            database_type, host, port, database, user,
            exc_info=True
        )
        raise
    finally:
        await client.close()


@mcp.tool()
async def list_database_tables(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = "",
    database_type: str = "postgres"
) -> str:
    """
    List all user tables and views in the specified database, for Postgres or MSSQL.

    Returns:
      A JSON‐encoded array of table and view names, e.g. '["shops","items","sales","customer_view"]'.

    Raises:
      ValueError: If `database_type` is unsupported.
      Otherwise, re-raises any DB client errors so you can see them.
    """
    logger.info(
        "🔍 list_database_tables called against %s:%s/%s as %s (%s) - including tables and views",
        host, port, database or "<default>", user, database_type
    )

    # 1) Instantiate the right client
    if database_type == "postgres":
        client = PostgresClient(
            host, port, user, password,
            database=database or "postgres", min_size=1, max_size=5
        )
    elif database_type == "mssql":
        client = MSSQLClient(
            host, port, user, password,
            database=database or "master"
        )
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    # 2) Open
    await client.init()

    try:
        # 3) Fetch raw list
        tables_list: List[str] = await client.list_tables()
        logger.info("📋 Retrieved %d database objects (tables and views) for %s", 
                   len(tables_list), database_type)
        logger.debug("Raw objects list for %s: %r", database_type, tables_list)

        # 4) Serialize
        tables_json = json.dumps(tables_list)
        logger.debug("Returning tables_json: %s", tables_json)

        return tables_json

    except Exception as e:
        # 5) Log full traceback so you see *why* MSSQL is failing
        logger.error(
            "❌ list_database_tables failed for %s://%s:%s/%s as %s",
            database_type, host, port, database or "<default>", user,
            exc_info=True
        )
        # Re-raise so the MCP server surfaces the error
        raise

    finally:
        # 6) Always close
        await client.close()


@mcp.tool()
async def list_database_keys(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    database_type: str = "postgres"
) -> Dict[str, List[str]]:
    """
    List all column names (“keys”) for each table in the specified database,
    for Postgres or MSSQL.

    Steps:
      1. Initialize the appropriate client.
      2. Call client.list_keys().
      3. Close the pool.
      4. Return the mapping.

    Args:
      host (str):          DB host.
      port (int):          DB port.
      user (str):          Username.
      password (str):      Password.
      database (str):      Database to inspect.
      database_type (str): Either "postgres" or "mssql".

    Returns:
      Dict[str, List[str]]:
        e.g. {
          "shops": ["shop_id", "name", ...],
          "items": ["item_id", "shop_id", ...]
        }

    Raises:
      ValueError:
        If `database_type` is unsupported.
      asyncpg.PostgresError:
        On any Postgres connection or query failure.
      mssql_python.Error:
        On any MSSQL connection or query failure.  # DB-API base exception :contentReference[oaicite:6]{index=6}:contentReference[oaicite:7]{index=7}
    """
    logger.info(
        "🔍 list_database_keys called against %s:%s/%s as %s (%s) - including tables and views",
        host, port, database, user, database_type
    )

    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    try:
        await client.init()
        logger.info("✅ Database client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database client: {e}")
        raise
        
    try:
        keys_map = await client.list_keys()
        logger.info("📋 Retrieved column mappings for %d database objects (tables and views)", len(keys_map))
        logger.info("📋 Sample tables: %s", list(keys_map.keys())[:5])
        logger.debug("Keys map: %s", keys_map)
        return keys_map
    except Exception as e:
        logger.error(f"❌ Error calling client.list_keys(): {e}")
        raise
    finally:
        try:
            await client.close()
            logger.info("✅ Database client closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database client: {e}")

@mcp.tool()
async def get_database_column_metadata(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    schema: str = None,
    database_type: str = "postgres"
) -> Dict[str, Dict[str, Any]]:
    """
    Get detailed metadata for all columns including data types and schema information.
    
    Returns a mapping where each key is "schema.table.column" and value contains:
    - table_name, column_name, data_type, table_schema, is_nullable, etc.
    
    Args:
      host (str):          DB host.
      port (int):          DB port.
      user (str):          Username.
      password (str):      Password.
      database (str):      Database to inspect.
      schema (str):        Optional schema filter. If None, includes all user schemas.
      database_type (str): Either "postgres" or "mssql".
    
    Returns:
      Dict[str, Dict[str, Any]]: Comprehensive column metadata
    """
    logger.info(
        "🔍 get_database_column_metadata called against %s:%s/%s as %s (%s) - schema filter: %s",
        host, port, database, user, database_type, schema or "ALL"
    )

    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    await client.init()
    try:
        metadata = await client.get_column_metadata(schema=schema)
        logger.info("📋 Retrieved metadata for %d columns", len(metadata))
        logger.debug("Sample metadata keys: %s", list(metadata.keys())[:5])
        return metadata
    finally:
        await client.close()


@mcp.tool()
async def get_enhanced_schema_with_confluence(
    space: str,
    title: str,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    columns: List[str],
    database_type: str = "postgres"
) -> Dict[str, List[Dict[str, str]]]:
    """
    Create enhanced schema structure ONLY for the specified columns.
    
    Takes a list of specific columns (table.column format) and returns only those
    with descriptions from Confluence and types from database.
    
    Args:
        space (str): Confluence space
        title (str): Confluence page title  
        host (str): Database host
        port (int): Database port
        user (str): Database username
        password (str): Database password
        database (str): Database name
        columns (List[str]): Specific columns to fetch (e.g., ["shops.id", "shops.name"])
        database_type (str): Either "postgres" or "mssql"
    
    Returns:
        Dict[str, List[Dict[str, str]]]: 
        {
            "schema.table": [
                {"name": "column", "description": "...", "type": "varchar"}, 
                ...
            ],
            ...
        }
    """
    logger.info("🔍 get_enhanced_schema_with_confluence called for %d specific columns", len(columns))
    logger.info(f"📊 Database: {host}:{port}/{database} as {user}")
    logger.info(f"📋 Confluence: {space}/{title}")
    logger.debug("📋 Requested columns (first 10): %s", columns[:10])  # Log first 10 columns
    
    # 1. Get database metadata for ALL columns (we'll filter later)
    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    try:
        await client.init()
        logger.info("✅ Database client initialized for enhanced schema")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database client for enhanced schema: {e}")
        raise
        
    try:
        # Get detailed column metadata with types
        column_metadata = await client.get_column_metadata()
        logger.info("📊 Got metadata for %d total columns from database", len(column_metadata))
        
    except Exception as e:
        logger.error(f"❌ Error getting column metadata: {e}")
        raise
    finally:
        try:
            await client.close()
            logger.info("✅ Database client closed for enhanced schema")
        except Exception as e:
            logger.error(f"❌ Error closing database client for enhanced schema: {e}")
    
    # 2. Get Confluence descriptions for the specific columns
    logger.info("📋 Fetching Confluence descriptions from %s/%s", space, title)
    try:
        confluence_descriptions = await collect_db_confluence_key_descriptions(
            space=space,
            title=title,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        logger.info("✅ Got %d descriptions from Confluence", len(confluence_descriptions))
    except Exception as e:
        logger.warning("⚠️ Failed to get Confluence descriptions: %s", e)
        confluence_descriptions = {}
    
    # 3. Build enhanced schema structure ONLY for requested columns
    enhanced_schema = {}
    processed_columns = 0
    
    def _normalize_column_spec(column_spec: str) -> str:
        """Normalize column spec to table.column format in case schema.table.column is passed."""
        if not column_spec or "." not in column_spec:
            return column_spec
            
        parts = column_spec.split(".")
        if len(parts) == 2:
            # Already in table.column format
            return column_spec
        elif len(parts) == 3:
            # schema.table.column format - return table.column
            logger.debug("Normalizing column spec: %s -> %s.%s", column_spec, parts[1], parts[2])
            return f"{parts[1]}.{parts[2]}"
        else:
            # Unexpected format - return as-is
            logger.warning("Unexpected column spec format: %s", column_spec)
            return column_spec
    
    for column_spec in columns:
        # Normalize the column specification
        normalized_spec = _normalize_column_spec(column_spec)
        
        if "." not in normalized_spec:
            logger.warning("⚠️ Invalid column format '%s' (original: '%s') - skipping", normalized_spec, column_spec)
            continue
            
        table_name = normalized_spec.split(".", 1)[0]
        column_name = normalized_spec.split(".", 1)[1]
        
        # Find the schema and metadata for this specific column
        table_schema = "public"  # default
        data_type = "UNKNOWN"
        
        # Look for this column in database metadata
        for meta_key, meta_data in column_metadata.items():
            if (meta_data["table_name"] == table_name and 
                meta_data["column_name"] == column_name):
                table_schema = meta_data["table_schema"]
                data_type = meta_data["data_type"]
                break
        
        schema_table_key = f"{table_schema}.{table_name}"
        
        # Get description from Confluence for this specific column
        description = confluence_descriptions.get(normalized_spec, "")
        
        # Create the column entry
        column_entry = {
            "name": column_name,
            "description": description,
            "type": data_type
        }
        
        # Add to enhanced schema
        if schema_table_key not in enhanced_schema:
            enhanced_schema[schema_table_key] = []
        
        enhanced_schema[schema_table_key].append(column_entry)
        processed_columns += 1
        
        logger.debug("✅ Processed %s -> schema=%s, type=%s, desc_len=%d", 
                    normalized_spec, table_schema, data_type, len(description))
    
    logger.info("✅ Built enhanced schema for %d columns across %d schema.table entries", 
               processed_columns, len(enhanced_schema))
    
    # Log sample for debugging  
    if enhanced_schema:
        sample_key = list(enhanced_schema.keys())[0]
        sample_columns = enhanced_schema[sample_key][:2]  # First 2 columns
        logger.debug("📋 Sample enhanced schema entry '%s': %s", sample_key, sample_columns)
    
    return enhanced_schema


@mcp.tool()
async def generate_column_data_for_confluence(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    columns: List[str],
    database_type: str = "postgres"
) -> List[Dict[str, Any]]:
    """
    Generate a complete data structure for Confluence sync from a list of column names.
    
    This function takes a simple list of column names (e.g., ["table.column1", "table.column2"])
    and returns a complete structure with descriptions, types, schemas, and empty owner fields
    ready for Confluence table synchronization.
    
    Args:
        host (str): Database host
        port (int): Database port  
        user (str): Database username
        password (str): Database password
        database (str): Database name
        columns (List[str]): List of column names in "table.column" format
        database_type (str): Either "postgres" or "mssql"
    
    Returns:
        List[Dict[str, Any]]: List of complete column data structures with:
            - column: "table.column"
            - description: Generated description (empty if generation fails)
            - type: Data type from database metadata
            - schema: Schema name from database metadata  
            - owner: Empty string (to be filled later)
    """
    logger.info("🔍 generate_column_data_for_confluence called for %d columns", len(columns))
    logger.debug("📋 Input columns: %s", columns[:5] + ["..."] if len(columns) > 5 else columns)
    
    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    await client.init()
    try:
        # Get comprehensive metadata for all columns
        metadata = await client.get_column_metadata()
        logger.info("📊 Retrieved metadata for %d total columns in database", len(metadata))
        
        result = []
        for col_spec in columns:
            try:
                # Parse table.column format
                if "." not in col_spec:
                    logger.warning("⚠️  Column spec '%s' missing table prefix, skipping", col_spec)
                    continue
                    
                table_name = col_spec.split(".", 1)[0]
                column_name = col_spec.split(".", 1)[1]
                
                # Find matching metadata entry
                metadata_entry = None
                column_schema = "public"  # default
                data_type = "unknown"
                
                # Try to find exact match with schema
                for meta_key, meta_data in metadata.items():
                    if (meta_data["table_name"] == table_name and 
                        meta_data["column_name"] == column_name):
                        metadata_entry = meta_data
                        column_schema = meta_data["table_schema"]
                        data_type = meta_data["data_type"]
                        break
                
                if not metadata_entry:
                    logger.warning("⚠️  No metadata found for column %s", col_spec)
                    column_schema = "public"
                    data_type = "unknown"
                
                # Create complete entry structure
                entry = {
                    "column": col_spec,
                    "description": "",  # Will be filled by describe_columns if needed
                    "type": data_type,
                    "schema": column_schema,
                    "owner": ""
                }
                
                result.append(entry)
                logger.debug("✅ Processed %s: type=%s, schema=%s", col_spec, data_type, column_schema)
                
            except Exception as e:
                logger.error("❌ Error processing column %s: %s", col_spec, e)
                # Add entry with minimal info
                result.append({
                    "column": col_spec,
                    "description": f"Error: {e}",
                    "type": "unknown",
                    "schema": "unknown", 
                    "owner": ""
                })
        
        logger.info("✅ Generated %d complete column data entries", len(result))
        return result
        
    finally:
        await client.close()


@mcp.tool()
async def get_table_delta_keys(
    space: str,
    title: str,
    columns: List[str]
) -> str:
    """
    Return the subset of `columns` that are not present in the
    <table class="relative-table"> on the Confluence page, as a JSON array.
    
    If no table exists on the page, returns all columns (since they're all "missing").

    Args:
      space (str):     Confluence space key (e.g., "PROJ").
      title (str):     Page title.
      columns (List[str]):
        List of column names (e.g. ["shops.id","shops.name", …]).

    Returns:
      str: JSON‐encoded list of column names that do NOT already appear
           as the first <td> in any row of the existing table, for example:
           '["sales.channel","sales.transaction_ref","sales.loyalty_points","sales.notes"]'.
           If no table exists, returns all input columns.

    Raises:
      Exception: Propagates errors from the Confluence client.
    """
    page_id = await confluence.get_page_id(space, title)
    page = await confluence.get_page_content(page_id, expand="body.storage")
    html = page["body"]["storage"]["value"]

    soup = BeautifulSoup(html, "html.parser")
    tbl = soup.find("table", class_="relative-table")
    if not tbl:
        # No table exists yet - all columns are "missing" and need to be added
        logger.info("📋 No existing table found on page '%s' - all %d columns are new", title, len(columns))
        return json.dumps(columns)

    existing = {
        tr.find("td").text.strip()
        for tr in tbl.find_all("tr")[1:]
        if tr.find("td") and tr.find("td").text
    }
    delta = [c for c in columns if c not in existing]

    logger.debug("Confluence columns: %s", existing)
    logger.debug("Database columns:    %s", columns)
    logger.debug("Delta columns:       %s", delta)

    # Return the full delta array as one JSON-encoded string
    return json.dumps(delta)

@mcp.tool()
async def suggest_keys_for_analytics(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    system_prompt: str,
    user_prompt: str
) -> str:
    """
    Suggests which table columns (“keys”) BI developers should use for a given analytics request.

    1. Connects to the specified Postgres database.
    2. Retrieves all tables and their column names (list_keys).
    3. Calls the remote LLM with:
       • system_prompt: guidance that “You are a BI assistant…”
       • user_prompt: the analytics question (e.g., “Show me top-selling items…”)
       • context: JSON of { table: [columns,…], … }
    4. Returns the LLM’s recommendation as a single string.

    Args:
      host (str):         Postgres host/IP.
      port (int):         Postgres port (5432).
      user (str):         DB username.
      password (str):     DB password.
      database (str):     DB name (e.g., “malldb”).
      system_prompt (str):
         Instruction to the LLM, e.g.
         “You are a BI assistant. Given table schemas, pick the
          columns needed to answer the user’s query.”
      user_prompt (str):  The actual analytics request from the user.

    Returns:
      str: The LLM’s answer, listing the relevant keys.

    Raises:
      asyncpg.PostgresError: On DB connection/query errors.
      HTTPError:            On LLM API failures.
    """
    # 1) Fetch schema keys and metadata
    logger.info("🔍 suggest_keys_for_analytics called for database %s:%s/%s", 
               host, port, database)
    
    pg = PostgresClient(
        host=host, port=port,
        user=user, password=password,
        database=database,
        min_size=1, max_size=5
    )
    await pg.init()
    try:
        # Get basic table->columns mapping
        keys_map: Dict[str, List[str]] = await pg.list_keys()
        
        # Get detailed column metadata for schema context
        metadata = await pg.get_column_metadata()
        
        logger.info("📊 Retrieved %d tables and %d column metadata entries", 
                   len(keys_map), len(metadata))
        
        # Build schema-aware context
        schema_context = {}
        for table, columns in keys_map.items():
            # Find schema for this table by looking at metadata
            table_schema = "public"  # default
            for meta_key, meta_data in metadata.items():
                if meta_data["table_name"] == table:
                    table_schema = meta_data["table_schema"]
                    break
            
            # Use schema.table as key for better context
            schema_table_key = f"{table_schema}.{table}"
            schema_context[schema_table_key] = columns
        
        logger.debug("Schema-aware context built: %d schema.table entries", len(schema_context))
        
    finally:
        await pg.close()

    # 2) Prepare enhanced context for LLM with schema information
    context_parts = [
        f"PostgreSQL database '{database}' schema information with schema qualifiers:",
        json.dumps(schema_context, indent=2),
        "",
        f"IMPORTANT: All tables are within the SINGLE database named '{database}'.",
        "The format 'schema.table' refers to SCHEMA.TABLE within the same database.",
        "When suggesting columns, use format 'schema.table.column' (e.g., 'public.users.id').",
        "Do NOT suggest database.table.column format - only schema.table.column.",
        "All schemas shown are within the same PostgreSQL database."
    ]
    context = "\n".join(context_parts)

    # 3) Invoke LLM with enhanced context
    logger.info("📤 Calling LLM with schema-aware context (%d chars)", len(context))
    recommendation = await llm.call_remote_llm(
        context=context,
        prompt=user_prompt,
        system_prompt=system_prompt
    )

    logger.info("✅ LLM recommendation received (%d chars)", len(recommendation or ""))
    logger.debug("LLM recommendation preview: %s", (recommendation or "")[:200])
    return recommendation


@mcp.tool()
async def run_analytics_query_on_database(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    analytics_prompt: str,
    system_prompt: str
) -> List[Dict[str, Any]]:
    """
    1. Introspect tables+columns.
    2. Ask LLM to generate a JOIN/aggregation SQL.
    3. Execute that SQL, return the resulting rows.
    """
    def _strip_sql_fences(txt: str) -> str:
        """Enhanced SQL fence stripping with comprehensive logging"""
        if not txt:
            logger.warning("⚠️ _strip_sql_fences: Empty input")
            return txt
        
        logger.info(f"🔧 _strip_sql_fences: Input length {len(txt)} chars")
        logger.debug(f"🔧 _strip_sql_fences: Raw input: {txt[:200]}...")
        
        original_txt = txt
        
        # Remove HTML code tags
        t = re.sub(r"</?code[^>]*>", "", txt, flags=re.I)
        if t != txt:
            logger.debug("🔧 Removed HTML code tags")
        
        # Look for SQL code blocks
        m = re.search(r"```(?:sql)?\s*(.*?)```", t, flags=re.S | re.I)
        if m:
            t = m.group(1)
            logger.debug(f"🔧 Extracted from code block, new length: {len(t)}")
        else:
            logger.debug("🔧 No code block found, proceeding with full text")
        
        # Remove any remaining backticks
        t = t.replace("```", "").strip()
        
        # Remove leading "sql:" or "SQL:" labels
        before_label_removal = t
        t = re.sub(r"^\s*sql\s*[:\-]?\s*", "", t, flags=re.I)
        if t != before_label_removal:
            logger.debug("🔧 Removed SQL label prefix")
        
        logger.info(f"🔧 _strip_sql_fences: Final SQL length {len(t)} chars")
        logger.debug(f"🔧 _strip_sql_fences: Final SQL preview: {t[:100]}...")
        
        if not t.strip():
            logger.error(f"❌ _strip_sql_fences: Result is empty! Original was: {original_txt[:500]}")
        
        return t

    logger.info("🔍 run_analytics_query_on_database: start host=%s port=%s db=%s user=%s", host, port, database, user)

    # 1) Get schema and metadata
    pg = PostgresClient(host, port, user, password, database)
    await pg.init()
    try:
        # Get basic table->column structure
        schema = await pg.list_keys()
        
        # Get detailed metadata for schema context
        metadata = await pg.get_column_metadata()
        
        logger.info("📊 Retrieved %d tables and %d column metadata entries for SQL building", 
                   len(schema), len(metadata))
        
        # Build schema-aware context for LLM
        enhanced_schema = {}
        for table, columns in schema.items():
            # Find schema for this table
            table_schema = "public"  # default
            for meta_key, meta_data in metadata.items():
                if meta_data["table_name"] == table:
                    table_schema = meta_data["table_schema"]
                    break
            
            # Use schema.table as key and include type information
            schema_table_key = f"{table_schema}.{table}"
            column_details = []
            
            for col in columns:
                # Find column type from metadata
                col_type = "unknown"
                full_meta_key = f"{table_schema}.{table}.{col}"
                if full_meta_key in metadata:
                    col_type = metadata[full_meta_key]["data_type"]
                
                column_details.append(f"{col} ({col_type})")
            
            enhanced_schema[schema_table_key] = column_details
        
    except Exception as e:
        logger.exception("❌ DB schema introspection failed: %s", e)
        await pg.close()
        raise

    # 2) Enhanced context with schema and type information
    context_parts = [
        f"PostgreSQL database '{database}' schema with types and schema qualifiers:",
        json.dumps(enhanced_schema, indent=2),
        "",
        f"CRITICAL: You are working within a SINGLE database named '{database}'.",
        "The format 'schema.table' refers to SCHEMA.TABLE within the same database, NOT different databases.",
        "Example valid PostgreSQL queries:",
        "- SELECT * FROM public.users;",
        "- SELECT * FROM analytics.sales JOIN public.users ON sales.user_id = users.id;",
        "- SELECT count(*) FROM inventory.products;",
        "",
        "NEVER use database.table format - only use schema.table format.",
        "All tables shown are within the same PostgreSQL database.",
        "Column types are shown in parentheses for reference."
    ]
    context = "\n".join(context_parts)
    logger.info("📤 Enhanced context for LLM: %d chars", len(context))

    # 3) LLM
    sql_raw = await llm.call_remote_llm(
        context=context,
        prompt=analytics_prompt,
        system_prompt=system_prompt
    )
    logger.info("🤖 LLM returned SQL (raw) length=%d", len(sql_raw or 0))
    logger.debug(f"🤖 Raw SQL from LLM: {sql_raw}")
    
    sql = _strip_sql_fences(sql_raw)
    logger.info("🔍 Generated SQL (final query, length: %d chars):\n%s", len(sql), sql)

    # 4) Execute with proper error handling
    rows = []
    query_error = None
    
    # Validate SQL before execution
    if not sql or not sql.strip():
        query_error = "Generated SQL is empty after processing"
        logger.error(f"❌ {query_error}")
        logger.error(f"❌ Raw LLM output was: {sql_raw}")
    else:
        try:
            rows = await pg.execute_query(sql)
            logger.info("✅ Query executed successfully: rows=%d", len(rows or []))
            if rows:
                logger.info("📊 First row sample (first 5 columns): %s", {k: v for k, v in list(rows[0].items())[:5]} if rows[0] else "N/A")
                logger.debug("📊 Full first row sample: %s", rows[0])
            else:
                logger.info("📊 Query returned no rows")
        except Exception as ex:
            query_error = str(ex)
            logger.error("❌ SQL execution failed: %s", query_error)
            logger.error("❌ Failed SQL query was:\n%s", sql)
    
    # Always close DB connection
    logger.debug("Closing DB pool...")
    await pg.close()

    # Return comprehensive result
    result = {
        "rows": rows, 
        "sql": sql,
        "raw_sql": sql_raw,
        "execution_successful": query_error is None
    }
    
    if query_error:
        result["error"] = query_error
        logger.info("❌ Returning result with execution error")
    else:
        logger.info("✅ Returning successful result")
    
    logger.info(f"📊 Analytics query result: {len(rows)} rows, SQL length: {len(sql)} chars, success: {query_error is None}")
    return result


@mcp.tool()
async def describe_columns(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    table: str,
    columns: List[str],
    limit: int,
    database_type: str = "postgres"
) -> str:
    """
    Describe only the given `columns` of `table` (or view) for Postgres or MSSQL.

    1. Connects to the correct database type (PostgresClient or MSSQLClient).
    2. Gets column metadata including data types and schema information.
    3. Samples up to `limit` values per column.
    4. Asks the LLM to produce a one-line description for each (excluding type info).

    Returns a JSON‐encoded array of:
      [{ 
        "column": "table.col", 
        "description": "...", 
        "type": "data_type",
        "schema": "schema_name",
        "owner": "",  # Empty for Confluence sync compatibility
        "values": [...] 
      }, …]

    Raises:
      ValueError: If `database_type` is unsupported.
    """
    logger.info("🔍 describe_columns called for table/view '%s' in %s:%s/%s (%s)", 
               table, host, port, database, database_type)
    
    # 1) Pick the right client
    if database_type == "postgres":
        client = PostgresClient(
            host, port, user, password,
            database=database, min_size=1, max_size=5
        )
    elif database_type == "mssql":
        client = MSSQLClient(
            host, port, user, password,
            database=database
        )
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    # 2) Initialize
    await client.init()

    try:
        # First get the schema for this table
        schema_name = await client.get_table_schema(table)
        logger.info("📂 Using schema '%s' for table '%s'", schema_name, table)
        
        # Get comprehensive column metadata
        metadata = await client.get_column_metadata(schema=schema_name)
        logger.info("📊 Retrieved metadata for %d columns in schema '%s'", len(metadata), schema_name)
        
        results: List[Dict[str, Any]] = []
        for col in columns:
            try:
                # Look for column metadata using various key formats
                full_key = f"{schema_name}.{table}.{col}"
                metadata_entry = metadata.get(full_key)
                
                if not metadata_entry:
                    # Try without schema if not found
                    alt_keys = [key for key in metadata.keys() 
                              if key.endswith(f".{table}.{col}")]
                    if alt_keys:
                        metadata_entry = metadata[alt_keys[0]]
                        logger.debug("Found metadata using alternate key: %s", alt_keys[0])
                
                # Extract type and schema information
                data_type = metadata_entry.get("data_type", "unknown") if metadata_entry else "unknown"
                column_schema = metadata_entry.get("table_schema", schema_name) if metadata_entry else schema_name
                
                # Get sample values
                vals = await client.get_column_values(table, col, limit)
                
                # Create LLM prompt with schema context and type exclusion
                prompt = (
                    f"Describe the purpose and meaning of column '{col}' from table '{table}' "
                    f"in schema '{column_schema}'. "
                    f"Here are up to {limit} example values: {vals}. "
                    f"The column type is {data_type}. "
                    f"Provide only a brief functional description of what this column represents - "
                    f"do NOT include the data type in your description as that will be stored separately. "
                    f"Focus on the business meaning and purpose."
                )
                
                desc = await llm.call_remote_llm(
                    context=f"Database schema context: {column_schema}.{table}",
                    prompt=prompt
                )
                
                results.append({
                    "column":      f"{table}.{col}",
                    "description": desc.strip(),
                    "type":        data_type,
                    "schema":      column_schema,
                    "owner":       "",  # Empty owner field for Confluence sync compatibility
                    "values":      vals
                })
                
                logger.debug("✅ Processed column %s.%s: type=%s, schema=%s", 
                           table, col, data_type, column_schema)
                           
            except Exception as inner:
                logger.error(
                    "❌ describe_columns error for %s.%s: %s",
                    table, col, inner, exc_info=True
                )
                results.append({
                    "column":      f"{table}.{col}",
                    "description": f"<error: {inner}>",
                    "type":        "unknown",
                    "schema":      schema_name,
                    "owner":       "",  # Empty owner field for Confluence sync compatibility
                    "values":      []
                })

        logger.info("✅ Successfully processed %d columns with metadata", len(results))
        logger.debug("Sample result: %r", results[0] if results else None)
        return json.dumps(results, default=str, separators=(",",":"))

    finally:
        await client.close()


# REMOVED: analyze_dbt_file_for_iterative_query MCP tool - now handled client-side

# REMOVED: _analyze_dbt_structure_dynamic and _infer_table_depth_dynamic - now handled client-side


# REMOVED: ask_ai_sufficiency_decision MCP tool - now handled client-side

@mcp.tool()
async def list_database_keys_filtered_by_depth(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    approved_tables: List[str],
    database_type: str = "postgres"
) -> Dict[str, List[str]]:
    """
    List column names ("keys") only for tables that are in the approved depth list.
    
    This is a filtered version of list_database_keys that only returns columns
    for tables that have been approved in the iterative dbt analysis.
    
    Args:
      host (str):          DB host.
      port (int):          DB port.
      user (str):          Username.
      password (str):      Password.
      database (str):      Database to inspect.
      approved_tables (List[str]): List of table names that were approved in iterative analysis.
      database_type (str): Either "postgres" or "mssql".

    Returns:
      Dict[str, List[str]]:
        e.g. {
          "approved_table1": ["col1", "col2", ...],
          "approved_table2": ["col1", "col2", ...]
        }
        Only includes tables from approved_tables list.
    """
    logger.info(
        f"🔍 list_database_keys_filtered_by_depth called for {len(approved_tables)} approved tables: {approved_tables}"
    )

    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    await client.init()
    try:
        # Get all keys first
        all_keys = await client.list_keys()
        
        # Filter to only include approved tables
        filtered_keys = {}
        approved_set = set(approved_tables)
        
        for table_name, columns in all_keys.items():
            if table_name in approved_set:
                filtered_keys[table_name] = columns
                logger.info(f"✅ Included table '{table_name}' with {len(columns)} columns")
            else:
                logger.debug(f"🚫 Skipped table '{table_name}' (not in approved list)")
        
        logger.info(f"📊 Filtered results: {len(filtered_keys)} tables from {len(all_keys)} total")
        return filtered_keys
        
    except Exception as e:
        logger.error(f"❌ Error in list_database_keys_filtered_by_depth: {e}", exc_info=True)
        raise
    finally:
        await client.close()


@mcp.tool()
async def run_analytics_query_on_approved_tables(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    analytics_prompt: str,
    approved_tables: List[str],
    database_type: str = "postgres",
    confluence_space: str = "",
    confluence_title: str = ""
) -> Dict[str, Any]:
    """
    Execute an analytics query only on tables that are in the approved depth list.
    
    This is a filtered version of run_analytics_query_on_database that only considers
    tables that have been approved in the iterative dbt analysis.
    
    Args:
      host (str):          DB host.
      port (int):          DB port.
      user (str):          Username.
      password (str):      Password.
      database (str):      Database to inspect.
      analytics_prompt (str): The analytics question/prompt.
      approved_tables (List[str]): List of table names that were approved in iterative analysis.
      database_type (str): Either "postgres" or "mssql".
      confluence_space (str): Confluence space for context (optional).
      confluence_title (str): Confluence page title for context (optional).

    Returns:
      Dict[str, Any]: Query results including SQL, data, and metadata.
    """
    logger.info(
        f"🔍 run_analytics_query_on_approved_tables called for {len(approved_tables)} approved tables"
    )
    logger.info(f"📊 Database: {host}:{port}/{database} as {user}")
    logger.info(f"📊 Analytics prompt: {analytics_prompt[:100]}...")
    logger.info(f"✅ Approved tables: {approved_tables}")
    logger.info(f"📋 Confluence context: {confluence_space}/{confluence_title}")
    logger.info(f"🔧 Database type: {database_type}")

    if database_type == "postgres":
        client = PostgresClient(host, port, user, password,
                                database=database, min_size=1, max_size=5)
    elif database_type == "mssql":
        client = MSSQLClient(host, port, user, password,
                             database=database)
    else:
        raise ValueError(f"Unsupported database_type: {database_type!r}")

    try:
        await client.init()
        logger.info("✅ Database client initialized for analytics query")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database client for analytics: {e}")
        raise
    try:
        # Get schema information only for approved tables
        logger.info("🔍 Getting schema information for approved tables...")
        
        # Get all tables/views first
        all_tables = await client.list_tables()
        
        # Filter to only approved tables (all_tables is now a list of strings)
        approved_schemas = []
        approved_set = set(approved_tables)
        
        for table_name in all_tables:
            if table_name in approved_set:
                # Detect actual schema by checking if table_name contains schema
                if "." in table_name:
                    schema_name, actual_table_name = table_name.split(".", 1)
                else:
                    # Use get_table_schema to find the correct schema for this table
                    if database_type == "postgres":
                        schema_name = await client.get_table_schema(table_name)
                        actual_table_name = table_name
                        logger.info(f"🔍 Detected schema '{schema_name}' for table '{table_name}' using get_table_schema()")
                    else:
                        schema_name = "dbo"  # Default MSSQL schema
                        actual_table_name = table_name
                
                # Create table info object for compatibility with rest of the code
                table_info = {
                    "table_name": actual_table_name,
                    "name": actual_table_name,
                    "schema": schema_name,
                    "full_name": f"{schema_name}.{actual_table_name}" if schema_name != "public" else actual_table_name  # Keep the full qualified name
                }
                approved_schemas.append(table_info)
                logger.info(f"✅ Included table schema for '{table_name}' (schema: {schema_name}, table: {actual_table_name}, full_name: {table_info['full_name']})")
                logger.debug(f"🔍 Table info stored: {table_info}")
            else:
                logger.debug(f"🚫 Skipped table schema for '{table_name}' (not approved)")
        
        logger.info(f"📊 Filtered schema: {len(approved_schemas)} tables from {len(all_tables)} total")
        
        # Get column information only for approved tables
        logger.info("🔍 Getting column information for approved tables...")
        approved_columns = []
        
        if database_type == "postgres":
            # Use get_column_metadata to get all column details at once for PostgreSQL
            all_column_metadata = await client.get_column_metadata()
            
            for table_info in approved_schemas:
                actual_table_name = table_info.get("table_name", table_info.get("name", ""))
                schema_name = table_info.get("schema")
                full_table_name = table_info.get("full_name", actual_table_name)
                
                logger.info(f"🔍 Processing table: actual_table_name='{actual_table_name}', schema_name='{schema_name}', full_table_name='{full_table_name}'")
                
                # Filter metadata for this specific table
                table_columns = []
                for metadata_key, metadata in all_column_metadata.items():
                    # metadata_key format is "schema.table.column"
                    metadata_schema = metadata.get("table_schema")
                    metadata_table = metadata.get("table_name")
                                        
                    if metadata_schema == schema_name and metadata_table == actual_table_name:
                        # Convert to the format expected by the rest of the code
                        column_info = {
                            "table_name": actual_table_name,
                            "column_name": metadata.get("column_name"),
                            "data_type": metadata.get("data_type"),
                            "schema_name": schema_name,
                            "full_table_name": full_table_name,
                            "is_nullable": metadata.get("is_nullable"),
                            "column_default": metadata.get("column_default"),
                            "character_maximum_length": metadata.get("character_maximum_length")
                        }
                        table_columns.append(column_info)
                        approved_columns.append(column_info)
                
                logger.info(f"✅ Got {len(table_columns)} columns for table '{full_table_name}' (schema: {schema_name})")
                if not table_columns:
                    logger.warning(f"⚠️ No columns found for table '{full_table_name}' in schema '{schema_name}'")
                    
        elif database_type == "mssql":
            # For MSSQL, fall back to list_keys method since get_column_metadata is not implemented
            logger.info("🔍 Using list_keys for MSSQL column information...")
            all_keys = await client.list_keys()
            
            for table_info in approved_schemas:
                actual_table_name = table_info.get("table_name", table_info.get("name", ""))
                schema_name = table_info.get("schema", "dbo")
                full_table_name = table_info.get("full_name", actual_table_name)
                
                # Get columns for this table from list_keys
                if actual_table_name in all_keys:
                    columns = all_keys[actual_table_name]
                    for column_name in columns:
                        column_info = {
                            "table_name": actual_table_name,
                            "column_name": column_name,
                            "data_type": "UNKNOWN",  # MSSQL client doesn't provide type info
                            "schema_name": schema_name,
                            "full_table_name": full_table_name,
                            "is_nullable": "UNKNOWN",
                            "column_default": None,
                            "character_maximum_length": None
                        }
                        approved_columns.append(column_info)
                    
                    logger.info(f"✅ Got {len(columns)} columns for table '{full_table_name}' (schema: {schema_name})")
                else:
                    logger.warning(f"⚠️ No columns found for table '{full_table_name}' in list_keys result")
        
        if not approved_columns:
            logger.error("❌ No columns found for any approved tables")
        else:
            logger.info(f"📊 Total approved columns collected: {len(approved_columns)}")
        
        logger.info(f"📊 Total approved columns: {len(approved_columns)}")
        
        # Build enhanced schema context only with approved tables
        enhanced_schema_context = ""
        if confluence_space and confluence_title:
            try:
                # Build column list for approved tables only
                approved_column_specs = []
                for table_name in approved_tables:
                    for col in approved_columns:
                        if col.get("table_name") == table_name:
                            approved_column_specs.append(f"{table_name}.{col.get('column_name', col.get('name', ''))}")
                
                logger.info(f"🔍 Building enhanced schema context for {len(approved_column_specs)} approved columns")
                
                enhanced_result = await get_enhanced_schema_with_confluence(
                    space=confluence_space,
                    title=confluence_title,
                    host=host,
                    port=port, 
                    user=user,
                    password=password,
                    database=database,
                    columns=approved_column_specs,
                    database_type=database_type
                )
                
                if enhanced_result:
                    enhanced_schema_context = json.dumps(enhanced_result, indent=2)
                    logger.info(f"✅ Built enhanced schema context for approved tables")
                        
            except Exception as e:
                logger.warning(f"⚠️ Failed to get enhanced schema context: {e}")
        else:
            logger.info("📋 No Confluence context provided, skipping enhanced schema")
        
        # Build the unified schema context combining all information
        logger.info("🔧 Building unified schema context for LLM prompt...")
        
        # Create a unified structure: schema.table -> columns with types and descriptions
        unified_schema = {}
        
        for table_info in approved_schemas:
            actual_table_name = table_info.get("table_name")
            schema_name = table_info.get("schema")
            full_table_name = f"{schema_name}.{actual_table_name}"
            
            # Initialize table entry
            unified_schema[full_table_name] = {
                "columns": []
            }
            
            # Get all columns for this table from approved_columns
            for col_info in approved_columns:
                if (col_info.get("table_name") == actual_table_name and 
                    col_info.get("schema_name") == schema_name):
                    
                    column_name = col_info.get("column_name")
                    data_type = col_info.get("data_type", "unknown")
                    
                    # Get description from enhanced_schema_context if available
                    description = ""
                    if enhanced_schema_context:
                        try:
                            enhanced_data = json.loads(enhanced_schema_context)
                            table_columns = enhanced_data.get(full_table_name, [])
                            for enhanced_col in table_columns:
                                if enhanced_col.get("name") == column_name:
                                    description = enhanced_col.get("description", "")
                                    break
                        except (json.JSONDecodeError, AttributeError):
                            pass
                    
                    # Add column to unified schema
                    unified_schema[full_table_name]["columns"].append({
                        "name": column_name,
                        "type": data_type,
                        "description": description
                    })
        
        logger.info(f"✅ Built unified schema for {len(unified_schema)} tables")
        
        # Format unified schema as clean text instead of JSON
        def _format_schema_as_text(schema_dict: Dict) -> str:
            """
            Convert unified schema dictionary to clean, token-efficient text format.
            
            Format:
            schema.table_name
                column_name (type) - description
                another_column (varchar) - description
            
            another_schema.table_name
                column_name (int) - description
            """
            if not schema_dict:
                return "No schema information available."
            
            lines = []
            for table_name, table_info in schema_dict.items():
                # Add table name
                lines.append(f"{table_name}")
                
                # Add columns with indentation
                columns = table_info.get("columns", [])
                for col in columns:
                    col_name = col.get("name", "unknown")
                    col_type = col.get("type", "unknown")
                    col_desc = col.get("description", "")
                    
                    # Format: column_name (type) - description
                    col_line = f"    {col_name} ({col_type})"
                    if col_desc.strip():
                        col_line += f" - {col_desc.strip()}"
                    
                    lines.append(col_line)
                
                # Add empty line between tables for readability
                lines.append("")
            
            return "\n".join(lines).strip()
        
        schema_text = _format_schema_as_text(unified_schema)
        logger.info(f"📝 Formatted schema as text: {len(schema_text)} characters (vs JSON: {len(json.dumps(unified_schema, indent=2))} chars)")
        logger.debug(f"📝 Schema text preview:\n{schema_text[:500]}...")
        
        # Create the clean, unified prompt
        enhanced_prompt = f"""
You are a PostgreSQL expert. Generate an analytical SQL query using the following database schema.

Original Analytics Request: {analytics_prompt}

DATABASE SCHEMA:
{schema_text}

CRITICAL SQL REQUIREMENTS:
1. **ONLY USE PROVIDED TABLES**: You MUST use ONLY the tables listed in the DATABASE SCHEMA above. Do NOT reference any other tables, views, or database objects that are not explicitly shown in the schema.
2. **EXACT TABLE NAMES**: Use the EXACT table names from the schema above - do not modify, abbreviate, or make up table names.
3. **EXACT COLUMN NAMES**: Use the EXACT column names shown in the schema - do not modify, abbreviate, or make up column names.
4. **Schema Qualification**: ALWAYS use fully qualified table names (schema.table_name format) exactly as shown in the schema.
5. **No Table Aliases**: Do NOT use table aliases like 't' or 'u' - use full schema.table_name format.
6. **PostgreSQL Syntax**: Use proper PostgreSQL syntax and functions.
7. **NO HALLUCINATION**: If you cannot answer the question with the provided tables and columns, say so rather than making up table or column names.

EXAMPLE CORRECT FORMAT:
SELECT public.users.id, public.users.name, analytics.sales.amount
FROM public.users 
JOIN analytics.sales ON public.users.id = analytics.sales.user_id
WHERE public.users.active = true;

QUERY GUIDELINES:
- Create meaningful joins based on common column names (id, foreign keys, etc.)
- Include appropriate aggregations, filters, and groupings to answer the question
- Add descriptive column aliases for readability
- Handle NULL values appropriately
- Use LIMIT clauses for performance when appropriate
- Focus on providing actionable business insights

IMPORTANT: Return ONLY the SQL query without any additional text, explanations, or formatting.
"""
        
        # Execute the analytics query with filtered context
        logger.info("🚀 Executing analytics query with approved tables context...")
        logger.info(f"📝 Enhanced prompt length: {len(enhanced_prompt)} characters")
        logger.debug(f"📝 Full enhanced prompt: {enhanced_prompt}")
        
        # Use LLM to generate SQL with the enhanced prompt
        logger.info("🤖 Calling LLM to generate SQL query...")
        sql_raw = await llm.call_remote_llm(
            context=enhanced_prompt,
            prompt="Generate an analytical SQL query based on the provided context and requirements.",
            system_prompt="You are a PostgreSQL expert. Generate efficient, analytical SQL queries that provide meaningful business insights. Use proper joins, aggregations, and filters. Return only the SQL query without explanation."
        )
        
        logger.info(f"🤖 LLM returned SQL (length: {len(sql_raw)} chars)")
        logger.debug(f"🤖 Raw SQL from LLM: {sql_raw}")
        
        # Clean the SQL (strip code fences) - using enhanced function for consistency
        def _strip_sql_fences_local(txt: str) -> str:
            """Enhanced SQL fence stripping with comprehensive logging"""
            if not txt:
                logger.warning("⚠️ _strip_sql_fences_local: Empty input")
                return txt
            
            logger.info(f"🔧 _strip_sql_fences_local: Input length {len(txt)} chars")
            logger.debug(f"🔧 _strip_sql_fences_local: Raw input: {txt[:200]}...")
            
            original_txt = txt
            
            # Remove HTML code tags
            t = re.sub(r"</?code[^>]*>", "", txt, flags=re.I)
            if t != txt:
                logger.debug("🔧 Removed HTML code tags")
            
            # Look for SQL code blocks
            m = re.search(r"```(?:sql)?\s*(.*?)```", t, flags=re.S | re.I)
            if m:
                t = m.group(1)
                logger.debug(f"🔧 Extracted from code block, new length: {len(t)}")
            else:
                logger.debug("🔧 No code block found, proceeding with full text")
            
            # Remove any remaining backticks
            t = t.replace("```", "").strip()
            
            # Remove leading "sql:" or "SQL:" labels
            before_label_removal = t
            t = re.sub(r"^\s*sql\s*[:\-]?\s*", "", t, flags=re.I)
            if t != before_label_removal:
                logger.debug("🔧 Removed SQL label prefix")
            
            logger.info(f"🔧 _strip_sql_fences_local: Final SQL length {len(t)} chars")
            logger.debug(f"🔧 _strip_sql_fences_local: Final SQL preview: {t[:100]}...")
            
            if not t.strip():
                logger.error(f"❌ _strip_sql_fences_local: Result is empty! Original was: {original_txt[:500]}")
            
            return t
        
        sql = _strip_sql_fences_local(sql_raw)
        logger.info("🔍 Generated SQL for approved tables (length: %d chars):\n%s", len(sql), sql)
        
        # Execute the query
        logger.info("🔍 Executing SQL query against database...")
        rows = []
        query_error = None
        
        # Validate SQL before execution
        if not sql or not sql.strip():
            query_error = "Generated SQL is empty after processing"
            logger.error(f"❌ {query_error}")
            logger.error(f"❌ Raw LLM output was: {sql_raw}")
        else:
            try:
                rows = await client.execute_query(sql)
                logger.info("✅ Query executed successfully: rows=%d", len(rows or []))
                if rows:
                    logger.info("📊 First row sample (first 5 columns): %s", {k: v for k, v in list(rows[0].items())[:5]} if rows[0] else "N/A")
                    logger.info("📊 Column names: %s", list(rows[0].keys()) if rows and rows[0] else "N/A")
                else:
                    logger.info("📊 Query returned no rows")
            except Exception as ex:
                query_error = str(ex)
                logger.error("❌ SQL execution failed: %s", query_error)
                logger.error("❌ Failed SQL query was:\n%s", sql)
        
        # Build result with comprehensive information
        result = {
            "rows": rows, 
            "sql": sql,  # Always include the SQL, even if execution failed
            "raw_sql": sql_raw,  # Include raw LLM output for debugging
            "filtering_info": {
                "approved_tables": approved_tables,
                "total_approved_tables": len(approved_schemas) if 'approved_schemas' in locals() else 0,
                "total_approved_columns": len(approved_columns) if 'approved_columns' in locals() else 0,
                "filtering_applied": True
            }
        }
        
        # Add error information if query failed
        if query_error:
            result["error"] = query_error
            result["execution_successful"] = False
            logger.info("❌ Returning result with execution error")
        else:
            result["execution_successful"] = True
            logger.info("✅ Returning successful result")
        
        logger.info("✅ Analytics query completed")
        logger.info(f"📊 Final result: {len(rows)} rows, SQL length: {len(sql)} chars, success: {not query_error}")
        logger.debug(f"📊 Full result keys: {list(result.keys())}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error in run_analytics_query_on_approved_tables: {e}", exc_info=True)
        
        # Try to include any SQL that was generated before the error
        error_sql = ""
        error_raw_sql = ""
        if 'sql' in locals():
            error_sql = sql
        if 'sql_raw' in locals():
            error_raw_sql = sql_raw
            
        error_result = {
            "error": str(e),
            "sql": error_sql,
            "raw_sql": error_raw_sql,
            "rows": [],
            "execution_successful": False,
            "filtering_info": {
                "approved_tables": approved_tables if 'approved_tables' in locals() else [],
                "total_approved_tables": 0,
                "total_approved_columns": 0,
                "filtering_applied": True
            }
        }
        logger.info("❌ Returning exception error result with available SQL: %s", {k: v for k, v in error_result.items() if k != 'raw_sql'})
        return error_result
    finally:
        try:
            await client.close()
            logger.info("✅ Database client closed for analytics query")
        except Exception as e:
            logger.error(f"❌ Error closing database client for analytics: {e}")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
