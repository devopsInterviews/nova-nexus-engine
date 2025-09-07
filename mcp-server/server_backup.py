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
async def list_database_tables(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str = "",
    database_type: str = "postgres"
) -> str:
    """
    List all user tables in the specified database, for Postgres or MSSQL.

    Returns:
      A JSON‐encoded array of table names, e.g. '["shops","items","sales"]'.

    Raises:
      ValueError: If `database_type` is unsupported.
      Otherwise, re-raises any DB client errors so you can see them.
    """
    logger.info(
        "list_database_tables called against %s:%s/%s as %s (%s)",
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
        logger.debug("Raw tables_list for %s: %r", database_type, tables_list)

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
        "list_database_keys called against %s:%s/%s as %s (%s)",
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
        logger.debug("Keys map: %s", keys_map)
        return keys_map
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

    Args:
      space (str):     Confluence space key (e.g., "PROJ").
      title (str):     Page title.
      columns (List[str]):
        List of column names (e.g. ["shops.id","shops.name", …]).

    Returns:
      str: JSON‐encoded list of column names that do NOT already appear
           as the first <td> in any row of the existing table, for example:
           '["sales.channel","sales.transaction_ref","sales.loyalty_points","sales.notes"]'.

    Raises:
      ValueError:      If the target table is not found.
    """
    page_id = await confluence.get_page_id(space, title)
    page = await confluence.get_page_content(page_id, expand="body.storage")
    html = page["body"]["storage"]["value"]

    soup = BeautifulSoup(html, "html.parser")
    tbl = soup.find("table", class_="relative-table")
    if not tbl:
        raise ValueError(f"relative-table not found on '{title}' in '{space}'")

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
    # 1) Fetch schema keys
    pg = PostgresClient(
        host=host, port=port,
        user=user, password=password,
        database=database,
        min_size=1, max_size=5
    )
    await pg.init()
    try:
        keys_map: Dict[str, List[str]] = await pg.list_keys()
        logger.debug("Keys map: %s", keys_map)
    finally:
        await pg.close()

    # 2) Prepare context for LLM
    context = json.dumps(keys_map, indent=2)

    # 3) Invoke LLM
    recommendation = await llm.call_remote_llm(
        context=context,
        prompt=user_prompt,
        system_prompt=system_prompt
    )

    logger.info("LLM recommendation: %s", recommendation)
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

    logger.info("run_analytics_query_on_database: start host=%s port=%s db=%s user=%s", host, port, database, user)

    # 1) schema
    pg = PostgresClient(host, port, user, password, database)
    await pg.init()
    try:
        schema = await pg.list_keys()
    except Exception as e:
        logger.exception("DB list_keys failed: %s", e)
        await pg.close()
        raise

    # 2) context (DB schema only; any Confluence desc was appended to analytics_prompt by the route)
    context = json.dumps(schema, indent=2)
    logger.debug("Context JSON length=%d", len(context))

    # 3) LLM
    sql_raw = await llm.call_remote_llm(
        context=context,
        prompt=analytics_prompt,
        system_prompt=system_prompt
    )
    logger.info("Generated SQL (raw) length=%d", len(sql_raw or 0))
    sql = _strip_sql_fences(sql_raw)
    logger.debug("Generated SQL (cleaned):\n%s", sql)

    # 4) Execute
    try:
        rows = await pg.execute_query(sql)
        logger.info("Query OK: rows=%d", len(rows or []))
        if rows:
            logger.debug("First row sample=%s", rows[0])
    finally:
        logger.debug("Closing DB pool …")
        await pg.close()

    return {"rows" : rows, "sql" : sql}


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
    Describe only the given `columns` of `table` for Postgres or MSSQL.

    1. Connects to the correct database type (PostgresClient or MSSQLClient).
    2. Samples up to `limit` values per column.
    3. Asks the LLM to produce a one-line description for each.

    Returns a JSON‐encoded array of:
      [{ "column": "table.col", "description": "...", "values": [...] }, …]

    Raises:
      ValueError: If `database_type` is unsupported.
    """
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
        results: List[Dict[str, Any]] = []
        for col in columns:
            try:
                vals = await client.get_column_values(table, col, limit)
                prompt = (
                    f"Describe the column {table}.{col}. "
                    f"Here are up to {limit} example values: {vals}. "
                    "Format each as: column – description – possible values/type"
                )
                desc = await llm.call_remote_llm(context="", prompt=prompt)
                results.append({
                    "column":      f"{table}.{col}",
                    "description": desc,
                    "values":      vals
                })
            except Exception as inner:
                logger.error(
                    "describe_columns error for %s.%s: %s",
                    table, col, inner, exc_info=True
                )
                results.append({
                    "column":      f"{table}.{col}",
                    "description": f"<error: {inner}>",
                    "values":      []
                })

        logger.debug("Raw describe_columns results for %s: %r", table, results)
        return json.dumps(results, default=str, separators=(",",":"))

    finally:
        await client.close()



if __name__ == "__main__":
    mcp.run(transport="streamable-http")
