"""
DBT Analysis Service - Client-side implementation for dbt file analysis
"""
import json
import logging
from typing import Dict, Any, List, Tuple, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================================
# DBT MANIFEST PREPROCESSING FUNCTIONS
# ============================================================================

def detect_dbt_file_type(dbt_file_data: Dict[str, Any]) -> str:
    """
    Detect the type of dbt file uploaded.
    
    Args:
        dbt_file_data: The parsed JSON data from the uploaded file
        
    Returns:
        str: 'manifest', 'tree', or 'unknown'
    """
    if not isinstance(dbt_file_data, dict):
        return "unknown"
    
    # Check for manifest.json format (has metadata and nodes)
    if "metadata" in dbt_file_data and "nodes" in dbt_file_data:
        return "manifest"
    
    # Check for tree format (has relations array) - tree object is optional
    if "relations" in dbt_file_data and isinstance(dbt_file_data["relations"], list):
        # Validate that relations have the expected structure
        relations = dbt_file_data["relations"]
        if len(relations) > 0:
            # Check if relations have expected fields like depth, unique_id, etc.
            sample_relation = relations[0]
            if isinstance(sample_relation, dict) and ("depth" in sample_relation or "unique_id" in sample_relation):
                return "tree"
    
    return "unknown"


def preprocess_dbt_manifest(manifest_data: Dict[str, Any], include_sources: bool = True) -> Dict[str, Any]:
    """
    Convert a raw dbt manifest.json file to tree format for analysis.
    
    This function:
    1. Extracts nodes and sources from the manifest
    2. Builds a dependency graph
    3. Calculates depth levels for each relation
    4. Returns data in tree format compatible with existing analysis code
    
    Args:
        manifest_data: Raw dbt manifest.json content
        include_sources: Whether to include source tables in the output
        
    Returns:
        Dict containing relations list, tree structure, and metadata
    """
    logger.info("🔄 Converting dbt manifest.json to tree format")
    
    try:
        # Extract nodes and sources
        nodes = manifest_data.get("nodes", {})
        sources = manifest_data.get("sources", {}) if include_sources else {}
        
        logger.info(f"📊 Found {len(nodes)} nodes and {len(sources)} sources")
        
        # Build dependency graph
        dependency_graph = _build_dependency_graph(nodes, sources)
        
        # Calculate depths for all relations
        depths = _calculate_depths(dependency_graph)
        
        # Build the relations list
        relations = _build_relations_list(nodes, sources, depths, dependency_graph)
        
        # Build tree structure for compatibility
        tree = _build_tree_structure(relations)
        
        result = {
            "relations": relations,
            "tree": tree,
            "metadata": {
                "generated_from": "dbt_manifest",
                "project_name": manifest_data["metadata"].get("project_name"),
                "total_relations": len(relations),
                "max_depth": max(depths.values()) if depths else 0,
                "include_sources": include_sources
            }
        }
        
        logger.info(f"✅ Preprocessing complete: {len(relations)} relations, max depth: {result['metadata']['max_depth']}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error preprocessing manifest: {e}")
        raise


