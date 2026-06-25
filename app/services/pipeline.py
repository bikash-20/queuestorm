"""End-to-end classification pipeline.

Orchestrates:
    SafetyInspector  →  ClassifierStrategy  →  SummaryGenerator  →  SafetyFilter

Returns a fully-formed `ClassificationResponse` ready to serialize.

The controller (endpoint) only calls `classify_ticket(...)`. Adding a new
strategy, summary template, or safety rule requires zero changes here.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.models import (
    CaseType,
    ClassificationResponse,
    Department,
    Severity,
    TicketRequest,
)
from app.services.classifier import get_classifier
from app.services.safety import get_safety_inspector
from app.services.summary import get_summary_generator

logger = get_logger(__name__)


def classify_ticket(request: TicketRequest) -> ClassificationResponse:
    """Run the full pipeline and return the API-ready response."""
    log = logger.bind(ticket_id=request.ticket_id, locale=str(request.locale))

    # 1. Input inspection (does NOT block; just informs confidence).
    inspector = get_safety_inspector()
    verdict = inspector.inspect(request.message)
    log = log.bind(risk_score=verdict.risk_score, reasons=list(verdict.reasons))

    # 2. Classification (strategy).
    classifier = get_classifier()
    result = classifier.classify(request.message, locale=str(request.locale) if request.locale else None)
    log = log.bind(case_type=result.case_type.value, severity=result.severity.value)

    # 3. Confidence adjustment — high input risk slightly boosts confidence
    #    that human review is needed (already covered by case_type=phishing,
    #    but stays correct for other risky inputs).
    confidence = result.confidence
    if verdict.is_high_risk:
        confidence = max(confidence, 0.9)

    # 4. Summary generation (with safety pass).
    summary = get_summary_generator().build(
        case_type=result.case_type,
        message=request.message,
    )

    # 5. Decide human review — phishing or critical → always true.
    human_review_required = (
        result.case_type == CaseType.PHISHING
        or result.severity == Severity.CRITICAL
        or verdict.is_high_risk
    )

    response = ClassificationResponse(
        ticket_id=request.ticket_id,
        case_type=result.case_type,
        severity=result.severity,
        department=result.department,
        agent_summary=summary,
        human_review_required=human_review_required,
        confidence=round(confidence, 3),
    )
    log.info("ticket.classified", **response.model_dump(mode="json"))
    return response
