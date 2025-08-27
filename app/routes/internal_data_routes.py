import logging
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import get_db_session, User
from app.routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal-data"])

@router.get("/list-tables")
async def list_internal_tables(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Return list of tables from the internal application database (auth / metadata)."""
    try:
        inspector = inspect(db.bind)  # type: ignore
        tables: List[str] = inspector.get_table_names()
        return {"status":"success","data": tables}
    except Exception as e:
        logger.error(f"Internal list tables failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to list internal tables")

@router.get("/table/{table_name}")
async def get_internal_table_rows(
    table_name: str,
    limit: int = 100,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Return first N rows from a given internal DB table using raw SQL (safe limited select)."""
    if not table_name.isidentifier():  # simple safety check
        raise HTTPException(status_code=400, detail="Invalid table name")
    limit = max(1, min(limit, 500))
    try:
        # Use parameterized text for limit not directly supported; ensure sanitized integer above
        query = text(f'SELECT * FROM "{table_name}" LIMIT {limit}')
        result = db.execute(query)
        rows = [dict(r._mapping) for r in result]
        columns = list(rows[0].keys()) if rows else []
        return {"status":"success","data": {"columns": columns, "rows": rows, "total_rows": len(rows)}}
    except Exception as e:
        logger.error(f"Internal get rows failed for {table_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rows")
