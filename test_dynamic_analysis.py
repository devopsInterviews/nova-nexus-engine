#!/usr/bin/env python3
"""
Test script for the dynamic dbt analysis functionality.
This tests the core dynamic logic without requiring external dependencies.
"""

import json
import re
from typing import Dict, List, Any, Tuple


def _infer_table_depth_dynamic(table_name: str) -> int:
    """
    Dynamically infer table depth from naming patterns and conventions.
    
    Higher numbers = more detailed/specific tables
    Lower numbers = more aggregated/summary tables
    """
    table_lower = table_name.lower()
    
    # Fact tables and detailed transaction tables (highest depth)
    if any(keyword in table_lower for keyword in [
        'fact_', 'facts_', 'transaction', 'detail', 'raw_', 'staging_', 'stg_', 'src_'
    ]):
        return 4
    
    # Dimension tables and reference data
    elif any(keyword in table_lower for keyword in [
        'dim_', 'dimension', 'ref_', 'lookup', 'master', 'bridge_'
    ]):
        return 3
    
    # Aggregated/summary tables
    elif any(keyword in table_lower for keyword in [
        'agg_', 'summary', 'sum_', 'rollup', 'daily', 'monthly', 'weekly', 'mart_'
    ]):
        return 2
    
    # High-level summary/dashboard tables
    elif any(keyword in table_lower for keyword in [
        'dashboard', 'kpi', 'metric', 'report', 'executive', 'overview'
    ]):
        return 1
    
    # Default depth for unclassified tables (middle ground)
    else:
        return 2


def analyze_dbt_structure_dynamic(dbt_data: Dict[str, Any]) -> Tuple[Dict[int, List[str]], int, Dict[str, Any]]:
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
        # Case 1: Explicit depth structure (like stadium.json)
        if isinstance(dbt_data, dict) and any(key.startswith("depth") for key in dbt_data.keys()):
            print("🔍 Found explicit depth structure")
            
            for key, value in dbt_data.items():
                if key.startswith("depth") and isinstance(value, list):
                    try:
                        depth_num = int(re.search(r'\d+', key).group())
                        tables_by_depth[depth_num] = value
                        max_depth = max(max_depth, depth_num)
                    except (AttributeError, ValueError):
                        pass
            
            total_tables = sum(len(tables) for tables in tables_by_depth.values())
            dbt_context.update({
                "type": "depth-organized structure",
                "description": f"depth-organized structure with {total_tables} tables across {max_depth + 1} depth levels",
                "total_tables": total_tables
            })
        
        # Case 2: dbt relations structure (manifest-like)
        elif isinstance(dbt_data, dict) and "relations" in dbt_data:
            print("🔍 Found dbt relations structure")
            relations = dbt_data["relations"]
            
            for relation in relations:
                depth = relation.get("depth", 0)
                table_name = relation.get("identifier", relation.get("name", "unknown"))
                
                if depth not in tables_by_depth:
                    tables_by_depth[depth] = []
                tables_by_depth[depth].append(table_name)
                max_depth = max(max_depth, depth)
            
            total_tables = sum(len(tables) for tables in tables_by_depth.values())
            dbt_context.update({
                "type": "dbt relations",
                "description": f"dbt relations structure with {total_tables} relations across {max_depth + 1} depth levels",
                "total_tables": total_tables
            })
        
        # Case 3: dbt models file
        elif isinstance(dbt_data, dict) and ("models" in dbt_data or "model" in dbt_data):
            print("🔍 Found dbt models structure")
            models = dbt_data.get("models", dbt_data.get("model", {}))
            
            if isinstance(models, dict):
                tables_list = list(models.keys())
            else:
                tables_list = []
            
            # Infer depths from model names
            for table in tables_list:
                depth = _infer_table_depth_dynamic(str(table))
                if depth not in tables_by_depth:
                    tables_by_depth[depth] = []
                tables_by_depth[depth].append(table)
                max_depth = max(max_depth, depth)
            
            dbt_context.update({
                "type": "dbt models",
                "description": f"dbt models configuration with {len(tables_list)} models",
                "total_tables": len(tables_list)
            })
        
        # Case 4: Generic array or object
        else:
            print("🔍 Analyzing generic structure")
            tables_list = []
            
            if isinstance(dbt_data, list):
                # Array format
                for item in dbt_data:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("table_name") or item.get("table")
                        if name:
                            tables_list.append(name)
                    elif isinstance(item, str):
                        tables_list.append(item)
                
                dbt_context.update({
                    "type": "table list",
                    "description": f"table list with {len(tables_list)} entries"
                })
            
            elif isinstance(dbt_data, dict):
                # Generic object - look for table information
                for key, value in dbt_data.items():
                    if isinstance(value, list):
                        tables_list.extend([str(item) for item in value if isinstance(item, (str, int))])
                    elif isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, list):
                                tables_list.extend([str(item) for item in subvalue if isinstance(item, (str, int))])
                
                dbt_context.update({
                    "type": "generic structure",
                    "description": f"generic structure with {len(tables_list)} extracted table references"
                })
            
            # Infer depths for generic structures
            for table in tables_list:
                depth = _infer_table_depth_dynamic(str(table))
                if depth not in tables_by_depth:
                    tables_by_depth[depth] = []
                tables_by_depth[depth].append(table)
                max_depth = max(max_depth, depth)
            
            dbt_context["total_tables"] = len(tables_list)
        
        # Update final context
        dbt_context["depth_distribution"] = {f"depth_{k}": len(v) for k, v in tables_by_depth.items()}
        
        print(f"📊 Final analysis: {dbt_context['description']}")
        print(f"🎯 Depth distribution: {dbt_context['depth_distribution']}")
        
        return tables_by_depth, max_depth, dbt_context
        
    except Exception as e:
        print(f"❌ Error analyzing dbt structure: {e}")
        return {}, -1, dbt_context


