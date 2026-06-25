"""Summary generator.

Produces a 1–2 sentence neutral summary an agent can read in ~2 seconds.

Design:
    * Template-based with extracted hints (amount, recipient hints, etc.)
    * Always passes through the SafetyFilter before being returned.
    * Bounded length — never exceeds ~280 chars in practice.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from app.models import CaseType
from app.services.safety import SafetyFilter, get_safety_filter

_AMOUNT_RE = re.compile(
    r"(?P<amt>\b\d[\d,]{0,9}\s?(?:taka|bdt|tk|usd|inr|rs|rupees?|\$|৳)?\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SummaryTemplate:
    case_type: CaseType
    single: str
    detail: str


_TEMPLATES: dict[CaseType, SummaryTemplate] = {
    CaseType.WRONG_TRANSFER: SummaryTemplate(
        CaseType.WRONG_TRANSFER,
        "Customer reports sending money to the wrong recipient.",
        "Customer reports sending {amount} to the wrong recipient and asks for recovery.",
    ),
    CaseType.PAYMENT_FAILED: SummaryTemplate(
        CaseType.PAYMENT_FAILED,
        "Customer reports a failed payment.",
        "Customer reports a failed payment and is concerned about a possible deduction.",
    ),
    CaseType.REFUND_REQUEST: SummaryTemplate(
        CaseType.REFUND_REQUEST,
        "Customer is requesting a refund.",
        "Customer requests a refund for a recent transaction.",
    ),
    CaseType.PHISHING: SummaryTemplate(
        CaseType.PHISHING,
        "Customer reports a suspected phishing or social-engineering attempt.",
        "Customer reports a suspected phishing attempt targeting credentials; agent should follow the fraud playbook.",
    ),
    CaseType.OTHER: SummaryTemplate(
        CaseType.OTHER,
        "Customer reports an issue that does not match a standard category.",
        "Customer reports an app or account issue that needs general assistance.",
    ),
}


class SummaryGenerator:
    """Compose a safe, neutral summary from a classified ticket."""

    def __init__(self, safety: SafetyFilter | None = None) -> None:
        self._safety = safety or get_safety_filter()

    def build(self, *, case_type: CaseType, message: str) -> str:
        template = _TEMPLATES[case_type]
        amount_match = _AMOUNT_RE.search(message)
        amount = amount_match.group("amt").strip() if amount_match else None

        if amount and "{amount}" in template.detail:
            text = template.detail.format(amount=amount)
        else:
            text = template.single

        # Final defense: always run through the safety filter.
        result = self._safety.sanitize(text)
        return result.sanitized_text


@lru_cache(maxsize=1)
def get_summary_generator() -> SummaryGenerator:
    return SummaryGenerator()
