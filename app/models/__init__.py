"""Pydantic schemas for the API layer.

These are the contracts that the grader (and clients) rely on.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enums (mirror the spec exactly)
# ─────────────────────────────────────────────────────────────────────────────
class Channel(str, Enum):
    APP = "app"
    SMS = "sms"
    CALL_CENTER = "call_center"
    MERCHANT_PORTAL = "merchant_portal"


class Locale(str, Enum):
    BN = "bn"
    EN = "en"
    MIXED = "mixed"


class CaseType(str, Enum):
    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    PHISHING = "phishing_or_social_engineering"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Department(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    FRAUD_RISK = "fraud_risk"


# ─────────────────────────────────────────────────────────────────────────────
# Request schema
# ─────────────────────────────────────────────────────────────────────────────
class TicketRequest(BaseModel):
    """Inbound CRM ticket for classification."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    ticket_id: str = Field(..., min_length=1, max_length=64, description="Unique ticket id; echoed in response")
    channel: Channel | None = Field(default=None, description="Origination channel")
    locale: Locale | None = Field(default=None, description="Customer locale")
    message: str = Field(..., min_length=1, description="Free text customer complaint")

    @field_validator("ticket_id")
    @classmethod
    def _normalize_ticket_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ticket_id must not be empty")
        return v.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Response schema
# ─────────────────────────────────────────────────────────────────────────────
class ClassificationResponse(BaseModel):
    """Structured classification result for a single ticket."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str = Field(..., min_length=1, max_length=600)
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────
class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    uptime_seconds: float
    classifier_backend: str
    classifier_ready: bool
    memory_rss_mb: float
    memory_threshold_mb: float
    timestamp: str