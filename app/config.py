from pathlib import Path

# Project root (GrievanceHub/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Runtime data
DATA_DIR = PROJECT_ROOT / "data"

# Official source files for index rebuilds (CONTRACT / CIM / ELM PDFs and zips)
APP_SOURCES_DIR = PROJECT_ROOT / "app" / "sources"

PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "indexes"
LOG_DIR = DATA_DIR / "logs"
BACKUP_DIR = DATA_DIR / "backups"
REPORT_DIR = DATA_DIR / "reports"
REPORT_TEMPLATE_DIR = PROJECT_ROOT / "app" / "templates" / "reports"
REPORT_STATIC_DIR = PROJECT_ROOT / "app" / "static" / "reports"

# Blank grievance form templates (committed app assets — not runtime data/)
GRIEVANCE_TEMPLATE_DIR = PROJECT_ROOT / "app" / "assets" / "grievance_templates"

# Generated filled grievance forms — never commit; never write under GRIEVANCE_TEMPLATE_DIR
GENERATED_FORM_OUTPUT_DIR = DATA_DIR / "generated" / "forms"
CASE_FORM_OUTPUT_DIR = DATA_DIR / "case_forms"

# Case-owned assets (uploads, future reports/grievances/exports) — local storage only
CASE_ASSET_DIR = DATA_DIR / "case_assets"
CASE_ASSET_MAX_UPLOAD_BYTES = 25 * 1024 * 1024

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