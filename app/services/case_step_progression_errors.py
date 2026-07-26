"""Shared errors for persisted grievance-step progression."""


class CaseStepProgressionNotFoundError(Exception):
    """Raised when no persisted progression exists for a case UUID."""


class CaseStepNotFoundError(Exception):
    """Raised when a requested persisted step is not present on a case."""


class CaseStepProgressionError(Exception):
    """Raised for invalid persisted step-progression operations."""