def _build_dependency_graph(nodes: Dict[str, Any], sources: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Build dependency graph from nodes and sources."""
    graph = defaultdict(set)
    
    # Process nodes (models, seeds, snapshots)
    for node_id, node in nodes.items():
        if _is_physical_node(node):
            depends_on = node.get("depends_on", {}).get("nodes", [])
            for dep in depends_on:
                if dep in nodes and _is_physical_node(nodes[dep]):
                    graph[node_id].add(dep)
                elif dep in sources:
                    graph[node_id].add(dep)
    
    # Process sources
    for source_id in sources:
        if source_id not in graph:
            graph[source_id] = set()  # Sources have no dependencies
    
    return graph


def _calculate_depths(dependency_graph: Dict[str, Set[str]]) -> Dict[str, int]:
    """Calculate depth for each node using topological sort."""
    depths = {}
    
    # Find all nodes with no dependencies (depth 0)
    for node_id, deps in dependency_graph.items():
        if not deps:
            depths[node_id] = 0
    
    # Calculate depths iteratively
    changed = True
    while changed:
        changed = False
        for node_id, deps in dependency_graph.items():
            if node_id in depths:
                continue
                
            # Check if all dependencies have been processed
            deps_depths = []
            for dep in deps:
                if dep in depths:
                    deps_depths.append(depths[dep])
                else:
                    break
            
            # If all dependencies processed, calculate this node's depth
            if len(deps_depths) == len(deps):
                depths[node_id] = max(deps_depths) + 1 if deps_depths else 0
                changed = True
    
    return depths


def _build_tree_structure(relations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build tree structure from relations for compatibility with existing analysis code."""
    tree = {}
    
    for relation in relations:
        table_name = relation["identifier"] or "unknown"
        tree[table_name] = {
            "depth": relation["depth"],
            "upstream": relation.get("upstream_uids", []),
            "metadata": {
                "unique_id": relation["unique_id"],
                "kind": relation["kind"],
                "database": relation["database"],
                "schema": relation["schema"]
            }
        }
    
    return tree


def _build_relations_list(
    nodes: Dict[str, Any], 
    sources: Dict[str, Any], 
    depths: Dict[str, int],
    dependency_graph: Dict[str, Set[str]]
) -> List[Dict[str, Any]]:
    """Build the relations list in the target format."""
    relations = []
    
    # Process nodes
    for node_id, node in nodes.items():
        if _is_physical_node(node):
            relation = {
                "unique_id": _get_table_identifier(node),
                "database": node.get("database", ""),
                "schema": node.get("schema", ""),
                "identifier": node.get("name", ""),
                "kind": node.get("resource_type", ""),
                "materialization": _get_materialization(node),
                "depth": depths.get(node_id, 0),
                "upstream_uids": [
                    _get_node_table_identifier(dep, nodes, sources) 
                    for dep in dependency_graph.get(node_id, set())
                ]
            }
            relations.append(relation)
    
    # Process sources  
    for source_id, source in sources.items():
        relation = {
            "unique_id": _get_source_identifier(source),
            "database": source.get("database", ""),
            "schema": source.get("schema", ""),
            "identifier": source.get("name", ""),
            "kind": "source",
            "materialization": None,
            "depth": depths.get(source_id, 0),
            "upstream_uids": []
        }
        relations.append(relation)
    
    # Sort by depth, then by identifier
    relations.sort(key=lambda r: (r["depth"], r["identifier"]))
    
    return relations


def _is_physical_node(node: Dict[str, Any]) -> bool:
    """Check if node is a physical node (model, seed, snapshot) and not ephemeral/disabled."""
    if not node:
        return False
        
    resource_type = node.get("resource_type", "")
    config = node.get("config", {})
    
    # Must be a physical resource type
    if resource_type not in ["model", "seed", "snapshot"]:
        return False
    
    # Must not be ephemeral
    if config.get("materialized") == "ephemeral":
        return False
    
    # Must not be disabled
    if config.get("enabled") is False:
        return False
    
    return True


def _get_table_identifier(node: Dict[str, Any]) -> str:
    """Get table identifier for a node."""
    database = node.get("database", "")
    schema = node.get("schema", "")
    name = node.get("name", "")
    return f"{database}.{schema}.{name}" if database and schema else name


def _get_source_identifier(source: Dict[str, Any]) -> str:
    """Get identifier for a source."""
    database = source.get("database", "")
    schema = source.get("schema", "")
    name = source.get("name", "")
    return f"{database}.{schema}.{name}" if database and schema else name


def _get_materialization(node: Dict[str, Any]) -> Optional[str]:
    """Get materialization type for a node."""
    return node.get("config", {}).get("materialized")


def _get_node_table_identifier(node_id: str, nodes: Dict[str, Any], sources: Dict[str, Any]) -> str:
    """Get table identifier for a node or source by ID."""
    if node_id in nodes:
        return _get_table_identifier(nodes[node_id])
    elif node_id in sources:
        return _get_source_identifier(sources[node_id])
    else:
        return node_id


# ============================================================================
# EXISTING DBT ANALYSIS FUNCTIONS
# ============================================================================


def process_dbt_file_for_ui(dbt_file_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process dbt file for UI display, handling both manifest.json and tree format.
    
    This function detects the file type and preprocesses it if needed:
    - If raw manifest.json: converts to tree format with depth calculation
    - If already tree format: ensures proper structure and uses as-is
    
    Args:
        dbt_file_data: The raw dbt file data (dict format)
        
    Returns:
        Dict containing:
        - processed_data: The data in tree format ready for analysis
        - file_type: 'manifest' or 'tree'
        - metadata: Processing information including conversion status
    """
    logger.info("📋 Processing dbt file for UI display")
    
    try:
        # Detect file type
        file_type = detect_dbt_file_type(dbt_file_data)
        logger.info(f"🔍 Detected file type: {file_type}")
        
        if file_type == "manifest":
            # Convert manifest to tree format
            logger.info("🔄 Converting manifest.json to tree format")
            processed_data = preprocess_dbt_manifest(dbt_file_data)
            conversion_status = "converted_from_manifest"
        elif file_type == "tree":
            # Already in tree format, but ensure it has tree structure
            logger.info("✅ File already in tree format, ensuring proper structure")
            processed_data = dbt_file_data.copy()
            
            # If no tree structure exists, build it from relations
            if "tree" not in processed_data and "relations" in processed_data:
                logger.info("🔧 Building tree structure from relations")
                relations = processed_data["relations"]
                tree = {}
                for relation in relations:
                    identifier = relation.get("identifier", relation.get("name", "unknown"))
                    tree[identifier] = {
                        "depth": relation.get("depth", 0),
                        "upstream": relation.get("upstream_uids", []),
                        "metadata": {
                            "unique_id": relation.get("unique_id", ""),
                            "kind": relation.get("kind", ""),
                            "database": relation.get("database", ""),
                            "schema": relation.get("schema", "")
                        }
                    }
                processed_data["tree"] = tree
            
            conversion_status = "no_conversion_needed"
        else:
            # Unknown format
            logger.error(f"❌ Unknown file format: {file_type}")
            processed_data = {}
            conversion_status = "failed_unknown_format"
        
        return {
            "processed_data": processed_data,
            "file_type": file_type,
            "metadata": {
                "conversion": conversion_status,
                "original_format": file_type,
                "total_relations": len(processed_data.get("relations", [])),
                "has_tree_structure": "tree" in processed_data
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing dbt file for UI: {str(e)}")
        return {
            "processed_data": {},
            "file_type": "unknown",
            "metadata": {
                "conversion": "failed",
                "error": str(e)
            }
        }


async def _extract_tables_from_tree_format(processed_data: Dict[str, Any]) -> Tuple[Dict[int, List[str]], int, Dict[str, Any]]:
    """
    Extract tables by depth from tree format processed data.
    
    Args:
        processed_data: Processed dbt data in tree format
        
    Returns:
        Tuple of (tables_by_depth, max_depth, dbt_context)
    """
    logger.info("🌳 Extracting tables from tree format data")
    
    tables_by_depth = {}
    max_depth = -1
    dbt_context = {
        "total_tables": 0,
        "structure_type": "tree_format",
        "depth_analysis": {},
        "type": "tree format",
        "description": "Pre-processed dbt tree structure"
    }
    
    try:
        # Get the relations list from processed data
        if "relations" not in processed_data:
            logger.error("❌ Missing 'relations' in processed data")
            return tables_by_depth, max_depth, dbt_context
        
        relations = processed_data["relations"]
        
        # Tree structure is optional - if it doesn't exist, we can still extract from relations
        tree = processed_data.get("tree", {})
        
        # Build tables_by_depth from relations list
        for relation in relations:
            if "depth" in relation:
                depth = relation["depth"]
                # Handle both 'name' (tree format) and 'identifier' (manifest format)
                table_name = relation.get("name") or relation.get("identifier") or "unknown"
                
                if depth not in tables_by_depth:
                    tables_by_depth[depth] = []
                
                tables_by_depth[depth].append(table_name)
                max_depth = max(max_depth, depth)
        
        # Update context
        dbt_context["total_tables"] = len(relations)
        dbt_context["max_depth"] = max_depth
        dbt_context["depth_analysis"] = {
            str(depth): len(tables) 
            for depth, tables in tables_by_depth.items()
        }
        
        logger.info(f"📊 Extracted {len(relations)} tables across {max_depth + 1} depth levels")
        for depth in sorted(tables_by_depth.keys(), reverse=True):
            logger.info(f"   Depth {depth}: {len(tables_by_depth[depth])} tables")
        
        return tables_by_depth, max_depth, dbt_context
        
    except Exception as e:
        logger.error(f"❌ Error extracting tables from tree format: {str(e)}")
        return {}, -1, {"error": str(e), "structure_type": "tree_format"}


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
    
    This function now handles both raw manifest.json and pre-processed tree format files:
    1. Detects and processes the file format if needed
    2. Extracts tables by depth from the processed data
    3. Starts with the highest depth tables and iterates down
    4. Gets column metadata for current depth tables via MCP tools
    5. Asks AI if the available tables/columns are sufficient for the query
    6. If AI says "no", reduces depth by 1 and tries again
    7. If AI says "yes", generates and executes the full SQL query
    8. Continues until successful or reaches depth 0
    
    Args:
        dbt_file_data (Dict[str, Any]): Raw dbt file data (manifest.json or tree format)
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
        from ..client import _mcp_session
        
        # Step 1: Process the dbt file (convert manifest to tree format if needed)
        logger.info("🔄 Step 1: Processing dbt file and detecting format")
        file_processing_result = process_dbt_file_for_ui(dbt_file_data)
        processed_data = file_processing_result["processed_data"]
        
        logger.info(f"� File type: {file_processing_result['file_type']}")
        logger.info(f"🔄 Preprocessing: {file_processing_result['metadata']['conversion']}")
        
        # Step 2: Extract tables by depth from processed data
        logger.info("🔍 Step 2: Extracting tables by depth from processed data")
        tables_by_depth, max_depth, dbt_context = await _extract_tables_from_tree_format(processed_data)
        
        if max_depth < 0:
            logger.error("❌ No valid table structure found in processed data")
            return {
                "status": "error", 
                "error": "No valid table structure found in processed data",
                "dbt_context": dbt_context,
                "file_processing": file_processing_result["metadata"]
            }
        
        logger.info(f"📊 Found {sum(len(tables) for tables in tables_by_depth.values())} tables")
        logger.info(f"🏔️  Maximum depth detected: {max_depth}")
        logger.info(f"📋 dbt Context: {dbt_context['description']}")
        
        for depth in sorted(tables_by_depth.keys()):
            count = len(tables_by_depth[depth])
            logger.info(f"   Depth {depth}: {count} tables")
        
        # Step 2: Get ALL database schema and enhanced metadata ONCE (before the iteration loop)
        logger.info("🔍 Getting complete database schema and enhanced metadata (one-time fetch)")
        logger.info(f"📊 Database connection: {connection['host']}:{connection['port']} as {connection['user']} to {connection['database']}")
        logger.info(f"📋 Confluence integration: space='{confluence_space}', title='{confluence_title}'")
        
        try:
            # First get all database columns that actually exist
            db_columns_args = {
                "host": connection['host'],
                "port": connection['port'],
                "user": connection['user'],
                "password": connection['password'],
                "database": connection['database'],
                "database_type": database_type
            }
            
            # Get all table->columns mapping from database
            logger.debug("Getting complete database schema...")
            db_schema_res = await _mcp_session.call_tool(
                "list_database_keys",
                arguments=db_columns_args
            )
            
            db_text_parts = [m.text for m in db_schema_res.content if getattr(m, "text", None)]
            db_text = db_text_parts[0] if db_text_parts else "{}"
            
            try:
                db_schema = json.loads(db_text)
                # Convert table->columns to flat list of table.column
                db_columns = []
                for table, columns in db_schema.items():
                    for column in columns:
                        db_columns.append(f"{table}.{column}")
                logger.info(f"✅ Found {len(db_columns)} total columns across {len(db_schema)} tables in database")
            except json.JSONDecodeError:
                logger.warning("Failed to parse database schema, using empty list")
                db_columns = []
                db_schema = {}
            
            # Now get enhanced schema with Confluence metadata for ALL columns
            if db_columns:
                logger.info(f"🔍 Getting enhanced schema for ALL {len(db_columns)} columns...")
                enhanced_args = {
                    "space": confluence_space,
                    "title": confluence_title,
                    "host": connection['host'],
                    "port": connection['port'],
                    "user": connection['user'],
                    "password": connection['password'],
                    "database": connection['database'],
                    "columns": db_columns,
                    "database_type": database_type
                }
                
                enhanced_schema_result = await _mcp_session.call_tool(
                    "get_enhanced_schema_with_confluence",
                    arguments=enhanced_args
                )
                
                # Parse enhanced schema response
                enhanced_schema_text = enhanced_schema_result.content[0].text if enhanced_schema_result.content else "{}"
                
                if enhanced_schema_text.startswith("Error executing tool"):
                    logger.error(f"MCP tool error: {enhanced_schema_text}")
                    # Provide specific error messages
                    if "password authentication failed" in enhanced_schema_text:
                        raise Exception(f"Database authentication failed: Check username '{connection['user']}' and password for database '{connection['database']}' on {connection['host']}:{connection['port']}")
                    elif "connection refused" in enhanced_schema_text:
                        raise Exception(f"Database connection refused: Cannot connect to {connection['host']}:{connection['port']}. Check if the database server is running and accessible.")
                    elif "database" in enhanced_schema_text and "does not exist" in enhanced_schema_text:
                        raise Exception(f"Database '{connection['database']}' does not exist on server {connection['host']}:{connection['port']}")
                    else:
                        raise Exception(f"Database connection failed: {enhanced_schema_text}")
                
                try:
                    all_enhanced_schema = json.loads(enhanced_schema_text)
                    logger.info(f"✅ Successfully fetched enhanced schema with {len(all_enhanced_schema)} schema.table entries")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse enhanced schema JSON: {e}")
                    logger.error(f"Raw content: {enhanced_schema_text}")
                    raise Exception(f"Invalid response from database: Expected JSON but got: {enhanced_schema_text[:200]}...")
            else:
                logger.warning("No database columns found, using empty enhanced schema")
                all_enhanced_schema = {}
                
        except Exception as schema_error:
            logger.error(f"Failed to fetch database schema or enhanced metadata: {str(schema_error)}")
            raise Exception(f"Database schema fetch failed: {str(schema_error)}")
        
        # Step 3: Start iterative process from max depth (using pre-fetched metadata)
        current_depth = max_depth
        process_log = []
        
        while current_depth >= 0:
            logger.info(f"🔄 Step 3.{max_depth - current_depth + 1}: Trying depth {current_depth}")
            
            # Get tables from current depth only (not cumulative)
            current_tables = tables_by_depth.get(current_depth, [])
            
            if not current_tables:
                logger.info(f"⏭️  No tables at depth {current_depth}, moving to next depth")
                current_depth -= 1
                continue
            
            logger.info(f"📋 Using {len(current_tables)} tables at depth {current_depth}")
            logger.debug(f"🏷️  Tables in scope: {current_tables}")
            
            try:
                # Filter pre-fetched enhanced schema to only include current tables
                logger.info("🔍 Filtering pre-fetched metadata for current table set")
                
                # Convert enhanced schema format to the expected column metadata format
                # Enhanced schema format: {"schema.table": [{"name": "col", "description": "desc", "type": "type"}]}
                # Convert to: {"schema.table.column": {"table_schema": "schema", "table_name": "table", "column_name": "col", "description": "desc", "data_type": "type"}}
                filtered_metadata = {}
                for schema_table_key, columns in all_enhanced_schema.items():
                    # Parse schema.table format
                    if "." in schema_table_key:
                        table_schema, table_name = schema_table_key.split(".", 1)
                    else:
                        table_schema = "public"
                        table_name = schema_table_key
                    
                    # Check if this table is in our current scope
                    if table_name in current_tables or f"{table_schema}.{table_name}" in current_tables:
                        for col in columns:
                            col_name = col.get("name", "")
                            col_desc = col.get("description", "No description")
                            col_type = col.get("type", "UNKNOWN")
                            
                            # Create a key compatible with existing logic
                            metadata_key = f"{table_schema}.{table_name}.{col_name}"
                            filtered_metadata[metadata_key] = {
                                "table_schema": table_schema,
                                "table_name": table_name,
                                "column_name": col_name,
                                "description": col_desc,
                                "data_type": col_type
                            }
                
                logger.info(f"📊 Filtered metadata: {len(filtered_metadata)} columns across {len(current_tables)} tables")
                
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
                
                logger.info(f"🎯 AI Decision: {decision['decision']}")
                logger.info(f"💭 AI Reasoning: {decision.get('reasoning', 'No reasoning provided')}")
                
                if decision["decision"] == "sufficient":
                    logger.info(f"✅ AI says YES at depth {current_depth}! Proceeding with enhanced analysis")
                    
                    # Step A: Use filtered metadata (no need to call MCP again - we have all the data)
                    logger.info("🔑 Step A: Using pre-fetched metadata for approved tables")
                    
                    # Convert filtered_metadata to the format expected by the analytics step
                    approved_keys = {}
                    for metadata_key, metadata in filtered_metadata.items():
                        table_name = metadata["table_name"]
                        column_name = metadata["column_name"]
                        
                        if table_name not in approved_keys:
                            approved_keys[table_name] = []
                        approved_keys[table_name].append(column_name)
                    
                    logger.info(f"📊 Prepared keys for {len(approved_keys)} tables with {sum(len(cols) for cols in approved_keys.values())} total columns")
                    
                    # Step B: Execute analytics query with approved tables only
                    logger.info("📊 Step B: Executing analytics query on approved tables")
                    try:
                        analytics_result_mcp = await _mcp_session.call_tool(
                            "run_analytics_query_on_approved_tables",
                            arguments={
                                "host": connection['host'],
                                "port": connection['port'],
                                "user": connection['user'],
                                "password": connection['password'],
                                "database": connection['database'],
                                "analytics_prompt": analytics_prompt,
                                "approved_tables": json.dumps(current_tables),
                                "database_type": database_type,
                                "confluence_space": confluence_space,
                                "confluence_title": confluence_title
                            }
                        )
                        
                        # Check if the MCP tool call was successful
                        if analytics_result_mcp and hasattr(analytics_result_mcp, 'content') and analytics_result_mcp.content:
                            # Parse the JSON result from MCP tool
                            analytics_text = analytics_result_mcp.content[0].text
                            try:
                                analytics_result = json.loads(analytics_text)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse analytics result JSON: {e}")
                                analytics_result = {"error": f"JSON parse error: {e}"}
                        else:
                            analytics_result = {"error": "No content returned from MCP tool"}
                        
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
        # Import the global llm_client instance from app.client
        from ..client import llm_client
        
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
        
        response = await llm_client.query_llm(decision_prompt)
        
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
