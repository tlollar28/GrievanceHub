"""HTTP client helper for saved cases UI (Phase 1.4F).

Thin wrapper around Phase 1.4E ``/cases/saved/*`` endpoints. Manual UI clicks and
future AI commands must use the same backend reopen workflow via
``SavedCaseService`` — this client does not implement a separate reopen path.

No OpenAI, no PDF/DOCX export, no filled-form disk output.
"""

from __future__ import annotations

from typing import Literal

import requests

from app.schemas.case_step_progression_schema import StepType
from app.schemas.saved_case_schema import (
    OpenCaseResponse,
    ReopenCaseResponse,
    ReopenSource,
    SavedCaseAction,
    SavedCaseListResponse,
    SavedCaseStatusFilter,
    SavedCaseSummary,
    SavedCaseTimelineResponse,
)

SavedCaseClickAction = Literal["open_case", "reopen_case"]


class SavedCaseApiError(Exception):
    """Raised when a saved-case API request fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Saved case API error {status_code}: {detail}")


def resolve_case_click_action(summary: SavedCaseSummary) -> SavedCaseClickAction:
    """Determine which backend action a steward row/card click should invoke.

    Closed workspaces use ``reopen_case`` (same path as future AI-command reopen).
    Active workspaces use ``open_case``.
    """
    if summary.workspace_status == "closed":
        return "reopen_case"
    return "open_case"


class SavedCaseApiClient:
    """Frontend-ready client for saved case list, open/reopen, and timeline."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        session: requests.Session | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout_seconds

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        response = self._session.request(
            method,
            self._url(path),
            params=params,
            json=json_body,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            detail = response.text
            try:
                payload = response.json()
                if isinstance(payload, dict) and "detail" in payload:
                    detail = str(payload["detail"])
            except ValueError:
                pass
            raise SavedCaseApiError(response.status_code, detail)
        return response.json()

    def list_saved_cases(
        self,
        *,
        status: SavedCaseStatusFilter = "all",
        step: StepType | None = None,
        search: str | None = None,
        order: Literal["newest_first", "oldest_first"] = "newest_first",
    ) -> SavedCaseListResponse:
        params: dict[str, str] = {"status": status, "order": order}
        if step is not None:
            params["step"] = step
        if search:
            params["search"] = search
        payload = self._request("GET", "/cases/saved", params=params)
        return SavedCaseListResponse.model_validate(payload)

    def get_saved_case(self, case_uuid: str) -> SavedCaseSummary:
        payload = self._request("GET", f"/cases/saved/{case_uuid}")
        return SavedCaseSummary.model_validate(payload)

    def open_case(
        self,
        case_uuid: str,
        *,
        source: ReopenSource = "manual_ui",
    ) -> OpenCaseResponse:
        payload = self._request(
            "POST",
            f"/cases/saved/{case_uuid}/open",
            json_body={"source": source},
        )
        return OpenCaseResponse.model_validate(payload)

    def reopen_case(
        self,
        case_uuid: str,
        *,
        reason: str | None = None,
        source: ReopenSource = "manual_ui",
    ) -> ReopenCaseResponse:
        body: dict[str, str] = {"source": source}
        if reason is not None:
            body["reason"] = reason
        payload = self._request(
            "POST",
            f"/cases/saved/{case_uuid}/reopen",
            json_body=body,
        )
        return ReopenCaseResponse.model_validate(payload)

    def get_timeline(
        self,
        case_uuid: str,
        *,
        order: Literal["oldest_first", "newest_first"] = "oldest_first",
    ) -> SavedCaseTimelineResponse:
        payload = self._request(
            "GET",
            f"/cases/saved/{case_uuid}/timeline",
            params={"order": order},
        )
        return SavedCaseTimelineResponse.model_validate(payload)

    def activate_case(
        self,
        summary: SavedCaseSummary,
        *,
        reason: str | None = None,
        source: ReopenSource = "manual_ui",
    ) -> OpenCaseResponse | ReopenCaseResponse:
        """Execute the unified click workflow for a saved case row/card."""
        action = resolve_case_click_action(summary)
        if action == "reopen_case":
            return self.reopen_case(summary.case_uuid, reason=reason, source=source)
        return self.open_case(summary.case_uuid, source=source)

    def run_action(
        self,
        case_uuid: str,
        action: SavedCaseAction,
        *,
        reason: str | None = None,
        source: ReopenSource = "manual_ui",
    ) -> OpenCaseResponse | ReopenCaseResponse | SavedCaseTimelineResponse:
        """Invoke an explicit saved-case action from a row/card button."""
        if action == "open_case":
            return self.open_case(case_uuid, source=source)
        if action == "reopen_case":
            return self.reopen_case(case_uuid, reason=reason, source=source)
        if action == "view_timeline":
            return self.get_timeline(case_uuid)
        raise ValueError(f"Action {action!r} is not handled by SavedCaseApiClient")
