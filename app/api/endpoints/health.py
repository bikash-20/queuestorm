"""GET /health — production-grade health probe.

Reports:
    * service identity & version
    * uptime since process start
    * RSS memory vs threshold
    * classifier readiness

Returns HTTP 200 even on `degraded` (e.g. classifier warming up) so that
load balancers do not pull the pod out of rotation during transient issues.
Returns HTTP 503 only if the process itself cannot serve requests.
"""
from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Request, Response, status

from app import __version__
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import HealthStatus
from app.services.classifier import classifier_ready, get_classifier

router = APIRouter(tags=["health"])
logger = get_logger(__name__)

# Process start time (epoch seconds)
_PROCESS_STARTED_AT = time.time()
_MEMORY_THRESHOLD_MB = float(os.getenv("MAX_MEMORY_MB", "512"))


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Deep health probe (uptime, memory, classifier readiness)",
)
async def health(request: Request, response: Response) -> HealthStatus:
    settings = get_settings()
    classifier = get_classifier()
    classifier_ok = classifier_ready(classifier)

    process = psutil.Process(os.getpid())
    rss_mb = process.memory_info().rss / (1024 * 1024)

    degraded = (not classifier_ok) or rss_mb > _MEMORY_THRESHOLD_MB
    if degraded:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning(
            "health.degraded",
            classifier_ready=classifier_ok,
            rss_mb=round(rss_mb, 1),
            threshold_mb=_MEMORY_THRESHOLD_MB,
        )

    body = HealthStatus(
        status="ok" if not degraded else "degraded",
        service=settings.app_name,
        version=__version__,
        uptime_seconds=round(time.time() - _PROCESS_STARTED_AT, 2),
        classifier_backend=classifier.name,
        classifier_ready=classifier_ok,
        memory_rss_mb=round(rss_mb, 1),
        memory_threshold_mb=_MEMORY_THRESHOLD_MB,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return body
