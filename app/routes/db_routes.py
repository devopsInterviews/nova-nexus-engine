import os
import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Router used by app.client to mount under /api
router = APIRouter()


# --- simple JSON persistence for saved connections ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CONNECTIONS_PATH = os.path.join(DATA_DIR, "connections.json")


def _read_connections() -> List[dict]:
    if not os.path.exists(CONNECTIONS_PATH):
        return []
    try:
        with open(CONNECTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _write_connections(conns: List[dict]) -> None:
    with open(CONNECTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(conns, f, ensure_ascii=False, indent=2)


class DbConnection(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str
    database_type: str = Field(..., description="postgres|mssql|mysql etc")
    name: Optional[str] = None
    id: Optional[str] = None


@router.get("/health")
async def api_health():
    return {"status": "ok", "service": "mcp-client"}


@router.post("/test-connection")
async def test_connection(conn: DbConnection):
    """
    Attempts to call the MCP tool `list_database_tables` with the provided
    credentials. If it returns successfully, we consider the connection valid.
    """
    # defer import to avoid circular import issues at module load time
    from app import client as client_module

    mcp_session = getattr(client_module, "_mcp_session", None)
    if mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session not ready")

    try:
        res = await mcp_session.call_tool(
            "list_database_tables",
            arguments={
                "host": conn.host,
                "port": conn.port,
                "user": conn.user,
                "password": conn.password,
                "database": conn.database,
                "database_type": conn.database_type,
            }
        )
        # Any non-exception response is considered a success
        # Optionally parse to ensure it's JSON / list
        _ = res.content[0].text
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {e}"}


@router.post("/save-connection")
async def save_connection(conn: DbConnection):
    """
    Saves a connection profile locally to data/connections.json.
    Returns a generated id.
    """
    import uuid

    conns = _read_connections()
    new_id = conn.id or str(uuid.uuid4())
    item = conn.dict()
    item["id"] = new_id

    # Upsert by id if provided
    updated = False
    for i, c in enumerate(conns):
        if c.get("id") == new_id:
            conns[i] = item
            updated = True
            break
    if not updated:
        conns.append(item)

    _write_connections(conns)
    return {"id": new_id}


@router.get("/get-connections")
async def get_connections():
    """Returns the list of saved connection profiles."""
    return _read_connections()


@router.post("/list-tables")
async def list_tables(conn: DbConnection):
    """Lists database tables via MCP `list_database_tables`."""
    from app import client as client_module

    mcp_session = getattr(client_module, "_mcp_session", None)
    if mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session not ready")

    try:
        res = await mcp_session.call_tool(
            "list_database_tables",
            arguments={
                "host": conn.host,
                "port": conn.port,
                "user": conn.user,
                "password": conn.password,
                "database": conn.database,
                "database_type": conn.database_type,
            }
        )
        text = res.content[0].text if res.content else "[]"
        try:
            data = json.loads(text)
            if isinstance(data, list):
                tables = data
            else:
                tables = [str(data)]
        except Exception:
            # fallback: split by newlines
            tables = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/list-tables")
async def list_tables(conn: DbConnection):
    """Return the list of tables for the provided connection as JSON."""
    from app import client as client_module

    mcp_session = getattr(client_module, "_mcp_session", None)
    if mcp_session is None:
        raise HTTPException(status_code=503, detail="MCP session not ready")

    try:
        res = await mcp_session.call_tool(
            "list_database_tables",
            arguments={
                "host": conn.host,
                "port": conn.port,
                "user": conn.user,
                "password": conn.password,
                "database": conn.database,
                "database_type": conn.database_type,
            }
        )
        text = res.content[0].text
        try:
            tables = json.loads(text)
        except Exception:
            # fall back: try to split lines
            tables = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
