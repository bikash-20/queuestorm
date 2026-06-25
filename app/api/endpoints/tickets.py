"""POST /sort-ticket — the primary classification endpoint."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request, status

from app.core.logging import get_logger
from app.models import ClassificationResponse, TicketRequest
from app.services.pipeline import classify_ticket

router = APIRouter(tags=["tickets"])
logger = get_logger(__name__)


@router.post(
    "/sort-ticket",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify a single customer ticket",
)
async def sort_ticket(payload: TicketRequest, request: Request) -> ClassificationResponse:
    """Accept a CRM ticket and return a structured classification."""
    start = time.perf_counter()
    log = logger.bind(
        ticket_id=payload.ticket_id,
        request_id=getattr(request.state, "request_id", None),
    )
    log.info(
        "ticket.received",
        channel=str(payload.channel) if payload.channel else None,
        message_length=len(payload.message),
    )

    response = classify_ticket(payload)

    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "ticket.responded",
        elapsed_ms=round(elapsed_ms, 2),
        case_type=response.case_type.value,
        severity=response.severity.value,
    )
    return response
