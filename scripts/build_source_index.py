import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.source_parser import build_source_index

if __name__ == "__main__":
    build_source_index()