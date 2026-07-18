"""Official Save-and-Print artifacts and steward-facing case history."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from app.database.models import (
    CaseAsset,
    CaseFormDraftRecord,
    CaseReportVersion,
    CaseSavedArtifact,
    CaseStep,
    CaseTimelineEventRecord,
    GrievanceCase,
)
from app.schemas.case_saved_artifact_schema import (
    ArtifactCompareResponse,
    CaseHistoryItem,
    CaseHistoryResponse,
    CaseSavedArtifactDetail,
    CaseSavedArtifactListResponse,
    CaseSavedArtifactSummary,
    SaveAndPrintGrievanceRequest,
    SaveAndPrintReportRequest,
    SaveAndPrintResponse,
)
from app.services.case_asset_service import CaseAssetService
from app.services.case_service import CaseNotFoundError, CaseService, ReportVersionNotFoundError
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.case_step_progression_service import CaseStepProgressionNotFoundError
from app.services.report_export.pdf_generator import PdfGenerationError
from app.services.report_export_service import NoReportVersionError, ReportExportService

logger = logging.getLogger(__name__)

_STEWARD_HISTORY_EVENT_TYPES = frozenset(
    {
        "case_created",
        "case_opened",
        "case_reopened",
        "case_closed",
        "case_settled",
        "case_archived",
        "files_uploaded",
        "analysis_report_generated",
        "analysis_report_saved",
        "analysis_report_saved_and_printed",
        "form_draft_created",
        "grievance_form_saved",
        "grievance_form_saved_and_printed",
        "grievance_revision_created",
        "step_decision_added",
        "step_closed",
        "step_reopened",
        "step_changed",
        "appealed_to_next_step",
        "important_case_decision_recorded",
        "management_response_uploaded",
    }
)

_ICON_BY_EVENT = {
    "case_created": "case",
    "case_opened": "case",
    "case_reopened": "case",
    "case_closed": "case",
    "case_settled": "case",
    "case_archived": "case",
    "files_uploaded": "upload",
    "management_response_uploaded": "upload",
    "analysis_report_generated": "report",
    "analysis_report_saved": "report",
    "analysis_report_saved_and_printed": "printed",
    "form_draft_created": "grievance",
    "grievance_form_saved": "grievance",
    "grievance_form_saved_and_printed": "printed",
    "grievance_revision_created": "grievance",
    "step_decision_added": "decision",
    "important_case_decision_recorded": "decision",
    "step_closed": "step",
    "step_reopened": "step",
    "step_changed": "step",
    "appealed_to_next_step": "step",
}


class CaseSavedArtifactError(Exception):
    pass


class CaseSavedArtifactNotFoundError(CaseSavedArtifactError):
    def __init__(self, artifact_uuid: str) -> None:
        self.artifact_uuid = artifact_uuid
        super().__init__(f"Saved artifact not found: {artifact_uuid}")


class CaseSavedArtifactValidationError(CaseSavedArtifactError):
    pass


class CaseSavedArtifactService:
    """Persist official Save-and-Print artifacts and steward case history."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._assets = CaseAssetService(db)
        self._progression = CaseStepProgressionPersistenceService(db)

    # ------------------------------------------------------------------
    # Save and Print — analysis report
    # ------------------------------------------------------------------

    def save_and_print_report(
        self,
        case_uuid: str,
        request: SaveAndPrintReportRequest,
    ) -> SaveAndPrintResponse:
        case = self._require_case(case_uuid)
        if request.idempotency_key:
            existing = self._find_by_idempotency(case_uuid, request.idempotency_key)
            if existing is not None:
                return self._idempotent_response(existing)

        # Steward Save from a temporary Generate preview creates the version now.
        if isinstance(request.preview, dict) and request.preview.get("report_data"):
            try:
                version = CaseService.persist_report_version_from_preview(
                    self.db,
                    case_uuid,
                    request.preview,
                    commit=False,
                )
            except ValueError as exc:
                raise CaseSavedArtifactValidationError(str(exc)) from exc
            case = CaseService.get_case(self.db, case_uuid)
        else:
            version = self._resolve_report_version(case, request.report_version_number)
        if not isinstance(version.report_data, dict):
            raise CaseSavedArtifactValidationError("Report content is invalid.")

        grievance_step = request.grievance_step or self._current_step_type(case_uuid)
        next_version = self._next_artifact_version(case.id, "analysis_report")
        title = request.title or f"Analysis Report v{next_version}"
        version_label = title
        now = datetime.utcnow()
        content = {
            "report_data": version.report_data,
            "report_summary": version.report_summary,
            "issue_analysis": version.issue_analysis,
            "ranked_authorities": version.ranked_authorities,
            "evidence_items": version.evidence_items,
            "retrieval_gaps": version.retrieval_gaps,
            "source_coverage_audit": version.source_coverage_audit,
        }
        key_summary = self._report_key_summary(version, grievance_step)

        self._clear_latest_flag(case.id, "analysis_report")
        artifact = CaseSavedArtifact(
            artifact_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case_uuid,
            artifact_type="analysis_report",
            title=title,
            version_number=next_version,
            version_label=version_label,
            grievance_step=grievance_step,
            content_json=content,
            key_summary_json=key_summary,
            source_report_version_id=version.id,
            source_report_version_number=version.version_number,
            pdf_status="pending",
            printed=False,
            is_latest_official=True,
            saved_by=request.saved_by or case.user_name,
            saved_at=now,
            idempotency_key=request.idempotency_key,
            status="official",
            created_at=now,
        )
        self.db.add(artifact)
        self.db.flush()

        # Consistency: artifact → domain event + memory → steward timeline → PDF.
        summary = version.report_summary if isinstance(version.report_summary, dict) else {}
        from app.services.case_domain_event_service import CaseDomainEventService
        from app.services.case_workflow_service import CaseWorkflowService

        analysis_event_type = (
            "analysis_saved_and_printed" if request.prepare_pdf else "analysis_saved"
        )
        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type=analysis_event_type,
            actor_id=request.saved_by or case.user_name,
            grievance_step=grievance_step,
            source_type="analysis_report",
            source_uuid=artifact.artifact_uuid,
            metadata={
                "report_version_number": version.version_number,
                "report_summary": {
                    k: v
                    for k, v in (summary or {}).items()
                    if k
                    not in {
                        "report_data",
                        "full_text",
                        "ranked_authorities",
                        "evidence_items",
                    }
                },
                "primary_issue": summary.get("primary_issue")
                or key_summary.get("primary_issue"),
                "recommendation": key_summary.get("key_conclusions"),
                "rationale": key_summary.get("key_conclusions"),
                "artifact_uuid": artifact.artifact_uuid,
                "official": True,
                "printed": bool(request.prepare_pdf),
                "saved_and_printed": bool(request.prepare_pdf),
                "version_label": version_label,
            },
            idempotency_key=request.idempotency_key
            or f"{analysis_event_type}:{artifact.artifact_uuid}",
            append_steward_timeline=False,
            commit=False,
        )
        try:
            CaseWorkflowService(self.db).transition(
                case_uuid,
                "step_1_official"
                if grievance_step and "step_1" in grievance_step
                else "step_2_official"
                if grievance_step and "step_2" in grievance_step
                else "step_3_official"
                if grievance_step and "step_3" in grievance_step
                else "step_1_official",
                reason=analysis_event_type,
                actor_id=request.saved_by or case.user_name,
                grievance_step=grievance_step,
                source_type="analysis_report",
                source_uuid=artifact.artifact_uuid,
                allow_authorized_override=True,
                commit=False,
                publish_event=False,
            )
        except Exception:
            pass

        self._append_timeline(
            case,
            event_type="analysis_report_saved_and_printed"
            if request.prepare_pdf
            else "analysis_report_saved",
            title=f"Analysis Report v{next_version} saved"
            + (" and printed" if request.prepare_pdf else ""),
            details=(
                "Official analysis saved and printable PDF prepared."
                if request.prepare_pdf
                else "Official analysis saved (not printed)."
            ),
            report_version_id=version.id,
            report_version_number=version.version_number,
            step_type=grievance_step,
            export_ref=artifact.artifact_uuid,
        )

        pdf_error = None
        print_ready = False
        export_path = None
        if request.prepare_pdf:
            try:
                pdf_bytes, filename = ReportExportService.export_case_pdf(
                    self.db,
                    case_uuid,
                    version_number=version.version_number,
                )
                asset = self._assets.store_system_generated_file(
                    case_uuid,
                    category="generated_report",
                    filename=filename,
                    content=pdf_bytes,
                    mime_type="application/pdf",
                    uploaded_by=request.saved_by or case.user_name,
                    source="export",
                    asset_metadata={
                        "artifact_uuid": artifact.artifact_uuid,
                        "official": True,
                        "save_and_print": True,
                    },
                    report_version_id=version.id,
                    report_version_number=version.version_number,
                    commit=False,
                )
                artifact.pdf_asset_uuid = asset.asset_uuid
                artifact.pdf_status = "ready"
                artifact.printed = True
                print_ready = True
                export_path = (
                    f"/cases/{case_uuid}/artifacts/{artifact.artifact_uuid}/pdf"
                )
            except (PdfGenerationError, NoReportVersionError, Exception) as exc:
                # Persist saved artifact; print is recoverable.
                logger.warning(
                    "save_and_print_report pdf_failed case_uuid=%s error_class=%s",
                    case_uuid,
                    type(exc).__name__,
                )
                artifact.pdf_status = "failed"
                pdf_error = f"PDF generation failed after save: {type(exc).__name__}"

        case.updated_at = now
        self.db.commit()
        self.db.refresh(artifact)

        status = "saved_pdf_failed" if pdf_error else "saved"
        if pdf_error:
            message = "Official analysis report saved; PDF generation failed."
        elif request.prepare_pdf:
            message = "Official analysis report saved and print package prepared."
        else:
            message = "Official analysis report saved."
        return SaveAndPrintResponse(
            case_uuid=case_uuid,
            status=status,
            message=message,
            artifact=self._to_summary(artifact),
            print_ready=print_ready,
            pdf_error=pdf_error,
            export_path=export_path,
        )

    # ------------------------------------------------------------------
    # Save and Print — grievance form
    # ------------------------------------------------------------------

    def save_and_print_grievance(
        self,
        case_uuid: str,
        request: SaveAndPrintGrievanceRequest,
    ) -> SaveAndPrintResponse:
        case = self._require_case(case_uuid)
        if request.idempotency_key:
            existing = self._find_by_idempotency(case_uuid, request.idempotency_key)
            if existing is not None:
                return self._idempotent_response(existing)

        if not isinstance(request.field_values, dict):
            raise CaseSavedArtifactValidationError("field_values must be an object.")

        grievance_step = (
            request.grievance_step
            or self._current_step_type(case_uuid)
            or "step_1_initial"
        )
        step = self._require_or_ensure_step(case_uuid, grievance_step)
        next_version = self._next_artifact_version(case.id, "grievance_form")
        title = request.title or f"Step 1 Grievance v{next_version}"
        if grievance_step and "step_2" in grievance_step:
            title = request.title or f"Step 2 Grievance v{next_version}"
        elif grievance_step and "step_3" in grievance_step:
            title = request.title or f"Step 3 Grievance v{next_version}"
        elif grievance_step and "step_1" in grievance_step:
            title = request.title or f"Step 1 Grievance v{next_version}"
        now = datetime.utcnow()

        field_values = dict(request.field_values)
        content_snapshot = request.content_snapshot or {
            "template_id": request.template_id,
            "template_version": request.template_version,
            "field_values": field_values,
            "steward_override_field_ids": list(request.steward_override_field_ids),
            "missing_required_field_ids": list(request.missing_required_field_ids),
            "validation_status": request.validation_status,
        }

        draft = CaseFormDraftRecord(
            draft_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case_uuid,
            case_step_id=step.id,
            template_id=request.template_id,
            template_version=request.template_version,
            draft_version=next_version,
            draft_status=request.draft_status or "ready_for_steward_review",
            validation_status=request.validation_status,
            missing_required_field_ids=list(request.missing_required_field_ids),
            steward_override_field_ids=list(request.steward_override_field_ids),
            field_values=field_values,
            content_snapshot=content_snapshot,
            is_official=True,
            saved_by=request.saved_by or case.user_name,
            printed_at=None,
            export_status="pending",
            export_attempted=bool(request.prepare_pdf),
            idempotency_key=request.idempotency_key,
            created_at=now,
        )
        self.db.add(draft)
        self.db.flush()

        key_summary = {
            "template_id": request.template_id,
            "template_version": request.template_version,
            "grievance_step": grievance_step,
            "field_count": len(field_values),
            "populated_field_ids": sorted(
                [k for k, v in field_values.items() if v not in (None, "")]
            )[:40],
            "key_field_values": {
                k: field_values[k]
                for k in (
                    "grievant_name",
                    "grievant_name_or_class",
                    "violation_articles_citations",
                    "corrective_action_requested",
                    "facts_what_happened",
                )
                if k in field_values and field_values[k] not in (None, "")
            },
            "validation_status": request.validation_status,
            "steward_override_field_ids": list(request.steward_override_field_ids),
            "is_latest_official": True,
            "printed": False,
        }

        self._clear_latest_flag(case.id, "grievance_form")
        artifact = CaseSavedArtifact(
            artifact_uuid=str(uuid4()),
            case_id=case.id,
            case_uuid=case_uuid,
            artifact_type="grievance_form",
            title=title,
            version_number=next_version,
            version_label=title,
            grievance_step=grievance_step,
            template_id=request.template_id,
            template_version=request.template_version,
            content_json=content_snapshot,
            key_summary_json=key_summary,
            source_draft_record_uuid=draft.draft_uuid,
            pdf_status="pending",
            printed=False,
            is_latest_official=True,
            saved_by=request.saved_by or case.user_name,
            saved_at=now,
            idempotency_key=request.idempotency_key,
            status="official",
            created_at=now,
        )
        self.db.add(artifact)
        self.db.flush()

        step_label = "Step 1"
        if grievance_step and "step_2" in grievance_step:
            step_label = "Step 2"
        elif grievance_step and "step_3" in grievance_step:
            step_label = "Step 3"
        # Consistency: artifact → domain event + memory → steward timeline → PDF.
        from app.services.case_domain_event_service import CaseDomainEventService
        from app.services.case_workflow_service import CaseWorkflowService

        grievance_event_type = (
            "grievance_saved_and_printed" if request.prepare_pdf else "grievance_saved"
        )
        CaseDomainEventService(self.db).publish(
            case_uuid,
            event_type=grievance_event_type,
            actor_id=request.saved_by or case.user_name,
            grievance_step=grievance_step,
            source_type="grievance_form",
            source_uuid=artifact.artifact_uuid,
            metadata={
                "version_number": next_version,
                "artifact_uuid": artifact.artifact_uuid,
                "title": title,
                "template_id": request.template_id,
                "key_field_values": key_summary.get("key_field_values") or {},
                "generated": False,
                "printed": bool(request.prepare_pdf),
                "saved_and_printed": bool(request.prepare_pdf),
                "revised": next_version > 1,
            },
            idempotency_key=request.idempotency_key
            or f"{grievance_event_type}:{artifact.artifact_uuid}",
            append_steward_timeline=False,
            commit=False,
        )
        if next_version > 1:
            CaseDomainEventService(self.db).publish(
                case_uuid,
                event_type="grievance_revised",
                actor_id=request.saved_by or case.user_name,
                grievance_step=grievance_step,
                source_type="grievance_form",
                source_uuid=artifact.artifact_uuid,
                metadata={
                    "version_number": next_version,
                    "artifact_uuid": artifact.artifact_uuid,
                    "title": title,
                    "generated": False,
                    "printed": bool(request.prepare_pdf),
                    "saved_and_printed": bool(request.prepare_pdf),
                },
                idempotency_key=f"grievance_revised:{artifact.artifact_uuid}",
                append_steward_timeline=False,
                commit=False,
            )
        try:
            CaseWorkflowService(self.db).transition(
                case_uuid,
                "step_1_official"
                if "step_1" in (grievance_step or "")
                else "step_2_official"
                if "step_2" in (grievance_step or "")
                else "step_3_official"
                if "step_3" in (grievance_step or "")
                else "step_1_official",
                reason=grievance_event_type,
                actor_id=request.saved_by or case.user_name,
                grievance_step=grievance_step,
                source_type="grievance_form",
                source_uuid=artifact.artifact_uuid,
                allow_authorized_override=True,
                commit=False,
                publish_event=False,
            )
        except Exception:
            pass

        self._append_timeline(
            case,
            event_type="grievance_form_saved_and_printed"
            if request.prepare_pdf
            else "grievance_form_saved",
            title=f"{step_label} Grievance v{next_version} saved"
            + (" and printed" if request.prepare_pdf else ""),
            details=(
                "Official grievance saved and printable PDF prepared."
                if request.prepare_pdf
                else "Official grievance saved (not printed)."
            ),
            step_type=grievance_step,
            draft_record_id=draft.id,
            draft_record_uuid=draft.draft_uuid,
            export_ref=artifact.artifact_uuid,
        )
        if next_version > 1:
            self._append_timeline(
                case,
                event_type="grievance_revision_created",
                title=f"{step_label} grievance revised (v{next_version})",
                details="New official grievance version created; prior versions retained.",
                step_type=grievance_step,
                draft_record_uuid=draft.draft_uuid,
                export_ref=artifact.artifact_uuid,
            )

        pdf_error = None
        print_ready = False
        export_path = None
        if request.prepare_pdf:
            try:
                pdf_bytes = self._render_grievance_fields_pdf(
                    case_uuid=case_uuid,
                    title=title,
                    template_id=request.template_id,
                    template_version=request.template_version,
                    grievance_step=grievance_step,
                    field_values=field_values,
                )
                filename = f"{case_uuid}_grievance_v{next_version}.pdf"
                asset = self._assets.store_system_generated_file(
                    case_uuid,
                    category="generated_grievance",
                    filename=filename,
                    content=pdf_bytes,
                    mime_type="application/pdf",
                    uploaded_by=request.saved_by or case.user_name,
                    source="export",
                    asset_metadata={
                        "artifact_uuid": artifact.artifact_uuid,
                        "official": True,
                        "save_and_print": True,
                        "template_id": request.template_id,
                    },
                    draft_record_uuid=draft.draft_uuid,
                    commit=False,
                )
                artifact.pdf_asset_uuid = asset.asset_uuid
                artifact.pdf_status = "ready"
                artifact.printed = True
                draft.pdf_asset_uuid = asset.asset_uuid
                draft.printed_at = now
                draft.export_status = "exported_pdf"
                draft.exported_at = now
                key_summary["printed"] = True
                artifact.key_summary_json = key_summary
                print_ready = True
                export_path = (
                    f"/cases/{case_uuid}/artifacts/{artifact.artifact_uuid}/pdf"
                )
            except Exception as exc:
                logger.warning(
                    "save_and_print_grievance pdf_failed case_uuid=%s error_class=%s",
                    case_uuid,
                    type(exc).__name__,
                )
                artifact.pdf_status = "failed"
                draft.export_status = "pdf_failed"
                pdf_error = f"PDF generation failed after save: {type(exc).__name__}"

        case.updated_at = now
        self.db.commit()
        self.db.refresh(artifact)

        status = "saved_pdf_failed" if pdf_error else "saved"
        return SaveAndPrintResponse(
            case_uuid=case_uuid,
            status=status,
            message=(
                "Official grievance form saved; PDF generation failed."
                if pdf_error
                else (
                    "Official grievance form saved and print package prepared."
                    if request.prepare_pdf
                    else "Official grievance form saved."
                )
            ),
            artifact=self._to_summary(artifact),
            print_ready=print_ready,
            pdf_error=pdf_error,
            export_path=export_path,
        )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_artifacts(
        self,
        case_uuid: str,
        *,
        artifact_type: str | None = None,
    ) -> CaseSavedArtifactListResponse:
        self._require_case(case_uuid)
        query = self.db.query(CaseSavedArtifact).filter(
            CaseSavedArtifact.case_uuid == case_uuid
        )
        if artifact_type:
            query = query.filter(CaseSavedArtifact.artifact_type == artifact_type)
        rows = query.order_by(
            CaseSavedArtifact.saved_at.asc(), CaseSavedArtifact.id.asc()
        ).all()
        summaries = [self._to_summary(row) for row in rows]
        groups: dict[str, list] = {
            "analysis_reports": [],
            "grievances": [],
            "management_responses": [],
            "evidence": [],
            "other": [],
        }
        for item in summaries:
            if item.artifact_type == "analysis_report":
                groups["analysis_reports"].append(item)
            elif item.artifact_type == "grievance_form":
                groups["grievances"].append(item)
            else:
                groups["other"].append(item)
        return CaseSavedArtifactListResponse(
            case_uuid=case_uuid,
            count=len(rows),
            artifacts=summaries,
            groups=groups,
        )

    def get_artifact(
        self,
        case_uuid: str,
        artifact_uuid: str,
        *,
        include_content: bool = True,
    ) -> CaseSavedArtifactDetail:
        row = self._get_artifact_row(case_uuid, artifact_uuid)
        summary = self._to_summary(row)
        return CaseSavedArtifactDetail(
            **summary.model_dump(),
            content_json=row.content_json if include_content else {},
            pdf_download_path=(
                f"/cases/{case_uuid}/artifacts/{artifact_uuid}/pdf"
                if row.pdf_asset_uuid
                else None
            ),
        )

    def get_artifact_pdf_bytes(
        self, case_uuid: str, artifact_uuid: str
    ) -> tuple[bytes, str]:
        row = self._get_artifact_row(case_uuid, artifact_uuid)
        if not row.pdf_asset_uuid:
            raise CaseSavedArtifactValidationError("No PDF snapshot for this artifact.")
        asset = self._assets.get_asset_row(case_uuid, row.pdf_asset_uuid)
        if not asset.stored_path:
            raise CaseSavedArtifactValidationError("PDF asset path missing.")
        from pathlib import Path

        from app.config import PROJECT_ROOT

        path = Path(asset.stored_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        data = path.read_bytes()
        return data, asset.original_filename or f"{artifact_uuid}.pdf"

    def list_steward_case_history(
        self,
        case_uuid: str,
        *,
        order: str = "oldest_first",
        limit: int = 100,
    ) -> CaseHistoryResponse:
        self._require_case(case_uuid)
        limit = max(1, min(limit, 200))
        rows = (
            self.db.query(CaseTimelineEventRecord)
            .filter(
                CaseTimelineEventRecord.case_uuid == case_uuid,
                CaseTimelineEventRecord.event_type.in_(_STEWARD_HISTORY_EVENT_TYPES),
            )
            .order_by(
                CaseTimelineEventRecord.event_timestamp.asc()
                if order == "oldest_first"
                else CaseTimelineEventRecord.event_timestamp.desc(),
                CaseTimelineEventRecord.id.asc()
                if order == "oldest_first"
                else CaseTimelineEventRecord.id.desc(),
            )
            .limit(limit)
            .all()
        )
        # Also surface official artifacts that may predate timeline wiring.
        artifacts = (
            self.db.query(CaseSavedArtifact)
            .filter(CaseSavedArtifact.case_uuid == case_uuid)
            .order_by(CaseSavedArtifact.saved_at.asc())
            .all()
        )
        artifact_by_uuid = {a.artifact_uuid: a for a in artifacts}
        events: list[CaseHistoryItem] = []
        seen_artifact_exports: set[str] = set()
        for row in rows:
            artifact = None
            if row.export_ref and row.export_ref in artifact_by_uuid:
                artifact = artifact_by_uuid[row.export_ref]
                seen_artifact_exports.add(row.export_ref)
            events.append(self._history_item_from_timeline(row, artifact))

        for artifact in artifacts:
            if artifact.artifact_uuid in seen_artifact_exports:
                continue
            events.append(self._history_item_from_artifact(artifact))

        events.sort(key=lambda item: item.event_timestamp)
        if order == "newest_first":
            events = list(reversed(events))
        events = events[:limit]
        return CaseHistoryResponse(
            case_uuid=case_uuid,
            label="Official Case Record",
            count=len(events),
            order="oldest_first" if order == "oldest_first" else "newest_first",
            events=events,
        )

    def official_artifact_index(self, case_uuid: str) -> list[dict]:
        """Lightweight index of ALL official artifacts (no bodies)."""
        self._require_case(case_uuid)
        rows = (
            self.db.query(CaseSavedArtifact)
            .filter(CaseSavedArtifact.case_uuid == case_uuid)
            .order_by(
                CaseSavedArtifact.artifact_type.asc(),
                CaseSavedArtifact.version_number.asc(),
                CaseSavedArtifact.id.asc(),
            )
            .all()
        )
        return [
            {
                "artifact_uuid": row.artifact_uuid,
                "artifact_type": row.artifact_type,
                "title": row.title,
                "version": row.version_number,
                "version_label": row.version_label,
                "grievance_step": row.grievance_step,
                "saved_at": row.saved_at.isoformat() if row.saved_at else None,
                "printed": bool(row.printed),
                "is_latest_official": bool(row.is_latest_official),
                "template_id": row.template_id,
                "retrieval_path": f"/cases/{case_uuid}/artifacts/{row.artifact_uuid}",
                "content_embedded": False,
            }
            for row in rows
        ]

    def compare_artifacts(
        self,
        case_uuid: str,
        left_artifact_uuid: str,
        right_artifact_uuid: str,
    ) -> ArtifactCompareResponse:
        """Retrieve and compare two official artifact versions on one case."""
        left = self.get_artifact(case_uuid, left_artifact_uuid, include_content=True)
        right = self.get_artifact(case_uuid, right_artifact_uuid, include_content=True)
        if left.artifact_type != right.artifact_type:
            raise CaseSavedArtifactValidationError(
                "Compared artifacts must share the same artifact_type."
            )
        left_keys = set((left.key_summary or {}).keys())
        right_keys = set((right.key_summary or {}).keys())
        shared = left_keys & right_keys
        changed = sorted(
            key
            for key in shared
            if (left.key_summary or {}).get(key) != (right.key_summary or {}).get(key)
        )
        return ArtifactCompareResponse(
            case_uuid=case_uuid,
            artifact_type=left.artifact_type,
            left=left,
            right=right,
            changed_summary_keys=changed,
            left_only_summary_keys=sorted(left_keys - right_keys),
            right_only_summary_keys=sorted(right_keys - left_keys),
            version_delta=right.version_number - left.version_number,
        )

    def compare_artifact_versions(
        self,
        case_uuid: str,
        artifact_type: str,
        left_version: int,
        right_version: int,
    ) -> ArtifactCompareResponse:
        """Resolve official versions by number and compare (case-scoped)."""
        left_row = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.artifact_type == artifact_type,
                CaseSavedArtifact.version_number == left_version,
            )
            .first()
        )
        right_row = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.artifact_type == artifact_type,
                CaseSavedArtifact.version_number == right_version,
            )
            .first()
        )
        if left_row is None or right_row is None:
            raise CaseSavedArtifactNotFoundError(
                f"{artifact_type}:v{left_version}|v{right_version}"
            )
        return self.compare_artifacts(
            case_uuid,
            left_row.artifact_uuid,
            right_row.artifact_uuid,
        )

    def find_official_pdf_for_report_version(
        self,
        case_uuid: str,
        report_version_number: int | None,
    ) -> CaseSavedArtifact | None:
        """Return official saved artifact for a report version when present."""
        query = self.db.query(CaseSavedArtifact).filter(
            CaseSavedArtifact.case_uuid == case_uuid,
            CaseSavedArtifact.artifact_type == "analysis_report",
            CaseSavedArtifact.pdf_asset_uuid.isnot(None),
        )
        if report_version_number is not None:
            query = query.filter(
                CaseSavedArtifact.source_report_version_number == report_version_number
            )
        return query.order_by(
            CaseSavedArtifact.is_latest_official.desc(),
            CaseSavedArtifact.version_number.desc(),
        ).first()

    def continuity_artifacts(self, case_uuid: str, *, limit: int = 12) -> list[dict]:
        """Bounded official-artifact summaries for AI continuity."""
        rows = (
            self.db.query(CaseSavedArtifact)
            .filter(CaseSavedArtifact.case_uuid == case_uuid)
            .order_by(CaseSavedArtifact.saved_at.desc(), CaseSavedArtifact.id.desc())
            .limit(limit)
            .all()
        )
        compact: list[dict] = []
        for row in reversed(rows):
            summary = row.key_summary_json if isinstance(row.key_summary_json, dict) else {}
            compact.append(
                {
                    "artifact_uuid": row.artifact_uuid,
                    "artifact_type": row.artifact_type,
                    "title": row.title,
                    "version": row.version_number,
                    "version_label": row.version_label,
                    "grievance_step": row.grievance_step,
                    "saved_at": row.saved_at.isoformat() if row.saved_at else None,
                    "status": row.status,
                    "printed": bool(row.printed),
                    "is_latest_official": bool(row.is_latest_official),
                    "template_id": row.template_id,
                    "template_version": row.template_version,
                    "key_conclusions": summary.get("key_conclusions")
                    or summary.get("primary_issue"),
                    "key_field_values": summary.get("key_field_values") or {},
                    "retrieval_reference": {
                        "path": f"/cases/{case_uuid}/artifacts/{row.artifact_uuid}",
                        "pdf_path": (
                            f"/cases/{case_uuid}/artifacts/{row.artifact_uuid}/pdf"
                            if row.pdf_asset_uuid
                            else None
                        ),
                    },
                    "content_embedded": False,
                }
            )
        return compact

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_case(self, case_uuid: str) -> GrievanceCase:
        case = CaseService._get_case_row(self.db, case_uuid)
        if case is None:
            raise CaseNotFoundError(case_uuid)
        return case

    def _get_artifact_row(self, case_uuid: str, artifact_uuid: str) -> CaseSavedArtifact:
        row = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.artifact_uuid == artifact_uuid,
            )
            .first()
        )
        if row is None:
            raise CaseSavedArtifactNotFoundError(artifact_uuid)
        return row

    def _find_by_idempotency(
        self, case_uuid: str, idempotency_key: str
    ) -> CaseSavedArtifact | None:
        return (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_uuid == case_uuid,
                CaseSavedArtifact.idempotency_key == idempotency_key,
            )
            .first()
        )

    def _idempotent_response(self, artifact: CaseSavedArtifact) -> SaveAndPrintResponse:
        return SaveAndPrintResponse(
            case_uuid=artifact.case_uuid,
            status="idempotent_replay",
            message="Idempotent Save and Print replay; no new version created.",
            artifact=self._to_summary(artifact),
            print_ready=bool(artifact.printed and artifact.pdf_status == "ready"),
            export_path=(
                f"/cases/{artifact.case_uuid}/artifacts/{artifact.artifact_uuid}/pdf"
                if artifact.pdf_asset_uuid
                else None
            ),
        )

    def _resolve_report_version(
        self, case: GrievanceCase, version_number: int | None
    ) -> CaseReportVersion:
        versions = sorted(case.report_versions or [], key=lambda v: v.version_number)
        if not versions:
            case_full = CaseService.get_case(self.db, case.case_uuid)
            versions = sorted(
                case_full.report_versions or [], key=lambda v: v.version_number
            )
        if not versions:
            raise NoReportVersionError(case.case_uuid)
        if version_number is None:
            return versions[-1]
        for version in versions:
            if version.version_number == version_number:
                return version
        raise ReportVersionNotFoundError(version_number)

    def _next_artifact_version(self, case_id: int, artifact_type: str) -> int:
        latest = (
            self.db.query(CaseSavedArtifact.version_number)
            .filter(
                CaseSavedArtifact.case_id == case_id,
                CaseSavedArtifact.artifact_type == artifact_type,
            )
            .order_by(CaseSavedArtifact.version_number.desc())
            .first()
        )
        return (latest[0] if latest else 0) + 1

    def _clear_latest_flag(self, case_id: int, artifact_type: str) -> None:
        rows = (
            self.db.query(CaseSavedArtifact)
            .filter(
                CaseSavedArtifact.case_id == case_id,
                CaseSavedArtifact.artifact_type == artifact_type,
                CaseSavedArtifact.is_latest_official.is_(True),
            )
            .all()
        )
        for row in rows:
            row.is_latest_official = False

    def _current_step_type(self, case_uuid: str) -> str | None:
        try:
            state = self._progression.get_progression(case_uuid)
        except CaseStepProgressionNotFoundError:
            return None
        return state.current_step_type

    def _require_or_ensure_step(self, case_uuid: str, step_type: str) -> CaseStep:
        self._progression.ensure_case_progression(case_uuid)
        step = (
            self.db.query(CaseStep)
            .filter(CaseStep.case_uuid == case_uuid, CaseStep.step_type == step_type)
            .first()
        )
        if step is not None:
            return step
        # Fall back to current open step when requested step row missing.
        step = (
            self.db.query(CaseStep)
            .filter(CaseStep.case_uuid == case_uuid)
            .order_by(CaseStep.step_number.desc())
            .first()
        )
        if step is None:
            raise CaseSavedArtifactValidationError(
                f"No grievance step available for case {case_uuid}"
            )
        return step

    def _append_timeline(
        self,
        case: GrievanceCase,
        *,
        event_type: str,
        title: str,
        details: str | None,
        step_type: str | None = None,
        report_version_id: int | None = None,
        report_version_number: int | None = None,
        draft_record_id: int | None = None,
        draft_record_uuid: str | None = None,
        export_ref: str | None = None,
    ) -> None:
        step_id = None
        if step_type:
            step = (
                self.db.query(CaseStep)
                .filter(
                    CaseStep.case_uuid == case.case_uuid,
                    CaseStep.step_type == step_type,
                )
                .first()
            )
            if step is not None:
                step_id = step.id
        now = datetime.utcnow()
        self.db.add(
            CaseTimelineEventRecord(
                event_uuid=str(uuid4()),
                case_id=case.id,
                case_uuid=case.case_uuid,
                case_step_id=step_id,
                step_type=step_type,
                event_type=event_type,
                event_timestamp=now,
                title=title,
                details=details,
                report_version_id=report_version_id,
                report_version_number=report_version_number,
                draft_record_id=draft_record_id,
                draft_record_uuid=draft_record_uuid,
                export_ref=export_ref,
                created_at=now,
            )
        )

    @staticmethod
    def _report_key_summary(version: CaseReportVersion, grievance_step: str | None) -> dict:
        summary = version.report_summary if isinstance(version.report_summary, dict) else {}
        report = version.report_data if isinstance(version.report_data, dict) else {}
        root = report.get("report") if isinstance(report.get("report"), dict) else report
        quick = root.get("quick_assessment") if isinstance(root.get("quick_assessment"), dict) else {}
        return {
            "primary_issue": summary.get("primary_issue") or quick.get("summary"),
            "grievability": quick.get("grievability"),
            "confidence": quick.get("confidence"),
            "key_conclusions": quick.get("summary"),
            "authority_count": summary.get("authority_count"),
            "grievance_step": grievance_step,
            "source_report_version_number": version.version_number,
            "printed": False,
            "is_latest_official": True,
        }

    def _to_summary(self, row: CaseSavedArtifact) -> CaseSavedArtifactSummary:
        return CaseSavedArtifactSummary(
            artifact_uuid=row.artifact_uuid,
            case_uuid=row.case_uuid,
            artifact_type=row.artifact_type,  # type: ignore[arg-type]
            title=row.title,
            version_number=row.version_number,
            version_label=row.version_label,
            grievance_step=row.grievance_step,
            template_id=row.template_id,
            template_version=row.template_version,
            printed=bool(row.printed),
            pdf_status=row.pdf_status,
            pdf_asset_uuid=row.pdf_asset_uuid,
            is_latest_official=bool(row.is_latest_official),
            saved_by=row.saved_by,
            saved_at=row.saved_at,
            source_report_version_number=row.source_report_version_number,
            source_draft_record_uuid=row.source_draft_record_uuid,
            key_summary=row.key_summary_json
            if isinstance(row.key_summary_json, dict)
            else None,
            retrieval={
                "artifact": f"/cases/{row.case_uuid}/artifacts/{row.artifact_uuid}",
                "pdf": f"/cases/{row.case_uuid}/artifacts/{row.artifact_uuid}/pdf",
            },
        )

    def _history_item_from_timeline(
        self,
        row: CaseTimelineEventRecord,
        artifact: CaseSavedArtifact | None,
    ) -> CaseHistoryItem:
        clickable = False
        retrieval = None
        artifact_uuid = None
        artifact_type = None
        if artifact is not None:
            clickable = True
            artifact_uuid = artifact.artifact_uuid
            artifact_type = artifact.artifact_type
            retrieval = f"/cases/{row.case_uuid}/artifacts/{artifact.artifact_uuid}"
        elif row.report_version_number is not None:
            clickable = True
            retrieval = (
                f"/cases/{row.case_uuid}/versions/{row.report_version_number}"
            )
        elif row.draft_record_uuid:
            clickable = True
            retrieval = f"/cases/{row.case_uuid}/workspace"
        elif row.upload_refs:
            clickable = True
            first = row.upload_refs[0]
            retrieval = f"/cases/{row.case_uuid}/assets/{first}"
        record_class = self._record_class_for_event(row.event_type)
        display_label = self._display_label_for_event(row.event_type, row.title)
        context_path = f"/cases/{row.case_uuid}/history/{row.event_uuid}/context"
        return CaseHistoryItem(
            event_id=row.event_uuid,
            event_type=row.event_type,
            title=row.title,
            details=row.details,
            event_timestamp=row.event_timestamp,
            icon=_ICON_BY_EVENT.get(row.event_type, "case"),
            clickable=True,
            artifact_uuid=artifact_uuid,
            artifact_type=artifact_type,
            asset_uuid=(row.upload_refs or [None])[0] if row.upload_refs else None,
            report_version_number=row.report_version_number,
            draft_uuid=row.draft_record_uuid,
            retrieval_path=retrieval,
            context_path=context_path,
            record_class=record_class,  # type: ignore[arg-type]
            display_label=display_label,
        )

    def _history_item_from_artifact(self, artifact: CaseSavedArtifact) -> CaseHistoryItem:
        event_type = (
            "analysis_report_saved_and_printed"
            if artifact.artifact_type == "analysis_report"
            else "grievance_form_saved_and_printed"
        )
        return CaseHistoryItem(
            event_id=artifact.artifact_uuid,
            event_type=event_type,
            title=artifact.version_label,
            details="Official saved artifact",
            event_timestamp=artifact.saved_at,
            icon="printed" if artifact.printed else (
                "report" if artifact.artifact_type == "analysis_report" else "grievance"
            ),
            clickable=True,
            artifact_uuid=artifact.artifact_uuid,
            artifact_type=artifact.artifact_type,
            retrieval_path=(
                f"/cases/{artifact.case_uuid}/artifacts/{artifact.artifact_uuid}"
            ),
            context_path=(
                f"/cases/{artifact.case_uuid}/artifacts/{artifact.artifact_uuid}"
            ),
            record_class="official_record",
            display_label="Official saved",
        )

    @staticmethod
    def _record_class_for_event(event_type: str) -> str:
        if event_type in {
            "analysis_report_saved",
            "analysis_report_saved_and_printed",
            "grievance_form_saved",
            "grievance_form_saved_and_printed",
        }:
            return "official_record"
        if event_type in {
            "analysis_report_generated",
            "form_draft_created",
            "grievance_revision_created",
        }:
            return "working_draft"
        if event_type.startswith("case_") or event_type in {
            "step_decision_added",
            "appealed_to_next_step",
            "important_case_decision_recorded",
        }:
            return "lifecycle"
        return "other"

    @staticmethod
    def _display_label_for_event(event_type: str, title: str) -> str:
        mapping = {
            "analysis_report_generated": "Draft generated",
            "form_draft_created": "Draft generated",
            "grievance_revision_created": "Revised draft",
            "analysis_report_saved": "Official saved",
            "grievance_form_saved": "Official saved",
            "analysis_report_saved_and_printed": "Official printed",
            "grievance_form_saved_and_printed": "Official printed",
        }
        return mapping.get(event_type) or title

    @staticmethod
    def _render_grievance_fields_pdf(
        *,
        case_uuid: str,
        title: str,
        template_id: str,
        template_version: str | None,
        grievance_step: str | None,
        field_values: dict,
    ) -> bytes:
        """Printable snapshot of persisted field values (official Local-300 overlay is future)."""
        rows = "".join(
            (
                "<tr><th>"
                f"{html.escape(str(key))}</th><td>"
                f"{html.escape(str(value) if value is not None else '')}</td></tr>"
            )
            for key, value in sorted(field_values.items(), key=lambda item: str(item[0]))
        )
        html_doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: Georgia, serif; margin: 32px; color: #1a1a1a; }}
h1 {{ font-size: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ width: 35%; background: #f4f4f4; }}
.meta {{ margin-bottom: 16px; font-size: 12px; color: #444; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta">
Case: {html.escape(case_uuid)}<br/>
Template: {html.escape(template_id)}
{" v" + html.escape(template_version) if template_version else ""}<br/>
Step: {html.escape(str(grievance_step or ""))}<br/>
Official saved field-value snapshot
</div>
<table>{rows or "<tr><td colspan='2'>No field values</td></tr>"}</table>
</body></html>"""
        return ReportExportService.render_pdf_from_html(html_doc)
