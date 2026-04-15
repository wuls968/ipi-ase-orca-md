from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
root = str(PROJECT_ROOT)
if root not in sys.path:
    sys.path.insert(0, root)
