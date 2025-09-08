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

    await client.init()
    try:
        keys_map = await client.list_keys()
        logger.info("📋 Retrieved column mappings for %d database objects (tables and views)", len(keys_map))
        logger.debug("Keys map: %s", keys_map)
        return keys_map
    finally:
        await client.close()

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
    logger.debug("📋 Requested columns: %s", columns[:10])  # Log first 10 columns
    
    # 1. Get database metadata for ALL columns (we'll filter later)
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
        # Get detailed column metadata with types
        column_metadata = await client.get_column_metadata()
        logger.info("📊 Got metadata for %d total columns from database", len(column_metadata))
        
    finally:
        await client.close()
    
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
        if not txt:
            return txt
        t = re.sub(r"</?code[^>]*>", "", txt, flags=re.I)
        m = re.search(r"```(?:sql)?\s*(.*?)```", t, flags=re.S | re.I)
        if m:
            t = m.group(1)
        t = t.replace("```", "").strip()
        t = re.sub(r"^\s*sql\s*[:\-]?\s*", "", t, flags=re.I)
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
    logger.info("Generated SQL (raw) length=%d", len(sql_raw or 0))
    sql = _strip_sql_fences(sql_raw)
    logger.info("🔍 Generated SQL (full query):\n%s", sql)

    # 4) Execute with proper error handling
    rows = []
    try:
        rows = await pg.execute_query(sql)
        logger.info("✅ Query executed successfully: rows=%d", len(rows or []))
        if rows:
            logger.debug("First row sample=%s", rows[0])
    except Exception as query_error:
        logger.error("❌ SQL execution failed: %s", str(query_error))
        logger.error("Failed SQL query was:\n%s", sql)
    finally:
        logger.debug("Closing DB pool …")
        await pg.close()

    return {"rows": rows, "sql": sql}


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



if __name__ == "__main__":
    mcp.run(transport="streamable-http")
