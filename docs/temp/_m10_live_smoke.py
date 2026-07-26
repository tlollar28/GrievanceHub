"""Disposable W6 Batch 4 / M10 realistic PDF live validation.

Synthetic cases only. This script intentionally leaves created records and their
referenced generated files in place because GrievanceHub has no established
case-deletion cleanup API.
"""

from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.database.models import (
    CaseAsset,
    CaseFormDraftRecord,
    CaseReportVersion,
    CaseSavedArtifact,
    GrievanceCase,
)
from app.database.session import SessionLocal
from app.main import app

BASE = "http://127.0.0.1:8000"
OUT = ROOT / "docs" / "temp" / "_m10_live_smoke_out.txt"
CASE_UUIDS = ROOT / "docs" / "temp" / "_m10_live_case_uuids.txt"


class Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self.streams = streams

    def write(self, text: str) -> int:
        for stream in self.streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, str, bytes, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={
            "Accept": "application/json, application/pdf",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            content_type = response.headers.get("content-type", "")
            parsed = (
                json.loads(raw.decode("utf-8"))
                if "application/json" in content_type
                else None
            )
            return response.status, content_type, raw, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        content_type = exc.headers.get("content-type", "")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            parsed = {"detail": raw.decode("utf-8", errors="replace")}
        return exc.code, content_type, raw, parsed


def post(path: str, body: dict[str, Any]) -> tuple[int, Any]:
    status, _content_type, _raw, parsed = request("POST", path, body)
    return status, parsed


def create_case(label: str, facts: dict[str, Any]) -> str:
    status, body = post(
        "/cases/",
        {
            "question": (
                f"W6 M10 synthetic {label}: Was management's July 2026 schedule "
                "change inconsistent with the applicable agreement?"
            ),
            "user_name": "W6 M10 Synthetic Steward",
            "local_number": "300",
            "known_facts": facts,
        },
    )
    assert status == 200, body
    case_uuid = (body.get("case") or {}).get("case_uuid") or body.get("case_uuid")
    assert case_uuid, body
    print(f"created_case label={label!r} case_uuid={case_uuid}")
    return str(case_uuid)


def db_snapshot(case_uuid: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        case = (
            db.query(GrievanceCase)
            .filter(GrievanceCase.case_uuid == case_uuid)
            .one()
        )
        artifacts = (
            db.query(CaseSavedArtifact)
            .filter(CaseSavedArtifact.case_uuid == case_uuid)
            .order_by(CaseSavedArtifact.id.asc())
            .all()
        )
        drafts = (
            db.query(CaseFormDraftRecord)
            .filter(CaseFormDraftRecord.case_uuid == case_uuid)
            .order_by(CaseFormDraftRecord.id.asc())
            .all()
        )
        assets = (
            db.query(CaseAsset)
            .filter(CaseAsset.case_uuid == case_uuid)
            .order_by(CaseAsset.id.asc())
            .all()
        )
        return {
            "case_id": case.id,
            "report_versions": (
                db.query(CaseReportVersion)
                .filter(CaseReportVersion.case_id == case.id)
                .count()
            ),
            "artifacts": [
                {
                    "uuid": row.artifact_uuid,
                    "type": row.artifact_type,
                    "status": row.status,
                    "pdf_status": row.pdf_status,
                    "printed": bool(row.printed),
                    "pdf_asset_uuid": row.pdf_asset_uuid,
                    "idempotency_key": row.idempotency_key,
                    "source_report_version_number": row.source_report_version_number,
                    "grievance_step": row.grievance_step,
                    "template_id": row.template_id,
                }
                for row in artifacts
            ],
            "drafts": [
                {
                    "uuid": row.draft_uuid,
                    "official": bool(row.is_official),
                    "export_status": row.export_status,
                    "pdf_asset_uuid": row.pdf_asset_uuid,
                    "template_id": row.template_id,
                    "idempotency_key": row.idempotency_key,
                }
                for row in drafts
            ],
            "assets": [
                {
                    "uuid": row.asset_uuid,
                    "category": row.asset_category,
                    "mime_type": row.mime_type,
                    "file_size": row.file_size,
                }
                for row in assets
            ],
        }
    finally:
        db.close()


def count_key(case_uuid: str, key: str) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.idempotency_key == key,
            )
            .count()
        )
    finally:
        db.close()


