"""
DBT Analysis Service - Client-side implementation for dbt file analysis
"""
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from ..llm_client import get_llm_client

logger = logging.getLogger(__name__)


async def analyze_dbt_file_for_iterative_query(
    dbt_file_data: Dict[str, Any],
    connection: Dict[str, Any],
    analytics_prompt: str,
    confluence_space: str,
    confluence_title: str,
    database_type: str = "postgres"
) -> Dict[str, Any]:
    """
    Analyze a dbt file and iteratively build SQL queries starting from the highest depth tables.
    
    This is the main orchestration function that:
    1. Parses the dbt file to extract tables/views by depth
    2. Starts with the highest depth tables
    3. Gets column metadata for current depth tables via MCP tools
    4. Asks AI if the available tables/columns are sufficient for the query
    5. If AI says "no", reduces depth by 1 and tries again
    6. If AI says "yes", generates and executes the full SQL query
    7. Continues until successful or reaches depth 0
    
    Args:
        dbt_file_data (Dict[str, Any]): Parsed dbt file content (not JSON string)
        connection (Dict[str, Any]): Database connection parameters
        analytics_prompt (str): The user's analytics question
        confluence_space (str): Confluence space for context
        confluence_title (str): Confluence page title for context
        database_type (str): Database type (default: postgres)
    
    Returns:
        Dict[str, Any]: Complete result including final SQL, data, and process log
    """
    logger.info("🚀 Starting client-side iterative dbt query analysis")
    logger.info(f"📊 Target database: {connection['host']}:{connection['port']}/{connection['database']}")
    logger.info(f"🎯 Analytics prompt: {analytics_prompt[:100]}...")
    logger.info(f"📋 Confluence context: {confluence_space}/{confluence_title}")
    
    try:
        # Import MCP client here to avoid circular imports
        from ..client import call_mcp_tool
        
        # Step 1: Dynamically analyze dbt structure and extract depth information
        logger.info("🔍 Step 1: Dynamically analyzing dbt structure for table depths")
        tables_by_depth, max_depth, dbt_context = await _analyze_dbt_structure_dynamic(dbt_file_data)
        
        if max_depth < 0:
            logger.error("❌ No valid table structure found in dbt file")
            return {
                "status": "error", 
                "error": "No valid table structure found in dbt file",
                "dbt_context": dbt_context
            }
        
        logger.info(f"📊 Found {sum(len(tables) for tables in tables_by_depth.values())} tables")
        logger.info(f"🏔️  Maximum depth detected: {max_depth}")
        logger.info(f"📋 dbt Context: {dbt_context['description']}")
        
        for depth in sorted(tables_by_depth.keys()):
            count = len(tables_by_depth[depth])
            logger.info(f"   Depth {depth}: {count} tables")
        
        # Step 2: Start iterative process from max depth
        current_depth = max_depth
        process_log = []
        
        while current_depth >= 0:
            logger.info(f"🔄 Step 2.{max_depth - current_depth + 1}: Trying depth {current_depth}")
            
            # Get tables from current depth only (not cumulative)
            current_tables = tables_by_depth.get(current_depth, [])
            
            if not current_tables:
                logger.info(f"⏭️  No tables at depth {current_depth}, moving to next depth")
                current_depth -= 1
                continue
            
            logger.info(f"📋 Using {len(current_tables)} tables at depth {current_depth}")
            logger.debug(f"🏷️  Tables in scope: {current_tables}")
            
            try:
                # Get column metadata for current tables via MCP
                logger.info("🔍 Getting column metadata for current table set")
                column_metadata_result = await call_mcp_tool(
                    "get_database_column_metadata",
                    host=str(connection['host']),
                    port=str(connection['port']),
                    user=str(connection['user']),
                    password=str(connection['password']),
                    database=str(connection['database']),
                    database_type=str(database_type)
                )
                
                if not column_metadata_result or "error" in column_metadata_result:
                    raise Exception(f"Failed to get column metadata: {column_metadata_result.get('error', 'Unknown error')}")
                
                # Parse the JSON result from MCP tool
                if isinstance(column_metadata_result.get("content"), list):
                    column_metadata_content = column_metadata_result["content"][0]
                else:
                    column_metadata_content = column_metadata_result.get("content", "{}")
                
                column_metadata = json.loads(column_metadata_content) if isinstance(column_metadata_content, str) else column_metadata_content
                
                # Filter metadata to only include our current tables
                filtered_metadata = {}
                for key, meta in column_metadata.items():
                    table_schema = meta.get("table_schema", "public")
                    table_name = meta.get("table_name")
                    
                    # Check if this table is in our current scope
                    if table_name in current_tables or f"{table_schema}.{table_name}" in current_tables:
                        filtered_metadata[key] = meta
                
                logger.info(f"📊 Found metadata for {len(filtered_metadata)} columns across {len(current_tables)} tables")
                
                # Ask AI if this table set is sufficient
                logger.info("🤖 Asking AI if current table set is sufficient")
                decision = await _ask_ai_sufficiency_decision(
                    tables=current_tables,
                    column_metadata=filtered_metadata,
                    analytics_prompt=analytics_prompt,
                    current_depth=current_depth,
                    max_depth=max_depth,
                    dbt_context=dbt_context
                )
                
                process_log.append({
                    "depth": current_depth,
                    "table_count": len(current_tables),
                    "column_count": len(filtered_metadata),
                    "ai_decision": decision["decision"],
                    "ai_reasoning": decision.get("reasoning", "")
                })
                
                if decision["decision"].lower().strip() == "yes":
                    logger.info(f"✅ AI says YES at depth {current_depth}! Proceeding with enhanced analysis")
                    
                    # Step A: Get filtered column keys for approved tables
                    logger.info("🔑 Step A: Getting filtered database keys for approved tables")
                    try:
                        approved_keys_result = await call_mcp_tool(
                            "list_database_keys_filtered_by_depth",
                            host=str(connection['host']),
                            port=str(connection['port']),
                            user=str(connection['user']),
                            password=str(connection['password']),
                            database=str(connection['database']),
                            approved_tables=json.dumps(current_tables),
                            database_type=str(database_type)
                        )
                        
                        if approved_keys_result and "error" not in approved_keys_result:
                            # Parse the JSON result from MCP tool
                            if isinstance(approved_keys_result.get("content"), list):
                                approved_keys_content = approved_keys_result["content"][0]
                            else:
                                approved_keys_content = approved_keys_result.get("content", "{}")
                            approved_keys = json.loads(approved_keys_content) if isinstance(approved_keys_content, str) else approved_keys_content
                        else:
                            approved_keys = {}
                        
                        logger.info(f"✅ Retrieved keys for {len(approved_keys)} approved tables")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to get filtered keys: {e}")
                        approved_keys = {}
                    
                    # Step B: Execute analytics query with approved tables only
                    logger.info("📊 Step B: Executing analytics query on approved tables")
                    try:
                        analytics_result_mcp = await call_mcp_tool(
                            "run_analytics_query_on_approved_tables",
                            host=str(connection['host']),
                            port=str(connection['port']),
                            user=str(connection['user']),
                            password=str(connection['password']),
                            database=str(connection['database']),
                            analytics_prompt=str(analytics_prompt),
                            approved_tables=json.dumps(current_tables),
                            database_type=str(database_type),
                            confluence_space=str(confluence_space),
                            confluence_title=str(confluence_title)
                        )
                        
                        if analytics_result_mcp and "error" not in analytics_result_mcp:
                            # Parse the JSON result from MCP tool
                            if isinstance(analytics_result_mcp.get("content"), list):
                                analytics_content = analytics_result_mcp["content"][0]
                            else:
                                analytics_content = analytics_result_mcp.get("content", "{}")
                            analytics_result = json.loads(analytics_content) if isinstance(analytics_content, str) else analytics_content
                        else:
                            analytics_result = {"error": analytics_result_mcp.get("error", "Unknown error")}
                        
                        logger.info("✅ Analytics query completed successfully")
                    except Exception as e:
                        logger.error(f"❌ Analytics query failed: {e}")
                        analytics_result = {"error": str(e)}
                    
                    # Return comprehensive results
                    return {
                        "status": "success",
                        "final_depth": current_depth,
                        "max_depth": max_depth,
                        "approved_tables": current_tables,
                        "column_count": len(filtered_metadata),
                        "process_log": process_log,
                        "approved_table_keys": approved_keys,
                        "analytics_result": analytics_result,
                        "sql_query": analytics_result.get("sql", ""),
                        "rows": analytics_result.get("rows", []),
                        "row_count": len(analytics_result.get("rows", [])),
                        "iteration_count": max_depth - current_depth + 1,
                        "dbt_context": dbt_context,
                        "filtering_applied": True
                    }
                
                else:
                    logger.warning(f"❌ AI says NO at depth {current_depth}: {decision.get('reasoning', 'No reason provided')}")
                    
                    if current_depth == 0:
                        logger.error("🚫 Reached depth 0 and AI still says NO - cannot proceed")
                        return {
                            "status": "insufficient_data",
                            "error": "AI could not generate query even with all available tables (depth 0)",
                            "final_depth": 0,
                            "max_depth": max_depth,
                            "process_log": process_log,
                            "dbt_context": dbt_context,
                            "filtering_applied": True
                        }
                    
                    # Reduce depth and try again
                    current_depth -= 1
                    logger.info(f"🔄 Reducing depth to {current_depth} and trying again")
                    
            except Exception as e:
                logger.error(f"❌ Error processing depth {current_depth}: {e}", exc_info=True)
                if current_depth == 0:
                    return {
                        "status": "error",
                        "error": f"Error at final depth 0: {e}",
                        "process_log": process_log,
                        "dbt_context": dbt_context
                    }
                current_depth -= 1
                continue
        
        # Should not reach here
        logger.error("🚫 Exhausted all depths without finding a solution")
        return {
            "status": "no_solution",
            "error": "No suitable table combination found at any depth",
            "process_log": process_log,
            "max_depth": max_depth,
            "dbt_context": dbt_context
        }
        
    except Exception as e:
        logger.error(f"❌ Fatal error in iterative analysis: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"Fatal error: {e}"
        }


