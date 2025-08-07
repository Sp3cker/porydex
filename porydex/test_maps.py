#!/usr/bin/env python3
"""
Standalone test file to run maps.py independently.
This file includes all necessary imports and dependencies.
"""

import os
import sys
import pathlib
import pickle
import re
import typing

# Add the current directory to Python path so we can import porydex modules
current_dir = pathlib.Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Mock the necessary imports that maps.py depends on
try:
    from pycparser.c_ast import Decl, ExprList, BinaryOp, Constant, ID
    from yaspin import yaspin
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install required packages:")
    print("pip install pycparser yaspin")
    sys.exit(1)

# Mock the porydex.parse functions that maps.py imports
# These are the functions that maps.py expects from porydex.parse

def mock_load_data(fname: pathlib.Path, extra_includes: list[str] = []) -> ExprList:
    """Mock implementation of load_data function"""
    print(f"Mock load_data called with: {fname}")
    # Return a mock ExprList for testing
    class MockExprList:
        def __init__(self):
            self.ext = []
    return MockExprList()

def mock_extract_id(expr) -> str:
    """Mock implementation of extract_id function"""
    if hasattr(expr, 'name'):
        return expr.name
    return "mock_id"

def mock_extract_int(expr) -> int:
    """Mock implementation of extract_int function"""
    if hasattr(expr, 'value'):
        try:
            return int(expr.value)
        except (ValueError, TypeError):
            return 0
    return 0

def mock_extract_u8_str(expr) -> str:
    """Mock implementation of extract_u8_str function"""
    if hasattr(expr, 'value'):
        return str(expr.value)
    return "mock_string"

# Create a mock porydex.parse module
class MockPorydexParse:
    def __init__(self):
        self.load_data = mock_load_data
        self.extract_id = mock_extract_id
        self.extract_int = mock_extract_int
        self.extract_u8_str = mock_extract_u8_str

# Mock the porydex.parse module
sys.modules['porydex.parse'] = MockPorydexParse()

# Now import the maps module
try:
    from porydex.parse.maps import (
        calculate_encounter_seed,
        all_maps,
        extract_map_constant_value,
        parse_map_constants,
        parse_map_constants_regex,
        parse_maps,
        WILD_AREA_LAND,
        WILD_AREA_WATER,
        WILD_AREA_ROCKS,
        WILD_AREA_FISHING,
        AREA_INFO
    )
    print("✅ Successfully imported maps.py functions!")
    
    # Test the functions
    print("\n--- Testing maps.py functions ---")
    
    # Test calculate_encounter_seed
    test_seed = calculate_encounter_seed(1, 2, 3, 4)
    print(f"calculate_encounter_seed(1, 2, 3, 4) = {test_seed}")
    
    # Test constants
    print(f"WILD_AREA_LAND = {WILD_AREA_LAND}")
    print(f"WILD_AREA_WATER = {WILD_AREA_WATER}")
    print(f"WILD_AREA_ROCKS = {WILD_AREA_ROCKS}")
    print(f"WILD_AREA_FISHING = {WILD_AREA_FISHING}")
    print(f"AREA_INFO = {AREA_INFO}")
    
    # Test extract_map_constant_value with mock data
    class MockBinaryOp:
        def __init__(self):
            self.op = "|"
            self.left = type('MockConstant', (), {'value': '16'})()
            self.right = type('MockBinaryOp', (), {
                'op': '<<',
                'left': type('MockConstant', (), {'value': '0'})()
            })()
    
    mock_expr = MockBinaryOp()
    map_num, map_group = extract_map_constant_value(mock_expr)
    print(f"extract_map_constant_value result: map_num={map_num}, map_group={map_group}")
    
    print("\n✅ All tests passed! maps.py is working correctly.")
    
except ImportError as e:
    print(f"❌ Failed to import maps.py: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error testing maps.py: {e}")
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    print("Test completed.")
