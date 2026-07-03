from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse

import shutil
import traceback
from uuid import uuid4

from app.config import INCOMING_DIR, REPORT_DIR
from app.api.routes.sources import router as sources_router
from app.api.routes.cases import router as cases_router
from app.api.routes.exports import router as exports_router

from app.services.report_service import (
    create_cross_craft_report,
    generate_findings,
)

from parsers.runtime_parser import parse_runtime_report
from parsers.employee_assignment_parser import parse_employee_assignments

from dotenv import load_dotenv
import os
load_dotenv()


app = FastAPI(title="GrievanceHub")

app.include_router(sources_router)
app.include_router(cases_router)
app.include_router(exports_router)

INCOMING_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "GrievanceHub",
    }


@app.post("/upload-clock-rings")
async def upload_clock_rings(file: UploadFile = File(...)):
    file_id = str(uuid4())
    file_path = INCOMING_DIR / f"{file_id}_{file.filename}"

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Clock rings PDF uploaded successfully",
        "file_id": file_id,
        "filename": file.filename,
        "saved_path": str(file_path),
    }


@app.post("/upload-runtime-report")
async def upload_runtime_report(file: UploadFile = File(...)):
    file_id = str(uuid4())
    file_path = INCOMING_DIR / f"{file_id}_{file.filename}"

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Runtime report uploaded successfully",
        "file_id": file_id,
        "filename": file.filename,
        "saved_path": str(file_path),
    }


@app.post("/generate-report")
def generate_report():
    try:
        runtime_path = INCOMING_DIR / "temp save.pdf"
        clerk_path = INCOMING_DIR / "CLERK ALL.pdf"
        pse_path = INCOMING_DIR / "PSE ALL.pdf"
        mh_path = INCOMING_DIR / "MH ALL.pdf"

        runtime_sessions = parse_runtime_report(runtime_path)

        clerk_assignments = parse_employee_assignments(
            clerk_path,
            craft="clerk",
            employee_type="career_clerk",
            max_pages=10,
        )

        pse_assignments = parse_employee_assignments(
            pse_path,
            craft="clerk",
            employee_type="pse",
            max_pages=10,
        )

        mail_handler_assignments = parse_employee_assignments(
            mh_path,
            craft="mail_handler",
            employee_type="mail_handler",
            max_pages=10,
        )

        findings = generate_findings(
            runtime_sessions,
            clerk_assignments,
            pse_assignments,
            mail_handler_assignments,
        )

        report_path = REPORT_DIR / "cross_craft_report.xlsx"

        create_cross_craft_report(report_path, findings)

        return {
            "runtime_sessions": len(runtime_sessions),
            "findings": len(findings),
            "report_path": str(report_path),
        }

    except Exception:
        traceback.print_exc()
        raise


@app.get("/download-report")
def download_report():
    report_path = REPORT_DIR / "cross_craft_report.xlsx"

    return FileResponse(
        path=report_path,
        filename="cross_craft_report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/test-mail-handler-parser")
def test_mail_handler_parser():
    mh_path = INCOMING_DIR / "MH ALL.pdf"

    mail_handler_assignments = parse_employee_assignments(
        mh_path,
        craft="mail_handler",
        employee_type="mail_handler",
        max_pages=10,
    )

    return {
        "mail_handlers_found": len(mail_handler_assignments),
        "sample_mail_handlers": mail_handler_assignments[:5],
    }


    
    