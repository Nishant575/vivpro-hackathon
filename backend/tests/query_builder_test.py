# Test script
from services.query_builder import build_query
import json

# Test 1: Simple query
query = build_query({"phase": "PHASE3", "status": "RECRUITING"})
print("Test 1 - Phase + Status:")
print(json.dumps(query, indent=2))

# Test 2: Condition search
query = build_query({"condition": "Lung Cancer"})
print("\nTest 2 - Condition:")
print(json.dumps(query, indent=2))

# Test 3: Complex query
query = build_query({
    "condition": "Breast Cancer",
    "phase": "PHASE3",
    "status": "RECRUITING",
    "location": "Boston"
}, page=2, size=20)
print("\nTest 3 - Complex:")
print(json.dumps(query, indent=2))

# Test 4: Empty query
query = build_query({})
print("\nTest 4 - Empty:")
print(json.dumps(query, indent=2))