async def _analyze_dbt_structure_dynamic(dbt_data: Dict[str, Any]) -> Tuple[Dict[int, List[str]], int, Dict[str, Any]]:
    """
    Dynamically analyze dbt file structure to extract tables by depth and determine context.
    
    Returns:
        - tables_by_depth: Dict mapping depth level to list of table names
        - max_depth: Maximum depth found in the structure  
        - dbt_context: Dictionary with file type, description, and metadata
    """
    tables_by_depth: Dict[int, List[str]] = {}
    max_depth = -1
    
    # Initialize context information
    dbt_context = {
        "type": "Unknown dbt file",
        "description": "dbt configuration",
        "total_tables": 0,
        "depth_distribution": {}
    }
    
    try:
        # Check if this is a manifest.json
        if "nodes" in dbt_data and "metadata" in dbt_data:
            logger.info("📋 Detected dbt manifest.json format")
            dbt_context["type"] = "dbt manifest.json"
            dbt_context["description"] = f"dbt manifest from project: {dbt_data.get('metadata', {}).get('project_name', 'unknown')}"
            
            nodes = dbt_data.get("nodes", {})
            
            # Extract table/view dependencies and build depth map
            node_depths = {}
            
            # First pass: collect all table/view nodes
            table_nodes = {}
            for node_id, node in nodes.items():
                if node.get("resource_type") in ["model", "view", "table"]:
                    table_name = node.get("name") or node_id.split(".")[-1]
                    table_nodes[node_id] = {
                        "name": table_name,
                        "depends_on": node.get("depends_on", {}).get("nodes", []),
                        "schema": node.get("schema", "public")
                    }
            
            # Second pass: calculate depths using dependency resolution
            def calculate_depth(node_id: str, visited: set) -> int:
                if node_id in visited:
                    return 0  # Circular dependency, treat as depth 0
                
                if node_id in node_depths:
                    return node_depths[node_id]
                
                if node_id not in table_nodes:
                    return 0  # External dependency, depth 0
                
                visited.add(node_id)
                
                dependencies = table_nodes[node_id]["depends_on"]
                if not dependencies:
                    depth = 0  # Base table
                else:
                    # Depth is 1 + max depth of dependencies
                    max_dep_depth = 0
                    for dep_id in dependencies:
                        dep_depth = calculate_depth(dep_id, visited.copy())
                        max_dep_depth = max(max_dep_depth, dep_depth)
                    depth = max_dep_depth + 1
                
                node_depths[node_id] = depth
                return depth
            
            # Calculate depths for all table nodes
            for node_id in table_nodes:
                depth = calculate_depth(node_id, set())
                table_name = table_nodes[node_id]["name"]
                
                if depth not in tables_by_depth:
                    tables_by_depth[depth] = []
                tables_by_depth[depth].append(table_name)
                max_depth = max(max_depth, depth)
            
            dbt_context["total_tables"] = len(table_nodes)
            
        # Check if this is a dbt_project.yml or profiles.yml
        elif "name" in dbt_data or "version" in dbt_data:
            logger.info("📋 Detected dbt project configuration format")
            dbt_context["type"] = "dbt project config"
            dbt_context["description"] = f"dbt project: {dbt_data.get('name', 'unnamed')}"
            
            # For project configs, we can't determine table depths
            # Return empty structure but valid context
            max_depth = -1
            
        # Check if this is a custom table structure
        elif "tables" in dbt_data or "models" in dbt_data:
            logger.info("📋 Detected custom dbt table structure")
            dbt_context["type"] = "custom table structure"
            
            # Handle various possible structures
            tables_source = dbt_data.get("tables", dbt_data.get("models", {}))
            
            if isinstance(tables_source, dict):
                # Structure like {"table1": {...}, "table2": {...}}
                for table_name, table_info in tables_source.items():
                    depth = 0  # Default depth
                    if isinstance(table_info, dict):
                        depth = table_info.get("depth", 0)
                    
                    if depth not in tables_by_depth:
                        tables_by_depth[depth] = []
                    tables_by_depth[depth].append(table_name)
                    max_depth = max(max_depth, depth)
            
            elif isinstance(tables_source, list):
                # Structure like [{"name": "table1", "depth": 0}, ...]
                for table_info in tables_source:
                    if isinstance(table_info, dict):
                        table_name = table_info.get("name", f"table_{len(tables_by_depth)}")
                        depth = table_info.get("depth", 0)
                    else:
                        table_name = str(table_info)
                        depth = 0
                    
                    if depth not in tables_by_depth:
                        tables_by_depth[depth] = []
                    tables_by_depth[depth].append(table_name)
                    max_depth = max(max_depth, depth)
            
            dbt_context["total_tables"] = sum(len(tables) for tables in tables_by_depth.values())
            
        else:
            logger.warning("⚠️ Unknown dbt file structure, attempting generic analysis")
            dbt_context["type"] = "unknown structure"
            dbt_context["description"] = "Unable to determine dbt file type"
            
            # Try to find any table-like structures
            def find_tables_recursive(obj, path="", depth=0):
                nonlocal max_depth
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{path}.{key}" if path else key
                        if key.lower() in ["tables", "models", "views"] and isinstance(value, (list, dict)):
                            # Found a table structure
                            if isinstance(value, dict):
                                for table_name in value.keys():
                                    if depth not in tables_by_depth:
                                        tables_by_depth[depth] = []
                                    tables_by_depth[depth].append(table_name)
                                    max_depth = max(max_depth, depth)
                            elif isinstance(value, list):
                                for item in value:
                                    table_name = item if isinstance(item, str) else str(item.get("name", item))
                                    if depth not in tables_by_depth:
                                        tables_by_depth[depth] = []
                                    tables_by_depth[depth].append(table_name)
                                    max_depth = max(max_depth, depth)
                        else:
                            find_tables_recursive(value, new_path, depth + 1)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        find_tables_recursive(item, f"{path}[{i}]", depth)
            
            find_tables_recursive(dbt_data)
            dbt_context["total_tables"] = sum(len(tables) for tables in tables_by_depth.values())
        
        # Update depth distribution in context
        dbt_context["depth_distribution"] = {
            str(depth): len(tables) for depth, tables in tables_by_depth.items()
        }
        
        logger.info(f"📊 Dynamic analysis complete:")
        logger.info(f"   Type: {dbt_context['type']}")
        logger.info(f"   Total tables: {dbt_context['total_tables']}")
        logger.info(f"   Max depth: {max_depth}")
        logger.info(f"   Depth distribution: {dbt_context['depth_distribution']}")
        
        return tables_by_depth, max_depth, dbt_context
        
    except Exception as e:
        logger.error(f"❌ Error in dynamic dbt structure analysis: {e}", exc_info=True)
        return {}, -1, {
            "type": "error",
            "description": f"Failed to analyze dbt structure: {e}",
            "total_tables": 0,
            "depth_distribution": {}
        }


