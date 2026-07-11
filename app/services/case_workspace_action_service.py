"""Case workspace orchestration — AI-first chat + compatibility actions (W1–W3).

Permanent product principle:
**The application manages the workflow. The steward manages the grievance.**

Canonical steward chat:
``POST /cases/{case_uuid}/interactions`` → ``submit_interaction``

One interaction automatically:
- persists steward + AI messages
- merges safe fact updates / asset refs
- runs the existing full analysis pipeline once
- creates one new immutable report version
- appends timeline events
- returns AI reply + synchronized workspace state + Generate Grievance availability

Internal primitives (no duplicate RAG/report builders):
- ``FollowUpChatService`` — conversational turn
- ``CaseService.generate_report_version`` — analysis refresh (W2 primitive)
- ``CaseAssetService`` — asset resolution (W3)
- ``CaseStepProgressionPersistenceService`` — timeline

Compatibility:
- ``save_and_update_analysis`` on ``/actions`` — analysis refresh without requiring
  a steward-facing Update Analysis button
- ``generate_grievance`` on ``/actions`` — explicit optional action (W5)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.database.models import CaseMessage, CaseReportVersion, GrievanceCase
from app.schemas.case_step_progression_schema import (
    CaseTimelineEvent,
    CaseTimelineEventReferences,
    StepType,
)
from app.schemas.case_workspace_action_schema import (
    AnalysisUpdateResult,
    CaseInteractionMessageSummary,
    CaseInteractionRequest,
    CaseInteractionResponse,
    GrievanceGenerationResult,
    WorkspaceActionAvailability,
    WorkspaceActionPrerequisite,
    WorkspaceActionRequest,
    WorkspaceActionResponse,
    WorkspaceActionType,
    WorkspaceInteractionPayload,
    WorkspaceTimelineEventSummary,
)
from app.services.case_service import CaseNotFoundError, CaseService
from app.services.case_asset_service import CaseAssetService
from app.services.case_step_progression_persistence_service import (
    CaseStepProgressionPersistenceService,
)
from app.services.case_step_progression_service import (
    CaseStepNotFoundError,
    CaseStepProgressionNotFoundError,
    CaseStepProgressionService,
)
from app.services.follow_up_chat_service import FollowUpChatService

# Internal compatibility markers (not steward UI button labels).
INTERNAL_SAVE_AND_UPDATE_ACTION = "save_and_update_analysis"
CASE_INTERACTION_INTENT = "case_interaction"
CASE_INTERACTION_TRIGGER = "case_interaction"
UPDATE_ANALYSIS_INTENT = "update_analysis"  # compatibility metadata
UPDATE_ANALYSIS_TRIGGER = "update_analysis"  # compatibility metadata


@dataclass
class _WorkspaceInspection:
    """Internal snapshot of case workspace prerequisites."""

    case: GrievanceCase
    has_analysis_report: bool
    latest_report_version_id: int | None
    latest_report_version_number: int | None
    has_step_progression: bool
    current_step_type: StepType | None
    template_id: str | None
    template_availability_status: str | None
    template_available: bool
    case_status: str


class CaseWorkspaceActionService:
    """Orchestration boundary for AI-first case interactions and actions.

    - ``submit_interaction``: canonical chat + automatic analysis refresh
    - ``save_and_update_analysis``: internal/compatibility analysis refresh
    - ``generate_grievance``: explicit optional action (W5)
    """

    W1_NOT_IMPLEMENTED_MESSAGE = (
        "Generate Grievance execution is deferred to Phase W5. "
        "Case chat uses POST /cases/{case_uuid}/interactions."
    )

    def __init__(self, db: Session) -> None:
        self.db = db
        self._progression = CaseStepProgressionPersistenceService(db)
        self._assets = CaseAssetService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_action(
        self,
        case_uuid: str,
        request: WorkspaceActionRequest,
    ) -> WorkspaceActionResponse:
        """Validate and dispatch a workspace action (compatibility + Generate Grievance)."""
        if request.action == "save_and_update_analysis":
            return self.save_and_update_analysis(case_uuid, request.interaction)
        if request.action == "generate_grievance":
            return self.generate_grievance(case_uuid, request.interaction)
        return WorkspaceActionResponse(
            case_uuid=case_uuid,
            action=request.action,
            status="invalid_request",
            message=f"Unsupported workspace action: {request.action}",
            missing_prerequisites=[
                WorkspaceActionPrerequisite(
                    code="action_not_implemented_in_w1",
                    message=f"Unknown action '{request.action}'.",
                )
            ],
            interaction_accepted_for_later_phases=request.interaction is not None,
        )

    def submit_interaction(
        self,
        case_uuid: str,
        request: CaseInteractionRequest,
        *,
        limit_per_source: int = 8,
        llm_callable: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> CaseInteractionResponse:
        """Canonical AI-first case interaction: chat turn + automatic analysis refresh.

        Creates exactly one new immutable analysis version. Does not generate
        grievances, snapshots, or exports.
        """
        interaction = request.to_interaction_payload()
        try:
            inspection = self._inspect_workspace(case_uuid)
        except CaseNotFoundError:
            return CaseInteractionResponse(
                case_uuid=case_uuid,
                status="case_not_found",
                message=f"Case not found: {case_uuid}",
                workspace_current=False,
                missing_prerequisites=[
                    WorkspaceActionPrerequisite(
                        code="case_not_found",
                        message=f"No grievance case exists for uuid {case_uuid}.",
                    )
                ],
            )

        available_actions = self.evaluate_action_availability(inspection)
        if inspection.case_status == "closed":
            return CaseInteractionResponse(
                case_uuid=case_uuid,
                status="prerequisites_not_met",
                message="Case is closed. Reopen the case before continuing the conversation.",
                workspace_current=False,
                available_actions=available_actions,
                generate_grievance_available=False,
                missing_prerequisites=[
                    WorkspaceActionPrerequisite(
                        code="case_closed_requires_reopen",
                        message=(
                            "Case is closed. Reopen before submitting a case interaction."
                        ),
                    )
                ],
                prior_report_version_id=inspection.latest_report_version_id,
                prior_report_version_number=inspection.latest_report_version_number,
                current_report_version_id=inspection.latest_report_version_id,
                current_report_version_number=inspection.latest_report_version_number,
            )

        if not inspection.has_analysis_report:
            return CaseInteractionResponse(
                case_uuid=case_uuid,
                status="prerequisites_not_met",
                message="Case interaction requires an existing analysis report version.",
                workspace_current=False,
                available_actions=available_actions,
                generate_grievance_available=False,
                missing_prerequisites=[
                    WorkspaceActionPrerequisite(
                        code="analysis_report_required",
                        message=(
                            "Case chat requires a current analysis report to ground replies."
                        ),
                    )
                ],
            )

        has_text = bool(
            (interaction.message and interaction.message.strip())
            or (interaction.clarification and interaction.clarification.strip())
        )
        has_uploads = bool(interaction.upload_refs)
        has_facts = bool(interaction.fact_updates)
        if not has_text and not has_uploads and not has_facts:
            return CaseInteractionResponse(
                case_uuid=case_uuid,
                status="invalid_request",
                message=(
                    "Interaction requires a message, clarification, fact_updates, "
                    "or upload_refs."
                ),
                workspace_current=False,
                available_actions=available_actions,
                generate_grievance_available=self._generate_grievance_available(
                    available_actions
                ),
                missing_prerequisites=[
                    WorkspaceActionPrerequisite(
                        code="interaction_content_required",
                        message="Provide chat content or context updates.",
                    )
                ],
                prior_report_version_id=inspection.latest_report_version_id,
                prior_report_version_number=inspection.latest_report_version_number,
                current_report_version_id=inspection.latest_report_version_id,
                current_report_version_number=inspection.latest_report_version_number,
            )

        prior_version_id = inspection.latest_report_version_id
        prior_version_number = inspection.latest_report_version_number

        facts_updated = self._merge_fact_updates(case_uuid, interaction)

        content = self._build_interaction_content(interaction)
        follow_up: dict[str, Any] | None = None
        user_message: CaseMessage | None = None
        assistant_message: CaseMessage | None = None
        ai_response_persisted = False

        if has_text:
            follow_up = FollowUpChatService.answer_follow_up(
                db=self.db,
                case_uuid=case_uuid,
                content=content,
                report_version_number=interaction.pinned_report_version,
                llm_callable=llm_callable,
            )
            user_message = follow_up["user_message"]
            assistant_message = follow_up["assistant_message"]
            ai_response_persisted = True
            trigger_metadata = self._enrich_interaction_message_metadata(
                case_uuid,
                user_message,
                interaction,
                facts_updated=facts_updated,
            )
        else:
            # Context-only interaction (facts/assets): persist one steward note,
            # then refresh analysis — still one report version, no chatbot-only path.
            user_message, trigger_metadata = self._persist_context_only_message(
                case_uuid, interaction, facts_updated=facts_updated
            )

        timeline_summaries: list[WorkspaceTimelineEventSummary] = []
        context_event = self._append_timeline_safe(
            case_uuid,
            event_type="context_saved",
            title="Context saved",
            step_type=inspection.current_step_type,
            details="Steward interaction persisted; conversation and context preserved.",
            references=CaseTimelineEventReferences(
                follow_up_message_ids=(
                    [user_message.id] if user_message is not None else []
                ),
                upload_refs=list(interaction.upload_refs),
            ),
        )
        if context_event is not None:
            timeline_summaries.append(
                self._timeline_summary(
                    context_event,
                    report_version_id=None,
                    report_version_number=None,
                )
            )

        # Exactly one analysis regeneration for this interaction (W2 primitive).
        new_version = CaseService.generate_report_version(
            db=self.db,
            case_uuid=case_uuid,
            limit_per_source=limit_per_source,
            trigger_message_id=(
                user_message.id if user_message is not None else None
            ),
        )

        analysis_event = self._append_timeline_safe(
            case_uuid,
            event_type="analysis_updated",
            title="Analysis updated",
            step_type=inspection.current_step_type,
            details=(
                f"New immutable analysis report version {new_version.version_number} "
                f"created automatically after case interaction."
            ),
            references=CaseTimelineEventReferences(
                report_version_id=new_version.id,
                report_version_number=new_version.version_number,
                follow_up_message_ids=(
                    [user_message.id] if user_message is not None else []
                ),
                upload_refs=list(interaction.upload_refs),
            ),
        )
        if analysis_event is not None:
            timeline_summaries.append(
                self._timeline_summary(
                    analysis_event,
                    report_version_id=new_version.id,
                    report_version_number=new_version.version_number,
                )
            )

        post_inspection = self._inspect_workspace(case_uuid)
        available_actions = self.evaluate_action_availability(post_inspection)
        generate_available = self._generate_grievance_available(available_actions)

        analysis_update = AnalysisUpdateResult(
            steward_action_label=None,
            interaction_saved=True,
            prior_conversation_preserved=True,
            facts_updated=facts_updated,
            ai_response_persisted=ai_response_persisted,
            prior_report_version_id=prior_version_id,
            prior_report_version_number=prior_version_number,
            new_report_version_id=new_version.id,
            new_report_version_number=new_version.version_number,
            is_current_analysis=True,
            older_versions_retained=True,
            trigger_message_id=(
                user_message.id if user_message is not None else None
            ),
            trigger_metadata=trigger_metadata,
            timeline_events=timeline_summaries,
            message=(
                f"Workspace is current. Analysis version {new_version.version_number} "
                f"is Current Analysis; prior versions retained. "
                f"Generate Grievance "
                f"{'available' if generate_available else 'unavailable'}."
            ),
        )

        ai_answer = None
        answer_type = None
        citations: list[dict[str, Any]] = []
        disclosures: list[str] = []
        facts_needed: list[str] = []
        if follow_up is not None:
            ai_answer = follow_up["answer"]
            answer_type = follow_up["answer_type"]
            citations = list(follow_up.get("citations") or [])
            disclosures = list(follow_up.get("disclosures") or [])
            facts_needed = list(follow_up.get("facts_needed") or [])

        return CaseInteractionResponse(
            case_uuid=case_uuid,
            status="completed",
            message=analysis_update.message,
            workspace_current=True,
            user_message=self._message_summary(user_message),
            assistant_message=self._message_summary(assistant_message),
            ai_answer=ai_answer,
            answer_type=answer_type,
            citations=citations,
            disclosures=disclosures,
            facts_needed=facts_needed,
            prior_report_version_id=prior_version_id,
            prior_report_version_number=prior_version_number,
            current_report_version_id=new_version.id,
            current_report_version_number=new_version.version_number,
            analysis_update=analysis_update,
            available_actions=available_actions,
            generate_grievance_available=generate_available,
            timeline_events=timeline_summaries,
            grievance_draft_created=False,
            generation_snapshot_persisted=False,
            export_attempted=False,
            analysis_versions_created=1,
        )

    def save_and_update_analysis(
        self,
        case_uuid: str,
        interaction: WorkspaceInteractionPayload | None = None,
        *,
        limit_per_source: int = 8,
    ) -> WorkspaceActionResponse:
        """Compatibility analysis refresh (internal; not a steward UI button).

        Prefer ``submit_interaction`` / POST /interactions for steward chat.
        Reuses the same ``generate_report_version`` primitive — no duplicate pipeline.
        """
        try:
            inspection = self._inspect_workspace(case_uuid)
        except CaseNotFoundError:
            return self._case_not_found_response(
                case_uuid, "save_and_update_analysis", interaction
            )

        available_actions = self.evaluate_action_availability(inspection)
        save_availability = next(
            a for a in available_actions if a.action == "save_and_update_analysis"
        )

        if not save_availability.available:
            return WorkspaceActionResponse(
                case_uuid=case_uuid,
                action="save_and_update_analysis",
                status="prerequisites_not_met",
                message=save_availability.reason
                or "Analysis refresh prerequisites not met.",
                steward_action_label=None,
                available_actions=available_actions,
                missing_prerequisites=list(save_availability.missing_prerequisites),
                prior_report_version_id=inspection.latest_report_version_id,
                prior_report_version_number=inspection.latest_report_version_number,
                analysis_update=AnalysisUpdateResult(
                    message=(
                        "Analysis refresh blocked: case must be open or reopened."
                    ),
                ),
                interaction_accepted_for_later_phases=interaction is not None,
            )

        prior_version_id = inspection.latest_report_version_id
        prior_version_number = inspection.latest_report_version_number

        trigger_message, interaction_saved, facts_updated, trigger_metadata = (
            self._persist_interaction(case_uuid, interaction)
        )

        timeline_summaries: list[WorkspaceTimelineEventSummary] = []
        if interaction_saved or facts_updated:
            context_event = self._append_timeline_safe(
                case_uuid,
                event_type="context_saved",
                title="Context saved",
                step_type=inspection.current_step_type,
                details="Steward context saved via compatibility analysis refresh.",
                references=CaseTimelineEventReferences(
                    follow_up_message_ids=(
                        [trigger_message.id] if trigger_message is not None else []
                    ),
                    upload_refs=list(interaction.upload_refs) if interaction else [],
                ),
            )
            if context_event is not None:
                timeline_summaries.append(
                    self._timeline_summary(
                        context_event,
                        report_version_id=None,
                        report_version_number=None,
                    )
                )

        new_version = CaseService.generate_report_version(
            db=self.db,
            case_uuid=case_uuid,
            limit_per_source=limit_per_source,
            trigger_message_id=(
                trigger_message.id if trigger_message is not None else None
            ),
        )

        analysis_event = self._append_timeline_safe(
            case_uuid,
            event_type="analysis_updated",
            title="Analysis updated",
            step_type=inspection.current_step_type,
            details=(
                f"New immutable analysis report version {new_version.version_number} "
                f"created via compatibility analysis refresh."
            ),
            references=CaseTimelineEventReferences(
                report_version_id=new_version.id,
                report_version_number=new_version.version_number,
                follow_up_message_ids=(
                    [trigger_message.id] if trigger_message is not None else []
                ),
                upload_refs=list(interaction.upload_refs) if interaction else [],
            ),
        )
        if analysis_event is not None:
            timeline_summaries.append(
                self._timeline_summary(
                    analysis_event,
                    report_version_id=new_version.id,
                    report_version_number=new_version.version_number,
                )
            )

        post_inspection = self._inspect_workspace(case_uuid)
        available_actions = self.evaluate_action_availability(post_inspection)

        analysis_update = AnalysisUpdateResult(
            steward_action_label=None,
            interaction_saved=interaction_saved,
            prior_conversation_preserved=True,
            facts_updated=facts_updated,
            ai_response_persisted=False,
            prior_report_version_id=prior_version_id,
            prior_report_version_number=prior_version_number,
            new_report_version_id=new_version.id,
            new_report_version_number=new_version.version_number,
            is_current_analysis=True,
            older_versions_retained=True,
            trigger_message_id=(
                trigger_message.id if trigger_message is not None else None
            ),
            trigger_metadata=trigger_metadata,
            timeline_events=timeline_summaries,
            message=(
                f"Analysis refreshed. New report version "
                f"{new_version.version_number} is current; prior versions retained. "
                f"Prefer POST /interactions for steward chat."
            ),
        )

        return WorkspaceActionResponse(
            case_uuid=case_uuid,
            action="save_and_update_analysis",
            status="completed",
            message=analysis_update.message,
            steward_action_label=None,
            available_actions=available_actions,
            prior_report_version_id=prior_version_id,
            prior_report_version_number=prior_version_number,
            current_report_version_id=new_version.id,
            current_report_version_number=new_version.version_number,
            analysis_update=analysis_update,
            grievance_generation=None,
            timeline_events=timeline_summaries,
            interaction_accepted_for_later_phases=interaction is not None,
        )

    def generate_grievance(
        self,
        case_uuid: str,
        interaction: WorkspaceInteractionPayload | None = None,
    ) -> WorkspaceActionResponse:
        """Generate Grievance — contract + prerequisite inspection only until W5."""
        try:
            inspection = self._inspect_workspace(case_uuid)
        except CaseNotFoundError:
            return self._case_not_found_response(
                case_uuid, "generate_grievance", interaction
            )

        available_actions = self.evaluate_action_availability(inspection)
        gen_availability = next(
            a for a in available_actions if a.action == "generate_grievance"
        )

        if not gen_availability.available:
            return WorkspaceActionResponse(
                case_uuid=case_uuid,
                action="generate_grievance",
                status="prerequisites_not_met",
                message=gen_availability.reason
                or "Generate Grievance prerequisites not met.",
                steward_action_label="Generate Grievance",
                available_actions=available_actions,
                missing_prerequisites=list(gen_availability.missing_prerequisites),
                prior_report_version_id=inspection.latest_report_version_id,
                prior_report_version_number=inspection.latest_report_version_number,
                current_report_version_id=inspection.latest_report_version_id,
                current_report_version_number=inspection.latest_report_version_number,
                grievance_generation=GrievanceGenerationResult(
                    step_type=inspection.current_step_type,
                    template_id=inspection.template_id,
                ),
                interaction_accepted_for_later_phases=interaction is not None,
            )

        return WorkspaceActionResponse(
            case_uuid=case_uuid,
            action="generate_grievance",
            status="not_implemented_in_w1",
            message=(
                "Generate Grievance execution is deferred to Phase W5. "
                "Case chat continues via POST /cases/{case_uuid}/interactions."
            ),
            steward_action_label="Generate Grievance",
            available_actions=available_actions,
            missing_prerequisites=[
                WorkspaceActionPrerequisite(
                    code="action_not_implemented_in_w1",
                    message="generate_grievance execution is deferred to Phase W5.",
                    resolved_in_phase="W5",
                )
            ],
            prior_report_version_id=inspection.latest_report_version_id,
            prior_report_version_number=inspection.latest_report_version_number,
            current_report_version_id=inspection.latest_report_version_id,
            current_report_version_number=inspection.latest_report_version_number,
            grievance_generation=GrievanceGenerationResult(
                step_type=inspection.current_step_type,
                template_id=inspection.template_id,
            ),
            interaction_accepted_for_later_phases=interaction is not None,
        )

    def evaluate_action_availability(
        self,
        inspection: _WorkspaceInspection,
    ) -> list[WorkspaceActionAvailability]:
        """Compute availability for workspace actions from case state."""
        return [
            self._availability_save_and_update(inspection),
            self._availability_generate_grievance(inspection),
        ]

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    def _merge_fact_updates(
        self,
        case_uuid: str,
        interaction: WorkspaceInteractionPayload,
    ) -> bool:
        if not interaction.fact_updates:
            return False
        case_row = CaseService._get_case_row(self.db, case_uuid)
        if case_row is None:
            raise CaseNotFoundError(case_uuid)
        merged = dict(case_row.known_facts or {})
        merged.update(interaction.fact_updates)
        CaseService.update_known_facts(self.db, case_uuid, merged)
        return True

    @staticmethod
    def _build_interaction_content(interaction: WorkspaceInteractionPayload) -> str:
        parts: list[str] = []
        if interaction.message and interaction.message.strip():
            parts.append(interaction.message.strip())
        if interaction.clarification and interaction.clarification.strip():
            parts.append(f"Clarification: {interaction.clarification.strip()}")
        return "\n\n".join(parts)

    def _enrich_interaction_message_metadata(
        self,
        case_uuid: str,
        user_message: CaseMessage,
        interaction: WorkspaceInteractionPayload,
        *,
        facts_updated: bool,
    ) -> dict:
        """Attach asset/fact/workflow metadata to the persisted steward message."""
        meta = dict(user_message.message_metadata or {})
        meta.update(
            {
                "intent": CASE_INTERACTION_INTENT,
                "trigger": CASE_INTERACTION_TRIGGER,
                "workflow": "ai_first_case_interaction",
                "source": interaction.source,
                "analysis_auto_refreshed": True,
            }
        )
        if interaction.clarification and interaction.clarification.strip():
            meta["clarification"] = interaction.clarification.strip()
        if interaction.upload_refs:
            meta["upload_refs"] = list(interaction.upload_refs)
            resolved = self._assets.resolve_upload_refs_for_context(
                case_uuid,
                list(interaction.upload_refs),
            )
            meta["uploaded_files"] = resolved
            meta["case_asset_uuids"] = [
                item["asset_uuid"] for item in resolved if item.get("asset_uuid")
            ]
        if interaction.fact_updates:
            meta["fact_updates"] = dict(interaction.fact_updates)
            meta["facts_updated"] = facts_updated
        if interaction.pinned_report_version is not None:
            meta["pinned_report_version"] = interaction.pinned_report_version

        user_message.message_metadata = meta
        self.db.add(user_message)
        self.db.commit()
        self.db.refresh(user_message)
        return meta

    def _persist_context_only_message(
        self,
        case_uuid: str,
        interaction: WorkspaceInteractionPayload,
        *,
        facts_updated: bool,
    ) -> tuple[CaseMessage, dict]:
        if facts_updated and interaction.upload_refs:
            content = "Context updated via case interaction (facts and asset refs)."
        elif facts_updated:
            content = "Known facts updated via case interaction."
        else:
            content = "Asset references added via case interaction."

        trigger_metadata: dict = {
            "intent": CASE_INTERACTION_INTENT,
            "trigger": CASE_INTERACTION_TRIGGER,
            "workflow": "ai_first_case_interaction",
            "source": interaction.source,
            "analysis_auto_refreshed": True,
        }
        if interaction.upload_refs:
            trigger_metadata["upload_refs"] = list(interaction.upload_refs)
            resolved = self._assets.resolve_upload_refs_for_context(
                case_uuid, list(interaction.upload_refs)
            )
            trigger_metadata["uploaded_files"] = resolved
            trigger_metadata["case_asset_uuids"] = [
                item["asset_uuid"] for item in resolved if item.get("asset_uuid")
            ]
        if interaction.fact_updates:
            trigger_metadata["fact_updates"] = dict(interaction.fact_updates)
            trigger_metadata["facts_updated"] = facts_updated

        message = CaseService.add_message(
            db=self.db,
            case_uuid=case_uuid,
            role="user",
            content=content,
            metadata=trigger_metadata,
        )
        return message, trigger_metadata

    # ------------------------------------------------------------------
    # Compatibility interaction persistence (save_and_update_analysis)
    # ------------------------------------------------------------------

    def _persist_interaction(
        self,
        case_uuid: str,
        interaction: WorkspaceInteractionPayload | None,
    ) -> tuple[CaseMessage | None, bool, bool, dict | None]:
        """Persist optional interaction for compatibility analysis refresh."""
        if interaction is None:
            return None, False, False, None

        has_text = bool(
            (interaction.message and interaction.message.strip())
            or (interaction.clarification and interaction.clarification.strip())
        )
        has_uploads = bool(interaction.upload_refs)
        has_facts = bool(interaction.fact_updates)

        if not has_text and not has_uploads and not has_facts:
            return None, False, False, None

        facts_updated = False
        if has_facts and interaction.fact_updates is not None:
            facts_updated = self._merge_fact_updates(case_uuid, interaction)

        content_parts: list[str] = []
        if interaction.message and interaction.message.strip():
            content_parts.append(interaction.message.strip())
        if interaction.clarification and interaction.clarification.strip():
            content_parts.append(
                f"Clarification: {interaction.clarification.strip()}"
            )
        if not content_parts:
            if has_facts and has_uploads:
                content_parts.append(
                    "Context updated via compatibility analysis refresh "
                    "(facts and upload refs)."
                )
            elif has_facts:
                content_parts.append(
                    "Known facts updated via compatibility analysis refresh."
                )
            else:
                content_parts.append(
                    "Upload references added via compatibility analysis refresh."
                )

        trigger_metadata: dict = {
            "intent": UPDATE_ANALYSIS_INTENT,
            "action": INTERNAL_SAVE_AND_UPDATE_ACTION,
            "source": interaction.source,
            "trigger": UPDATE_ANALYSIS_TRIGGER,
            "compatibility_path": True,
        }
        if interaction.clarification and interaction.clarification.strip():
            trigger_metadata["clarification"] = interaction.clarification.strip()
        if interaction.upload_refs:
            trigger_metadata["upload_refs"] = list(interaction.upload_refs)
            resolved = self._assets.resolve_upload_refs_for_context(
                case_uuid, list(interaction.upload_refs)
            )
            trigger_metadata["uploaded_files"] = resolved
            trigger_metadata["case_asset_uuids"] = [
                item["asset_uuid"]
                for item in resolved
                if item.get("asset_uuid")
            ]
        if interaction.fact_updates:
            trigger_metadata["fact_updates"] = dict(interaction.fact_updates)
        if interaction.pinned_report_version is not None:
            trigger_metadata["pinned_report_version"] = (
                interaction.pinned_report_version
            )

        message = CaseService.add_message(
            db=self.db,
            case_uuid=case_uuid,
            role="user",
            content="\n\n".join(content_parts),
            metadata=trigger_metadata,
        )
        return message, True, facts_updated, trigger_metadata

    def _append_timeline_safe(
        self,
        case_uuid: str,
        *,
        event_type: str,
        title: str,
        step_type: StepType | None,
        details: str | None,
        references: CaseTimelineEventReferences,
    ) -> CaseTimelineEvent | None:
        """Append one timeline event; skip only if case row is missing."""
        try:
            return self._progression.add_timeline_event(
                case_uuid,
                event_type=event_type,  # type: ignore[arg-type]
                title=title,
                step_type=step_type,
                details=details,
                references=references,
            )
        except (CaseStepProgressionNotFoundError, CaseStepNotFoundError):
            return None

    @staticmethod
    def _timeline_summary(
        event: CaseTimelineEvent,
        *,
        report_version_id: int | None,
        report_version_number: int | None,
    ) -> WorkspaceTimelineEventSummary:
        return WorkspaceTimelineEventSummary(
            event_id=event.event_id,
            event_type=event.event_type,
            title=event.title,
            event_timestamp=event.event_timestamp,
            report_version_id=report_version_id
            or event.references.report_version_id,
            report_version_number=report_version_number
            or event.references.report_version_number,
        )

    @staticmethod
    def _message_summary(
        message: CaseMessage | None,
    ) -> CaseInteractionMessageSummary | None:
        if message is None:
            return None
        return CaseInteractionMessageSummary(
            id=message.id,
            role=message.role,
            content=message.content,
            metadata=message.message_metadata,
            created_at=message.created_at,
        )

    @staticmethod
    def _generate_grievance_available(
        available_actions: list[WorkspaceActionAvailability],
    ) -> bool:
        for action in available_actions:
            if action.action == "generate_grievance":
                return bool(action.available)
        return False

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _availability_save_and_update(
        inspection: _WorkspaceInspection,
    ) -> WorkspaceActionAvailability:
        """Internal compatibility analysis refresh — not steward-visible."""
        missing: list[WorkspaceActionPrerequisite] = []
        if inspection.case_status == "closed":
            missing.append(
                WorkspaceActionPrerequisite(
                    code="case_closed_requires_reopen",
                    message=(
                        "Case is closed. Reopen the case before continuing "
                        "case interactions."
                    ),
                )
            )
            return WorkspaceActionAvailability(
                action="save_and_update_analysis",
                available=False,
                steward_visible=False,
                reason="Case is closed; reopen required.",
                missing_prerequisites=missing,
                current_step_type=inspection.current_step_type,
                template_id=inspection.template_id,
                template_availability=inspection.template_availability_status,  # type: ignore[arg-type]
            )

        return WorkspaceActionAvailability(
            action="save_and_update_analysis",
            available=True,
            steward_visible=False,
            reason=(
                "Internal/compatibility analysis refresh available. "
                "Steward chat should use POST /cases/{case_uuid}/interactions; "
                "do not render a separate analysis-refresh button."
            ),
            current_step_type=inspection.current_step_type,
            template_id=inspection.template_id,
            template_availability=inspection.template_availability_status,  # type: ignore[arg-type]
        )

    @staticmethod
    def _availability_generate_grievance(
        inspection: _WorkspaceInspection,
    ) -> WorkspaceActionAvailability:
        """generate_grievance prerequisites: analysis, progression, buildable template."""
        missing: list[WorkspaceActionPrerequisite] = []

        if inspection.case_status == "closed":
            missing.append(
                WorkspaceActionPrerequisite(
                    code="case_closed_requires_reopen",
                    message="Case is closed. Reopen before generating a grievance.",
                )
            )

        if not inspection.has_analysis_report:
            missing.append(
                WorkspaceActionPrerequisite(
                    code="analysis_report_required",
                    message=(
                        "Generate Grievance requires a current analysis report version."
                    ),
                )
            )

        if not inspection.has_step_progression:
            missing.append(
                WorkspaceActionPrerequisite(
                    code="step_progression_required",
                    message=(
                        "Generate Grievance requires initialized step progression. "
                        "Progression init is deferred to Phase W4."
                    ),
                    resolved_in_phase="W4",
                    details={"note": "step_progression_init_deferred_to_w4"},
                )
            )
            missing.append(
                WorkspaceActionPrerequisite(
                    code="step_progression_init_deferred_to_w4",
                    message=(
                        "Step progression initialization on case create is deferred "
                        "to Phase W4."
                    ),
                    resolved_in_phase="W4",
                )
            )

        step_type = inspection.current_step_type
        template_status = inspection.template_availability_status
        template_id = inspection.template_id

        if inspection.has_step_progression and step_type is not None:
            if step_type == "step_1_initial":
                missing.append(
                    WorkspaceActionPrerequisite(
                        code="template_unavailable",
                        message=(
                            "Step 1 initial filing template is not available "
                            "(unconfirmed_pending_steward_confirmation)."
                        ),
                        details={"step_type": step_type},
                    )
                )
            elif step_type == "step_3_appeal":
                missing.append(
                    WorkspaceActionPrerequisite(
                        code="template_deferred",
                        message=(
                            "Step 3 appeal template is deferred "
                            "(deferred_separate_form_required)."
                        ),
                        details={"step_type": step_type},
                    )
                )
            elif not inspection.template_available:
                missing.append(
                    WorkspaceActionPrerequisite(
                        code="template_unavailable",
                        message=(
                            f"No buildable official template for current step "
                            f"{step_type}."
                        ),
                        details={
                            "step_type": step_type,
                            "availability_status": template_status,
                        },
                    )
                )

        available = len(missing) == 0
        if available:
            reason = (
                "Prerequisites represented as met for Generate Grievance "
                "(Step 2 template available). Execution deferred to W5."
            )
        else:
            reason = "One or more Generate Grievance prerequisites are missing."

        return WorkspaceActionAvailability(
            action="generate_grievance",
            available=available,
            steward_visible=True,
            reason=reason,
            missing_prerequisites=missing,
            current_step_type=step_type,
            template_id=template_id,
            template_availability=template_status,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def _inspect_workspace(self, case_uuid: str) -> _WorkspaceInspection:
        case = CaseService.get_case(self.db, case_uuid)
        versions = sorted(case.report_versions, key=lambda v: v.version_number)
        latest: CaseReportVersion | None = versions[-1] if versions else None

        current_step_type: StepType | None = None
        template_id: str | None = None
        template_status: str | None = None
        template_available = False
        has_progression = False

        try:
            state = self._progression.get_progression(case_uuid)
            has_progression = True
            current_step_type = state.current_step_type
            availability = CaseStepProgressionService.get_step_template_availability(
                current_step_type
            )
            template_id = availability.template_id
            template_status = availability.availability_status
            template_available = availability.template_available
        except CaseStepProgressionNotFoundError:
            has_progression = False

        return _WorkspaceInspection(
            case=case,
            has_analysis_report=latest is not None,
            latest_report_version_id=latest.id if latest else None,
            latest_report_version_number=latest.version_number if latest else None,
            has_step_progression=has_progression,
            current_step_type=current_step_type,
            template_id=template_id,
            template_availability_status=template_status,
            template_available=template_available,
            case_status=str(case.status or "open"),
        )

    @staticmethod
    def _case_not_found_response(
        case_uuid: str,
        action: WorkspaceActionType,
        interaction: WorkspaceInteractionPayload | None,
    ) -> WorkspaceActionResponse:
        return WorkspaceActionResponse(
            case_uuid=case_uuid,
            action=action,
            status="case_not_found",
            message=f"Case not found: {case_uuid}",
            steward_action_label=(
                "Generate Grievance" if action == "generate_grievance" else None
            ),
            missing_prerequisites=[
                WorkspaceActionPrerequisite(
                    code="case_not_found",
                    message=f"No grievance case exists for uuid {case_uuid}.",
                )
            ],
            interaction_accepted_for_later_phases=interaction is not None,
        )
