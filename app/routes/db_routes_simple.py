import logging
import json
import traceback
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
from app.models import User
from app.routes.auth_routes import get_current_user

# Create router with tags for API documentation
router = APIRouter(tags=["database"])
logger = logging.getLogger("uvicorn.error")

@router.get("/sync-all-tables-progress")
async def sync_all_tables_with_progress_stream(user: User = Depends(get_current_user)):
    """
    Simple sync function that iterates through all schemas and tables,
    formats everything as table.column for Confluence.
    """
    logger.info("sync_all_tables_with_progress_stream: starting sync for user %s", user.username)
    
    async def sync_generator():
        progress_data = {
            "stage": "initializing",
            "progress_percentage": 0,
            "stage_details": "Starting synchronization",
            "current_table": None,
            "current_table_index": 0,
            "tables_processed": [],
            "tables_pending": [],
            "summary": {"total_tables": 0, "successful_tables": 0, "failed_tables": 0, "new_columns_added": 0}
        }
        
        try:
            # Initialize MCP session
            progress_data.update({
                "stage": "connecting",
                "progress_percentage": 5,
                "stage_details": "Connecting to MCP server"
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            from app.client import get_mcp_session
            _mcp_session = await get_mcp_session()
            
            # Get all schemas
            schemas_result = await _mcp_session.call_tool("list_database_schemas", arguments={})
            schemas = schemas_result.content[0].text if schemas_result.content else "[]"
            schema_list = json.loads(schemas)
            logger.info("Found %d schemas: %s", len(schema_list), schema_list)
            
            # Collect all tables and columns from all schemas  
            all_tables = []
            all_columns = {}  # table_name -> [table.column, table.column, ...]
            
            for schema in schema_list:
                logger.info("Processing schema: %s", schema)
                
                # Get tables for this schema
                tables_result = await _mcp_session.call_tool("list_database_tables", arguments={"schema": schema})
                tables_json = tables_result.content[0].text if tables_result.content else "[]"
                schema_tables = json.loads(tables_json)
                logger.info("Schema %s has %d tables: %s", schema, len(schema_tables), schema_tables)
                
                # Get columns for this schema  
                keys_result = await _mcp_session.call_tool("list_database_keys", arguments={"schema": schema})
                keys_json = keys_result.content[0].text if keys_result.content else "{}"
                schema_keys = json.loads(keys_json)
                logger.info("Schema %s has keys for %d tables", schema, len(schema_keys))
                
                # Add tables and format columns as table.column
                for table in schema_tables:
                    if table not in all_tables:
                        all_tables.append(table)
                    if table in schema_keys:
                        # schema_keys[table] should already be in table.column format
                        all_columns[table] = schema_keys[table]
                        logger.info("Table %s has %d columns: %s", table, len(schema_keys[table]), schema_keys[table][:3])
            
            progress_data.update({
                "stage": "processing_tables", 
                "progress_percentage": 10,
                "stage_details": f"Found {len(all_tables)} tables across {len(schema_list)} schemas",
                "summary": {"total_tables": len(all_tables)}
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            # Process each table
            table_progress_increment = 80 / max(len(all_tables), 1)
            
            for table_index, table in enumerate(all_tables):
                current_progress = 10 + (table_index * table_progress_increment)
                logger.info("Processing table %d/%d: %s", table_index + 1, len(all_tables), table)
                
                progress_data.update({
                    "stage": "processing_table",
                    "current_table": table,
                    "current_table_index": table_index + 1,
                    "progress_percentage": int(current_progress),
                    "stage_details": f"Processing table '{table}' ({table_index + 1}/{len(all_tables)})",
                    "tables_pending": all_tables[table_index + 1:]
                })
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Get columns for this table (already in table.column format)
                table_columns = all_columns.get(table, [])
                if not table_columns:
                    logger.warning("No columns found for table %s", table)
                    result = {"table": table, "newColumns": [], "error": "no_columns", "stage": "completed"}
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["failed_tables"] += 1
                    continue

                # Check what's already in Confluence (existing columns in table.column format)
                existing_columns = []
                try:
                    from app.client import get_confluence_client
                    confluence_client = get_confluence_client()
                    page_content = confluence_client.get_page_content(table)
                    
                    # Extract existing columns from Confluence page
                    import re
                    # Look for table.column patterns in the content
                    column_pattern = rf"{re.escape(table)}\.\w+"
                    existing_columns = re.findall(column_pattern, page_content)
                    logger.info("Found %d existing columns in Confluence for %s", len(existing_columns), table)
                except Exception as e:
                    logger.info("No existing Confluence page for %s: %s", table, str(e))
                
                # Find missing columns (those not in Confluence)
                missing_columns = [col for col in table_columns if col not in existing_columns]
                logger.info("Found %d missing columns for table %s", len(missing_columns), table)
                
                if not missing_columns:
                    result = {"table": table, "newColumns": [], "status": "up_to_date", "stage": "completed"}
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["successful_tables"] += 1
                    continue
                
                # Generate descriptions for missing columns
                progress_data["stage_details"] = f"Generating descriptions for {len(missing_columns)} missing columns in '{table}'"
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                try:
                    # Extract just column names from table.column format
                    column_names = [col.split(".")[-1] for col in missing_columns]
                    
                    desc_res = await _mcp_session.call_tool(
                        "describe_columns",
                        arguments={
                            "table": table,
                            "columns": column_names
                        }
                    )
                    descriptions_text = desc_res.content[0].text if desc_res.content else "{}"
                    descriptions = json.loads(descriptions_text)
                    
                    # Update Confluence with missing columns
                    new_columns = []
                    for col in missing_columns:
                        col_name = col.split(".")[-1]  # Extract column name
                        description = descriptions.get(col_name, "No description available")
                        new_columns.append({"name": col, "description": description})
                    
                    result = {"table": table, "newColumns": new_columns, "stage": "completed"}
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["successful_tables"] += 1
                    progress_data["summary"]["new_columns_added"] += len(new_columns)
                    
                except Exception as e:
                    logger.error("Error describing columns for %s: %s", table, str(e))
                    result = {"table": table, "newColumns": [], "error": str(e), "stage": "completed"}
                    progress_data["tables_processed"].append(result)
                    progress_data["summary"]["failed_tables"] += 1

            # Final summary
            progress_data.update({
                "stage": "completed",
                "progress_percentage": 100,
                "stage_details": f"Sync completed. Processed {len(all_tables)} tables.",
                "current_table": None,
                "tables_pending": []
            })
            yield f"data: {json.dumps(progress_data)}\n\n"
            
        except Exception as e:
            logger.error("Error during sync: %s", str(e))
            logger.error("Traceback: %s", traceback.format_exc())
            progress_data.update({
                "stage": "error",
                "progress_percentage": 100,
                "stage_details": f"Error during sync: {str(e)}",
                "error": str(e)
            })
            yield f"data: {json.dumps(progress_data)}\n\n"

    return StreamingResponse(
        sync_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