async def _ask_ai_sufficiency_decision(
    tables: List[str],
    column_metadata: Dict[str, Any],
    analytics_prompt: str,
    current_depth: int,
    max_depth: int,
    dbt_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Ask the AI if the current set of tables and columns is sufficient to answer the analytics prompt.
    
    Returns:
        Dict with "decision" (yes/no) and "reasoning" keys
    """
    try:
        llm_client = get_llm_client()
        
        # Build a clear prompt for the AI
        table_info = f"Available tables (depth {current_depth}/{max_depth}): {', '.join(tables)}\n\n"
        
        column_info = "Available columns:\n"
        for key, meta in column_metadata.items():
            table_name = meta.get("table_name", "unknown")
            column_name = meta.get("column_name", "unknown")
            data_type = meta.get("data_type", "unknown")
            column_info += f"  {table_name}.{column_name} ({data_type})\n"
        
        context_info = f"\nDBT Context: {dbt_context.get('description', 'Unknown')}\n"
        
        decision_prompt = f"""
You are analyzing whether the available database tables and columns are sufficient to answer a specific analytics question.

{context_info}

ANALYTICS QUESTION:
{analytics_prompt}

{table_info}

{column_info}

TASK: Determine if these tables and columns contain enough information to generate a meaningful SQL query that answers the analytics question.

Consider:
1. Are the necessary data elements present?
2. Can relationships between tables be established?
3. Are there enough columns to perform the required analysis?
4. Would the resulting query be meaningful and complete?

Respond with exactly "YES" or "NO" followed by a brief explanation.

If YES: The available tables/columns are sufficient to answer the question.
If NO: More tables or deeper table relationships are needed.

Response format:
DECISION: [YES/NO]
REASONING: [Brief explanation of why this set is sufficient or insufficient]
"""
        
        response = await llm_client.get_completion(decision_prompt)
        
        # Parse the response
        lines = response.strip().split('\n')
        decision = "no"
        reasoning = "Could not parse AI response"
        
        for line in lines:
            if line.startswith("DECISION:"):
                decision_text = line.replace("DECISION:", "").strip()
                decision = "yes" if "yes" in decision_text.lower() else "no"
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
        
        logger.info(f"🤖 AI Decision: {decision.upper()} - {reasoning}")
        
        return {
            "decision": decision,
            "reasoning": reasoning
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting AI decision: {e}", exc_info=True)
        # Default to "no" on error to be safe
        return {
            "decision": "no",
            "reasoning": f"Error occurred during AI analysis: {e}"
        }