def test_stadium_example():
    """Test with the stadium.json example structure"""
    print("\n🏟️  Testing with Stadium-like explicit depth structure:")
    
    stadium_data = {
        "depth0": ["dashboard_overview", "executive_summary"],
        "depth1": ["monthly_revenue", "kpi_summary"],
        "depth2": ["event_aggregates", "visitor_summary"],
        "depth3": ["dim_events", "ref_venues"],
        "depth4": ["fact_tickets", "staging_visitors"]
    }
    
    tables_by_depth, max_depth, context = analyze_dbt_structure_dynamic(stadium_data)
    
    print(f"✅ Detected max depth: {max_depth}")
    print(f"📋 Context: {context['description']}")
    assert max_depth == 4
    assert context['type'] == "depth-organized structure"
    assert context['total_tables'] == 10


def test_dbt_models():
    """Test with dbt models structure"""
    print("\n📊 Testing with dbt models structure:")
    
    dbt_models = {
        "models": {
            "fact_sales": {"materialization": "table"},
            "dim_customers": {"materialization": "table"},
            "agg_monthly_sales": {"materialization": "view"},
            "dashboard_revenue": {"materialization": "view"}
        }
    }
    
    tables_by_depth, max_depth, context = analyze_dbt_structure_dynamic(dbt_models)
    
    print(f"✅ Detected max depth: {max_depth}")
    print(f"📋 Context: {context['description']}")
    assert max_depth >= 0
    assert context['type'] == "dbt models"
    assert context['total_tables'] == 4


def test_generic_list():
    """Test with generic list structure"""
    print("\n📝 Testing with generic list structure:")
    
    generic_list = [
        "fact_transactions",
        "dim_products", 
        "summary_daily",
        "report_overview"
    ]
    
    tables_by_depth, max_depth, context = analyze_dbt_structure_dynamic(generic_list)
    
    print(f"✅ Detected max depth: {max_depth}")
    print(f"📋 Context: {context['description']}")
    assert max_depth >= 0
    assert context['type'] == "table list"
    assert context['total_tables'] == 4


def test_depth_inference():
    """Test the depth inference logic"""
    print("\n🧠 Testing depth inference logic:")
    
    test_cases = [
        ("fact_sales", 4),
        ("staging_customers", 4),
        ("dim_products", 3),
        ("ref_categories", 3),
        ("agg_monthly", 2),
        ("summary_daily", 2),
        ("dashboard_kpi", 1),
        ("report_executive", 1),
        ("unknown_table", 2)  # default
    ]
    
    for table_name, expected_depth in test_cases:
        actual_depth = _infer_table_depth_dynamic(table_name)
        print(f"  {table_name} -> depth {actual_depth} (expected {expected_depth})")
        assert actual_depth == expected_depth, f"Failed for {table_name}: got {actual_depth}, expected {expected_depth}"
    
    print("✅ All depth inference tests passed!")


if __name__ == "__main__":
    print("🚀 Testing Dynamic dbt Analysis Logic")
    print("=" * 50)
    
    try:
        test_depth_inference()
        test_stadium_example()
        test_dbt_models()
        test_generic_list()
        
        print("\n🎉 All tests passed! Dynamic analysis is working correctly.")
        print(f"✅ Stadium structure: Dynamic depth detection")
        print(f"✅ dbt models: Table name inference")
        print(f"✅ Generic lists: Flexible parsing")
        print(f"✅ Depth inference: Smart pattern matching")
        print("\n🎯 Ready for real-world dbt files with any structure!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
