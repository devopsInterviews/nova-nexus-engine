#!/usr/bin/env python3
"""
Simple test to debug the manifest preprocessing
"""
from app.services.dbt_manifest_service import detect_dbt_file_type, preprocess_dbt_manifest
from app.services.dbt_analysis_service import process_dbt_file_for_ui

# Create test data with proper structure
manifest_data = {
    "metadata": {"dbt_version": "1.5.0", "project_name": "test_project"},
    "nodes": {
        "model.test.final_report": {
            "resource_type": "model",
            "name": "final_report",
            "database": "analytics",
            "schema": "public",
            "depends_on": {"nodes": ["model.test.customers"]}
        },
        "model.test.customers": {
            "resource_type": "model",
            "name": "customers",
            "database": "analytics",
            "schema": "public",
            "depends_on": {"nodes": ["source.test.raw_customers"]}
        }
    },
    "sources": {
        "source.test.raw_customers": {
            "resource_type": "source",
            "name": "raw_customers",
            "database": "raw",
            "schema": "public"
        }
    }
}

print("🧪 Testing with proper manifest structure")
print(f"Nodes: {list(manifest_data['nodes'].keys())}")
print(f"Sources: {list(manifest_data['sources'].keys())}")

# Test file type detection
file_type = detect_dbt_file_type(manifest_data)
print(f"Detected type: {file_type}")

# Test preprocessing
result = preprocess_dbt_manifest(manifest_data, include_sources=True)
print(f"Result keys: {list(result.keys())}")
print(f"Relations count: {len(result['relations'])}")
print(f"Max depth: {result['metadata']['max_depth']}")

print("\nRelations:")
for i, rel in enumerate(result["relations"]):
    print(f"  {i+1}. {rel['identifier']} (depth: {rel['depth']}, type: {rel['kind']})")

# Test UI processing
ui_result = process_dbt_file_for_ui(manifest_data)
print(f"\nUI processing:")
print(f"  File type: {ui_result['file_type']}")
print(f"  Total relations: {ui_result['metadata']['total_relations']}")
print(f"  Conversion: {ui_result['metadata']['conversion']}")