def pdf_details(case_uuid: str, artifact_uuid: str) -> dict[str, Any]:
    status, content_type, raw, _parsed = request(
        "GET", f"/cases/{case_uuid}/artifacts/{artifact_uuid}/pdf"
    )
    assert status == 200, status
    assert content_type.startswith("application/pdf"), content_type
    assert raw.startswith(b"%PDF") and len(raw) > 1_000
    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    fields = reader.get_fields() or {}
    return {
        "status": status,
        "content_type": content_type,
        "bytes": len(raw),
        "pages": len(reader.pages),
        "text": text,
        "fields": fields,
    }


def field_value(fields: dict[str, Any], name: str) -> str:
    value = (fields.get(name) or {}).get("/V", "")
    return str(value)


def advance(case_uuid: str, expected_step: str) -> dict[str, Any]:
    status, body = post(
        f"/cases/{case_uuid}/outcomes",
        {
            "outcome_type": "denied",
            "decision_summary": f"Synthetic denial advancing to {expected_step}.",
            "decision_date": "2026-07-25",
            "appeal_to_next_step": True,
            "close_step": True,
            "close_case": False,
        },
    )
    assert status == 200, body
    workflow = body.get("workflow") or {}
    assert expected_step in str(workflow.get("current_grievance_step")), workflow
    print(
        "advance",
        status,
        workflow.get("explicit_state"),
        workflow.get("current_grievance_step"),
    )
    return workflow


def validate_analysis(case_uuids: list[str]) -> None:
    print("\n=== 1. Analysis report ===")
    case_uuid = create_case(
        "analysis report",
        {
            "employee_name": "Morgan Synthetic",
            "grievant_name": "Morgan Synthetic",
            "grievant_name_or_class": "Synthetic Mail Handler Class",
            "facts_what_happened": (
                "Management changed a posted synthetic schedule on July 20, 2026 "
                "without the advance notice described in the synthetic scenario."
            ),
            "facts_datetime_location": "July 20, 2026, 08:00, Synthetic Plant",
            "violation_articles_citations": "Article 8 (synthetic allegation)",
            "corrective_action_requested": (
                "Restore the synthetic schedule and make the synthetic grievant whole."
            ),
        },
    )
    case_uuids.append(case_uuid)

    status, generated = post(f"/cases/{case_uuid}/reports/generate", {})
    assert status == 200, generated
    assert generated.get("status") == "completed", generated
    assert generated.get("persisted") is False
    preview = generated.get("preview")
    assert isinstance(preview, dict) and preview.get("report_data")
    before = db_snapshot(case_uuid)
    assert before["report_versions"] == 0
    assert before["artifacts"] == []

    key = "w6-m10-analysis-save-print"
    status, saved = post(
        f"/cases/{case_uuid}/reports/save-and-print",
        {
            "preview": preview,
            "title": "W6 M10 Synthetic Analysis Report",
            "saved_by": "W6 M10 Synthetic Steward",
            "grievance_step": "step_1_initial",
            "idempotency_key": key,
            "prepare_pdf": True,
        },
    )
    assert status == 200, saved
    assert saved["status"] == "saved", saved
    assert saved["print_ready"] is True
    artifact = saved["artifact"]
    assert artifact["pdf_status"] == "ready"
    assert artifact["printed"] is True
    artifact_uuid = artifact["artifact_uuid"]

    replay_status, replay = post(
        f"/cases/{case_uuid}/reports/save-and-print",
        {
            "preview": preview,
            "idempotency_key": key,
            "prepare_pdf": True,
        },
    )
    assert replay_status == 200, replay
    assert replay["status"] == "idempotent_replay"
    assert replay["artifact"]["artifact_uuid"] == artifact_uuid
    assert count_key(case_uuid, key) == 1

    snapshot = db_snapshot(case_uuid)
    assert snapshot["report_versions"] == 1
    matching = [a for a in snapshot["artifacts"] if a["uuid"] == artifact_uuid]
    assert len(matching) == 1
    assert matching[0]["status"] == "official"
    assert matching[0]["pdf_status"] == "ready"
    assert matching[0]["source_report_version_number"] == 1

    pdf = pdf_details(case_uuid, artifact_uuid)
    report_text = " ".join(pdf["text"].split())
    for representative in (
        "GrievanceHub Analysis Report",
        "Quick Assessment",
        "W6 M10 synthetic analysis report",
    ):
        assert representative.lower() in report_text.lower(), (
            representative,
            report_text[:800],
        )
    print(
        f"PASS status={status} replay_status={replay_status} "
        f"artifact_uuid={artifact_uuid} report_versions=1 key_count=1 "
        f"pdf_status=ready pdf_http={pdf['status']} pdf_bytes={pdf['bytes']} "
        f"pdf_pages={pdf['pages']}"
    )
    print(f"text_snippet={report_text[:260]!r}")


