# Create a simple test file called test_import.py
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    from porydex.parse.maps import parse_map_constants, parse_maps
    print("Import successful!")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()