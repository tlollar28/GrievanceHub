from pathlib import Path

# Project root (GrievanceHub/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Runtime data
DATA_DIR = PROJECT_ROOT / "data"

PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indexes"
LOG_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backups"
REPORT_DIR = DATA_DIR / "reports"

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://grievancehub_user:grievancehub_password@localhost:5432/grievancehub",
)