def generate_grievance(case_uuid: str) -> dict[str, Any]:
    status, body = post(
        f"/cases/{case_uuid}/actions",
        {"action": "generate_grievance", "interaction": None},
    )
    assert status == 200, body
    assert body.get("status") == "completed", body
    generation = body.get("grievance_generation") or {}
    assert generation.get("draft_created") is True
    assert generation.get("official_artifact_created") is False
    return body


def save_grievance(
    case_uuid: str,
    generation: dict[str, Any],
    *,
    step: str,
    key: str,
    protected_values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    draft = generation["grievance_generation"]
    fields = dict(draft.get("field_values") or {})
    fields.update(protected_values)
    payload = {
        "template_id": draft["template_id"],
        "template_version": "m10-live-1",
        "grievance_step": step,
        "field_values": fields,
        "steward_override_field_ids": sorted(protected_values),
        "missing_required_field_ids": [],
        "validation_status": "valid",
        "draft_status": "ready_for_steward_review",
        "content_snapshot": {
            "template_id": draft["template_id"],
            "template_version": "m10-live-1",
            "grievance_step": step,
            "field_values": fields,
            "validation_status": "valid",
            "synthetic": True,
        },
        "saved_by": "W6 M10 Synthetic Steward",
        "idempotency_key": key,
        "prepare_pdf": True,
    }
    status, saved = post(f"/cases/{case_uuid}/grievances/save-and-print", payload)
    assert status == 200, saved
    assert saved["status"] == "saved", saved
    assert saved["print_ready"] is True
    assert saved["artifact"]["pdf_status"] == "ready"
    replay_status, replay = post(
        f"/cases/{case_uuid}/grievances/save-and-print", payload
    )
    assert replay_status == 200, replay
    assert replay["status"] == "idempotent_replay"
    assert replay["artifact"]["artifact_uuid"] == saved["artifact"]["artifact_uuid"]
    assert count_key(case_uuid, key) == 1
    return saved, replay


def validate_step_1(case_uuids: list[str]) -> None:
    print("\n=== 2. Step 1 grievance ===")
    case_uuid = create_case(
        "Step 1 grievance",
        {
            "grievant_name": "Avery Synthetic",
            "grievant_name_or_class": "Avery Synthetic",
            "facts_what_happened": (
                "Management changed Avery Synthetic's posted schedule."
            ),
            "facts_datetime_location": "July 20, 2026, Synthetic Plant",
            "violation_articles_citations": "Article 8",
            "corrective_action_requested": "Restore the posted synthetic schedule.",
        },
    )
    case_uuids.append(case_uuid)
    generated = generate_grievance(case_uuid)
    draft = generated["grievance_generation"]
    assert draft["step_type"] == "step_1_initial"
    assert draft["template_id"] == "official_grievance_worksheet_step_1"

    key = "w6-m10-step1-save-print"
    saved, replay = save_grievance(
        case_uuid,
        generated,
        step="step_1_initial",
        key=key,
        protected_values={
            "form_date": "July 26, 2026",
            "branch_grievance_number": "M10-S1-001",
            "steward_name": "Taylor Synthetic Steward",
            "grievant_name_or_class": "Avery Synthetic",
            "facts_dates": "July 20, 2026",
            "facts_time": "08:00",
            "facts_location": "Synthetic Plant",
            "facts_what_happened": (
                "Management changed Avery Synthetic's posted schedule."
            ),
            "corrective_action_requested": "Restore the posted synthetic schedule.",
        },
    )
    artifact_uuid = saved["artifact"]["artifact_uuid"]
    snapshot = db_snapshot(case_uuid)
    assert len(snapshot["artifacts"]) == 1
    assert len(snapshot["drafts"]) == 1
    assert snapshot["drafts"][0]["official"] is True
    assert snapshot["drafts"][0]["export_status"] == "exported_pdf"

    pdf = pdf_details(case_uuid, artifact_uuid)
    assert field_value(pdf["fields"], "gff1.1") == "M10-S1-001"
    assert field_value(pdf["fields"], "gff2.0") == "Avery Synthetic"
    assert (
        field_value(pdf["fields"], "gff3.6")
        == "Management changed Avery Synthetic's posted schedule."
    )
    print(
        f"PASS status=200 replay={replay['status']} artifact_uuid={artifact_uuid} "
        f"official_drafts=1 key_count=1 pdf_status=ready "
        f"pdf_http={pdf['status']} pdf_bytes={pdf['bytes']} pdf_pages={pdf['pages']}"
    )
    print(
        "representative_fields="
        f"{[field_value(pdf['fields'], name) for name in ('gff1.1', 'gff2.0', 'gff3.6')]}"
    )


def validate_step_2(case_uuids: list[str]) -> None:
    print("\n=== 3. Step 2 grievance ===")
    case_uuid = create_case(
        "Step 2 grievance",
        {
            "grievant_name": "Jordan Synthetic",
            "grievant_name_or_class": "Jordan Synthetic",
            "facts_what_happened": "Management denied the synthetic Step 1 grievance.",
            "facts_datetime_location": "July 24, 2026, Synthetic Plant",
            "violation_articles_citations": "Articles 8 and 15",
            "corrective_action_requested": (
                "Rescind the synthetic schedule change and make whole."
            ),
        },
    )
    case_uuids.append(case_uuid)
    advance(case_uuid, "step_2")
    generated = generate_grievance(case_uuid)
    draft = generated["grievance_generation"]
    assert draft["step_type"] == "step_2_appeal"
    assert draft["template_id"] == "official_standard_grievance_form_step_2"

    key = "w6-m10-step2-save-print"
    saved, replay = save_grievance(
        case_uuid,
        generated,
        step="step_2_appeal",
        key=key,
        protected_values={
            "form_date": "07/26/2026",
            "local_branch_number": "300",
            "branch_grievance_number": "M10-S2-001",
            "usps_number": "SYN-USPS-001",
            "step2_designee_name_title": "Synthetic Manager, Title",
            "grievant_name_or_class": "Jordan Synthetic",
            "violation_articles_citations": "Articles 8 and 15",
            "facts_datetime_location": "07/24/2026 Synthetic Plant",
            "facts_what_happened": (
                "Management denied the synthetic Step 1 grievance."
            ),
            "corrective_action_requested": (
                "Rescind the synthetic schedule change and make whole."
            ),
        },
    )
    artifact_uuid = saved["artifact"]["artifact_uuid"]
    snapshot = db_snapshot(case_uuid)
    assert len(snapshot["artifacts"]) == 1
    assert len(snapshot["drafts"]) == 1
    assert snapshot["drafts"][0]["official"] is True

    pdf = pdf_details(case_uuid, artifact_uuid)
    assert field_value(pdf["fields"], "Local Grievance No") == "M10-S2-001"
    assert field_value(pdf["fields"], "Grievant Name") == "Jordan Synthetic"
    assert field_value(pdf["fields"], "Violations ART & SECT") == "Articles 8 and 15"
    print(
        f"PASS status=200 replay={replay['status']} artifact_uuid={artifact_uuid} "
        f"official_drafts=1 key_count=1 pdf_status=ready "
        f"pdf_http={pdf['status']} pdf_bytes={pdf['bytes']} pdf_pages={pdf['pages']}"
    )
    print(
        "representative_fields="
        f"{[field_value(pdf['fields'], name) for name in ('Local Grievance No', 'Grievant Name', 'Violations ART & SECT')]}"
    )


def validate_step_3(case_uuids: list[str]) -> None:
    print("\n=== 4. Step 3 boundary ===")
    case_uuid = create_case(
        "Step 3 boundary",
        {
            "grievant_name": "Riley Synthetic",
            "facts_what_happened": "Synthetic Step 2 appeal was denied.",
            "violation_articles_citations": "Articles 8 and 15",
            "corrective_action_requested": "Synthetic make-whole remedy.",
        },
    )
    case_uuids.append(case_uuid)
    advance(case_uuid, "step_2")
    workflow = advance(case_uuid, "step_3")
    generated = generate_grievance(case_uuid)
    draft = generated["grievance_generation"]
    assert "step_3" in str(draft["step_type"])
    assert draft["template_id"] == "step_3_template_deferred"
    disclosure_dump = json.dumps(generated).lower()
    assert "deferred" in disclosure_dump

    before = db_snapshot(case_uuid)
    assert before["artifacts"] == []
    assert before["drafts"] == []
    assert not [
        asset
        for asset in before["assets"]
        if asset["category"] == "generated_grievance"
    ]

    base_payload = {
        "template_version": "m10-live-1",
        "grievance_step": "step_3_appeal",
        "field_values": draft["field_values"],
        "validation_status": "valid",
        "missing_required_field_ids": [],
        "prepare_pdf": True,
    }
    status_deferred, rejected_deferred = post(
        f"/cases/{case_uuid}/grievances/save-and-print",
        {
            **base_payload,
            "template_id": "step_3_template_deferred",
            "idempotency_key": "w6-m10-step3-reject",
        },
    )
    assert status_deferred == 400, rejected_deferred
    status_unknown, rejected_unknown = post(
        f"/cases/{case_uuid}/grievances/save-and-print",
        {
            **base_payload,
            "template_id": "synthetic_unsupported_template",
            "idempotency_key": "w6-m10-unsupported-reject",
        },
    )
    assert status_unknown == 400, rejected_unknown
    after = db_snapshot(case_uuid)
    assert after["artifacts"] == []
    assert after["drafts"] == []
    assert not [
        asset
        for asset in after["assets"]
        if asset["category"] == "generated_grievance"
    ]
    safe_details = (
        str(rejected_deferred.get("detail", ""))
        + " | "
        + str(rejected_unknown.get("detail", ""))
    )
    assert "Step 3 remains workflow tracking without an official form." in safe_details
    print(
        f"PASS workflow_state={workflow.get('explicit_state')} "
        f"template_id={draft['template_id']} disclosure_retained=True "
        f"deferred_reject_http={status_deferred} unsupported_reject_http={status_unknown} "
        "official_artifacts=0 official_drafts=0 generated_grievance_pdfs=0"
    )
    print(f"safe_rejection={safe_details!r}")


def validate_controlled_failure(case_uuids: list[str]) -> None:
    print("\n=== 5. Controlled PDF failure ===")
    case_uuid = create_case(
        "controlled PDF failure",
        {
            "grievant_name": "Casey Synthetic",
            "facts_what_happened": (
                "Synthetic schedule was changed for controlled failure validation."
            ),
            "violation_articles_citations": "Article 8",
            "corrective_action_requested": "Synthetic restoration remedy.",
        },
    )
    case_uuids.append(case_uuid)
    status, generated = post(f"/cases/{case_uuid}/reports/generate", {})
    assert status == 200, generated
    preview = generated["preview"]
    key = "w6-m10-controlled-pdf-failure"
    payload = {
        "preview": preview,
        "title": "W6 M10 Synthetic Controlled PDF Failure",
        "saved_by": "W6 M10 Synthetic Steward",
        "grievance_step": "step_1_initial",
        "idempotency_key": key,
        "prepare_pdf": True,
    }

    client = TestClient(app)
    with patch(
        "app.services.case_saved_artifact_service.ReportExportService.export_case_pdf",
        side_effect=RuntimeError(
            "SYNTHETIC_INTERNAL_SENTINEL C:\\private\\renderer\\secret.py"
        ),
    ):
        response = client.post(
            f"/cases/{case_uuid}/reports/save-and-print", json=payload
        )
    assert response.status_code == 200, response.text
    failed = response.json()
    assert failed["status"] == "saved_pdf_failed", failed
    assert failed["print_ready"] is False
    assert failed["artifact"]["pdf_status"] == "failed"
    assert failed["artifact"]["printed"] is False
    assert failed["pdf_error"] == "PDF generation failed after the artifact was saved."
    serialized = json.dumps(failed)
    for forbidden in (
        "RuntimeError",
        "SYNTHETIC_INTERNAL_SENTINEL",
        "secret.py",
        "C:\\\\private",
        "Traceback",
    ):
        assert forbidden not in serialized, forbidden

    replay_response = client.post(
        f"/cases/{case_uuid}/reports/save-and-print", json=payload
    )
    assert replay_response.status_code == 200, replay_response.text
    replay = replay_response.json()
    assert replay["status"] == "idempotent_replay"
    assert replay["artifact"]["artifact_uuid"] == failed["artifact"]["artifact_uuid"]
    assert replay["artifact"]["pdf_status"] == "failed"
    assert count_key(case_uuid, key) == 1
    snapshot = db_snapshot(case_uuid)
    assert snapshot["report_versions"] == 1
    assert len(snapshot["artifacts"]) == 1
    assert snapshot["artifacts"][0]["status"] == "official"
    assert snapshot["artifacts"][0]["pdf_status"] == "failed"
    assert snapshot["artifacts"][0]["pdf_asset_uuid"] is None
    print(
        f"PASS failure_http={response.status_code} status={failed['status']} "
        f"artifact_uuid={failed['artifact']['artifact_uuid']} artifact_retained=True "
        f"pdf_status=failed safe_error={failed['pdf_error']!r} "
        f"replay={replay['status']} key_count=1 report_versions=1 "
        "implementation_details_exposed=False"
    )


def run() -> None:
    case_uuids: list[str] = []
    status, _content_type, _raw, health = request("GET", "/health")
    print("=== health ===")
    print(f"backend_http={status} body={health}")
    assert status == 200, health

    validate_analysis(case_uuids)
    validate_step_1(case_uuids)
    validate_step_2(case_uuids)
    validate_step_3(case_uuids)
    validate_controlled_failure(case_uuids)

    CASE_UUIDS.write_text("\n".join(case_uuids) + "\n", encoding="utf-8")
    print("\n=== cleanup ===")
    print(
        "No records or generated files deleted: the repository exposes no "
        "established synthetic case-deletion cleanup API, and generated files "
        "remain referenced by retained synthetic database records."
    )
    print(f"synthetic_case_uuids={case_uuids}")
    print("\nM10_LIVE_SMOKE_OK")


def main() -> int:
    with OUT.open("w", encoding="utf-8") as evidence:
        with redirect_stdout(Tee(sys.stdout, evidence)):
            run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
