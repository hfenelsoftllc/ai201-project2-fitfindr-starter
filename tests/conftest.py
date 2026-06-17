import sys
import os

# Ensure the project root is on the path so `tools` is importable when
# pytest is run from inside the tests/ directory or from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
