"""
Custom exception hierarchy.

Defining typed exceptions lets us map error → HTTP status code in the global
exception handler, keeping the endpoint code clean and never leaking Python
tracebacks to the client.
"""

from __future__ import annotations


class QueueStormError(Exception):
    """Base exception for all QueueStorm errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ClassificationError(QueueStormError):
    """Raised when the classifier cannot produce a valid result."""

    status_code = 500
    error_code = "classification_failed"


class SafetyViolationError(QueueStormError):
    """Raised when the safety filter refuses to produce a safe summary."""

    status_code = 422
    error_code = "safety_violation"


class ClassifierUnavailableError(QueueStormError):
    """Raised when the configured classifier backend cannot be loaded."""

    status_code = 503
    error_code = "classifier_unavailable"


class ValidationError(QueueStormError):
    """Raised for invalid request payloads beyond Pydantic validation."""

    status_code = 400
    error_code = "invalid_request"
