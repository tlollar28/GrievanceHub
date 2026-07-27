"""Stateless grievance-step rules and official-form draft helpers.

This module deliberately owns no case state. Persisted step records remain the
responsibility of ``CaseStepProgressionPersistenceService`` and the explicit
workflow finite-state machine remains the responsibility of
``CaseWorkflowService``.
"""

from __future__ import annotations

from app.schemas.case_step_progression_schema import (
    CaseStepOutcomeRecord,
    CaseStepProgressionState,
    CaseTimelineEvent,
    StepTemplateAvailabilityInfo,
    StepType,
)
from app.schemas.grievance_form_draft_schema import (
    GrievanceFormDraftCaseContext,
    GrievanceFormDraftInput,
)
from app.services.case_step_progression_errors import CaseStepProgressionError
from app.services.grievance_form_draft_builder import build_grievance_form_draft
from app.services.grievance_template_registry import (
    OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1,
    OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2,
    get_grievance_template_by_id,
    list_registered_grievance_templates,
)

STEP_NUMBER_BY_TYPE: dict[StepType, int] = {
    "step_1_initial": 1,
    "step_2_appeal": 2,
    "step_3_appeal": 3,
}

NEXT_STEP_BY_TYPE: dict[StepType, StepType | None] = {
    "step_1_initial": "step_2_appeal",
    "step_2_appeal": "step_3_appeal",
    "step_3_appeal": None,
}

RESOLVED_OUTCOME_TYPES = frozenset(
    {"resolved", "granted", "settled", "closed_no_appeal", "withdrawn"}
)


def get_step_number(step_type: StepType) -> int:
    """Return the stable one-based number for a persisted grievance step."""
    return STEP_NUMBER_BY_TYPE[step_type]


def get_step_template_availability(
    step_type: StepType,
) -> StepTemplateAvailabilityInfo:
    """Return whether an official template is currently buildable for a step."""
    if step_type == "step_1_initial":
        template = OFFICIAL_GRIEVANCE_WORKSHEET_STEP_1
        return StepTemplateAvailabilityInfo(
            step_type=step_type,
            template_available=True,
            template_id=template.template_id,
            availability_status="available",
            notes=["The official Step 1 grievance worksheet is registered."],
        )

    if step_type == "step_3_appeal":
        return StepTemplateAvailabilityInfo(
            step_type=step_type,
            template_available=False,
            template_id=None,
            availability_status="deferred_separate_form_required",
            notes=[
                "Step 3 appeal/out-of-building template is deferred — separate form required later."
            ],
        )

    template = OFFICIAL_STANDARD_GRIEVANCE_FORM_STEP_2
    return StepTemplateAvailabilityInfo(
        step_type=step_type,
        template_available=True,
        template_id=template.template_id,
        availability_status="available",
        notes=["The official standard Step 2 grievance form is registered."],
    )


def list_buildable_template_ids_for_step(step_type: StepType) -> list[str]:
    """Return registered template IDs buildable for a step."""
    availability = get_step_template_availability(step_type)
    if not availability.template_available or availability.template_id is None:
        return []
    return [availability.template_id]


def build_step_form_draft(
    case_uuid: str,
    step_type: StepType,
    draft_input: GrievanceFormDraftInput,
    *,
    template_id: str | None = None,
):
    """Build a Step 1 or Step 2 draft without storing progression state."""
    availability = get_step_template_availability(step_type)
    if not availability.template_available:
        raise CaseStepProgressionError(
            f"No buildable official template for {step_type}: "
            f"{availability.availability_status}"
        )

    resolved_template_id = template_id or availability.template_id
    if resolved_template_id is None:
        raise CaseStepProgressionError(f"No template id resolved for {step_type}.")

    if resolved_template_id not in list_buildable_template_ids_for_step(step_type):
        registered = get_grievance_template_by_id(resolved_template_id)
        if registered is None:
            raise CaseStepProgressionError(
                f"Unknown template id for step draft: {resolved_template_id}"
            )
        raise CaseStepProgressionError(
            f"Template {resolved_template_id} is not buildable for {step_type}."
        )

    case_context = draft_input.case_context or GrievanceFormDraftCaseContext()
    case_context.case_uuid = case_uuid
    normalized_input = draft_input.model_copy(update={"case_context": case_context})
    return build_grievance_form_draft(resolved_template_id, normalized_input)


def sort_timeline_oldest_first(
    state: CaseStepProgressionState,
) -> list[CaseTimelineEvent]:
    return sorted(state.timeline, key=lambda event: event.event_timestamp)


def sort_timeline_newest_first(
    state: CaseStepProgressionState,
) -> list[CaseTimelineEvent]:
    return sorted(
        state.timeline,
        key=lambda event: event.event_timestamp,
        reverse=True,
    )


def get_prior_step_outcome(
    state: CaseStepProgressionState,
    step_type: StepType,
) -> CaseStepOutcomeRecord | None:
    stage = next((item for item in state.steps if item.step_type == step_type), None)
    if stage is None or not stage.outcomes:
        return None
    return stage.outcomes[-1]


def registered_templates_for_step(step_type: StepType) -> list[str]:
    """List registered template IDs whose step level matches the requested step."""
    return [
        template.template_id
        for template in list_registered_grievance_templates()
        if template.step_level == step_type
    ]
