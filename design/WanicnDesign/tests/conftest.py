import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
EXAMPLE = os.path.join(ROOT, "examples", "house_8x12.json")
