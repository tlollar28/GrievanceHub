from pathlib import Path

# Project root (GrievanceHub/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Runtime data
DATA_DIR = PROJECT_ROOT / "data"

INCOMING_DIR = DATA_DIR / "incoming"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indexes"
LOG_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backups"
REPORT_DIR = DATA_DIR / "reports"
REPORT_TEMPLATE_DIR = PROJECT_ROOT / "app" / "templates" / "reports"
REPORT_STATIC_DIR = PROJECT_ROOT / "app" / "static" / "reports"

# Grievance form templates (blank official assets — may be committed after review)
GRIEVANCE_TEMPLATE_DIR = DATA_DIR / "templates" / "grievance"

# Generated filled grievance forms — never commit; never write under GRIEVANCE_TEMPLATE_DIR
GENERATED_FORM_OUTPUT_DIR = DATA_DIR / "generated" / "forms"
CASE_FORM_OUTPUT_DIR = DATA_DIR / "case_forms"

FORBIDDEN_GENERATED_FORM_PATH_PREFIXES: tuple[Path, ...] = (
    GRIEVANCE_TEMPLATE_DIR,
    PROJECT_ROOT / "app" / "static",
    DATA_DIR / "templates",
)

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://grievancehub_user:grievancehub_password@localhost:5432/grievancehub",
)