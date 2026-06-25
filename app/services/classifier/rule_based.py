"""Rule-based classifier.

Deterministic, multilingual (English + Bengali romanized keywords),
explainable, and fast. This is the default backend.

The classifier uses weighted keyword scoring across five buckets:
    phishing, wrong_transfer, payment_failed, refund_request, other.

Highest-scoring bucket wins. Ties broken by priority order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.models import CaseType, Department, Severity
from app.services.classifier.base import Classification, ClassifierStrategy

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Pattern catalogs (English + romanized Bengali)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Pattern:
    pattern: re.Pattern[str]
    weight: float


# We deliberately use word boundaries to avoid false positives
# (e.g. "otp" matching inside unrelated words).
def _w(pat: str, weight: float = 1.0) -> Pattern:
    return Pattern(re.compile(pat, re.IGNORECASE | re.UNICODE), weight)


PHISHING_PATTERNS: list[Pattern] = [
    _w(r"\botp\b", 3.0),
    _w(r"\b(one[- ]time[- ]?password|one[- ]time[- ]?pin)\b", 3.0),
    _w(r"\bpin\b", 2.5),
    _w(r"\bpassword\b", 2.5),
    _w(r"\bcvv\b|\bcard number\b|\bcredit card\b", 2.5),
    _w(r"share (your|the) (otp|pin|password|code)", 4.0),
    _w(r"send (your|the) (otp|pin|password|code)", 4.0),
    _w(r"give (me )?(your|the) (otp|pin|password|code)", 4.0),
    _w(r"verify (your|the) (otp|pin|password)", 3.0),
    _w(r"click (the )?link", 1.5),
    _w(r"phish(ing)?", 4.0),
    _w(r"scam(mer)?", 2.5),
    _w(r"suspicious (call|sms|message|person)", 2.5),
    _w(r"fraud(ulent)?", 2.0),
    _w(r"someone (called|messaged|is asking)", 2.0),
    _w(r"asking for (my )?(otp|pin|password|code)", 3.5),
    _w(r"unknown (number|person|caller)", 1.5),
    _w(r"pretend(ing)? to be (bkash|bank|officer|agent)", 3.0),
    _w(r"reward|prize|lottery|bonus", 1.5),
    # romanized Bengali hints
    _w(r"dhoka|dhokha", 2.0),
    _w(r"pin den|otp den|otp dao", 3.5),
]

WRONG_TRANSFER_PATTERNS: list[Pattern] = [
    _w(r"wrong (number|account|person|recipient)", 4.0),
    _w(r"sent (money|cash|taka|amount) to (the )?wrong", 4.0),
    _w(r"transferred? to (the )?wrong", 3.5),
    _w(r"by mistake", 2.0),
    _w(r"mistakenly sent", 3.5),
    _w(r"accidentally sent", 3.5),
    _w(r"sent to wrong", 3.5),
    _w(r"please (help me )?(get|recover|retrieve) (it|the money|back)", 2.0),
    _w(r"get (it|the money) back", 2.0),
    _w(r"return (the )?money", 2.0),
    _w(r"reverse (the )?transfer", 2.5),
    _w(r"refund", 1.5),  # weak signal — refund request can override
    # romanized Bengali
    _w(r"bhul number|wrong number e|taka pathalam|pathie diyechi", 3.5),
    _w(r"taka ferot|ferot din|taka ulto", 2.0),
]

PAYMENT_FAILED_PATTERNS: list[Pattern] = [
    _w(r"payment failed", 4.0),
    _w(r"transaction failed", 4.0),
    _w(r"transaction (was )?unsuccessful", 3.5),
    _w(r"payment (was )?unsuccessful", 3.5),
    _w(r"failed but (balance|money) (was )?deducted", 5.0),
    _w(r"money (was )?deducted", 3.0),
    _w(r"balance (was )?deducted", 3.0),
    _w(r"amount (was )?deducted", 3.0),
    _w(r"double (charged|deducted)", 3.5),
    _w(r"charged twice", 3.0),
    _w(r"declined", 1.5),
    _w(r"couldn'?t (pay|purchase|complete)", 2.0),
    _w(r"didn'?t (receive|get) (the )?(product|service|item)", 2.5),
    _w(r"but (the )?(order|payment|merchant) (is )?not (received|confirmed|updated)", 2.5),
    _w(r"error (code)?", 1.0),
    _w(r"timeout|timed out", 1.5),
    # romanized Bengali
    _w(r"taka kateche|taka kete geche|kate geche", 3.0),
    _w(r"payment hoyni|transact hoyni|kaj hoyni", 3.5),
]

REFUND_PATTERNS: list[Pattern] = [
    _w(r"refund", 3.0),
    _w(r"please refund", 3.5),
    _w(r"want (my )?money back", 3.0),
    _w(r"i changed my mind", 4.0),
    _w(r"cancel (my )?(order|transaction|purchase)", 2.5),
    _w(r"return (the )?(product|item|order)", 2.0),
    _w(r"not satisfied", 2.0),
    _w(r"dissatisfied", 2.0),
    _w(r"dispute", 2.0),
    # romanized Bengali
    _w(r"taka ferot chai|ferot dia din|return korun", 3.0),
]

OTHER_NEGATIVE_HINTS: list[Pattern] = [
    _w(r"crash(ed|es|ing)?", 2.0),
    _w(r"app (is )?(not )?(working|opening|loading|responding)", 2.0),
    _w(r"can'?t (open|login|access|use) (the )?app", 2.0),
    _w(r"login (problem|issue|error|fail)", 1.5),
    _w(r"(otp|pin).*(not received|not coming|not getting)", 2.0),  # delivery issue, not phishing
    _w(r"slow", 0.5),
    _w(r"bug", 1.0),
    _w(r"update", 0.5),
]

# Priority order for tie-breaking (more critical wins).
PRIORITY: tuple[CaseType, ...] = (
    CaseType.PHISHING,
    CaseType.WRONG_TRANSFER,
    CaseType.PAYMENT_FAILED,
    CaseType.REFUND_REQUEST,
    CaseType.OTHER,
)


def _score(message: str, patterns: list[Pattern]) -> tuple[float, dict[str, float]]:
    """Return (total_score, hits)."""
    hits: dict[str, float] = {}
    total = 0.0
    for p in patterns:
        m = p.pattern.search(message)
        if m:
            total += p.weight
            hits[p.pattern.pattern] = p.weight
    return total, hits


class RuleBasedClassifier(ClassifierStrategy):
    """Deterministic, weighted-keyword classifier.

    Designed to be predictable and explainable. The `signals` field on the
    returned `Classification` exposes per-bucket scores for transparency.
    """

    name = "rule_based"

    def __init__(self) -> None:
        # Compile-once is implicit (regex already compiled in module scope).
        logger.info("rule_based_classifier.initialized")

    def classify(self, message: str, *, locale: str | None = None) -> Classification:
        msg = message.strip()

        phish_score, phish_hits = _score(msg, PHISHING_PATTERNS)
        wrong_score, wrong_hits = _score(msg, WRONG_TRANSFER_PATTERNS)
        fail_score, fail_hits = _score(msg, PAYMENT_FAILED_PATTERNS)
        refund_score, refund_hits = _score(msg, REFUND_PATTERNS)
        other_score, other_hits = _score(msg, OTHER_NEGATIVE_HINTS)

        scores: dict[CaseType, float] = {
            CaseType.PHISHING: phish_score,
            CaseType.WRONG_TRANSFER: wrong_score,
            CaseType.PAYMENT_FAILED: fail_score,
            CaseType.REFUND_REQUEST: refund_score,
            CaseType.OTHER: other_score,
        }

        # Choose highest-scoring bucket, with priority as tie-breaker.
        best_case = max(
            scores.keys(),
            key=lambda c: (scores[c], -PRIORITY.index(c)),
        )

        # If the best score is too low, fall back to "other" with low confidence.
        confidence = self._confidence(scores[best_case], best_case)
        if scores[best_case] <= 0.5:
            best_case = CaseType.OTHER
            confidence = min(confidence, 0.4)

        severity = self._severity(best_case, scores)
        department = self._department(best_case)

        signals = {
            "phishing": round(phish_score, 3),
            "wrong_transfer": round(wrong_score, 3),
            "payment_failed": round(fail_score, 3),
            "refund_request": round(refund_score, 3),
            "other": round(other_score, 3),
            "locale": locale or "unknown",
        }
        logger.debug(
            "classifier.scored",
            case_type=best_case.value,
            scores=signals,
            hits={
                "phish": list(phish_hits.keys())[:3],
                "wrong": list(wrong_hits.keys())[:3],
                "fail": list(fail_hits.keys())[:3],
                "refund": list(refund_hits.keys())[:3],
                "other": list(other_hits.keys())[:3],
            },
        )

        return Classification(
            case_type=best_case,
            severity=severity,
            department=department,
            confidence=round(confidence, 3),
            signals=signals,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _confidence(score: float, case: CaseType) -> float:
        """Map raw score → bounded confidence in [0.1, 0.99]."""
        if score <= 0:
            return 0.1
        # Saturating curve: 3 → ~0.66, 6 → ~0.86, 10 → ~0.95
        conf = min(0.99, 0.5 + (score / (score + 6.0)) * 0.49)
        # Boost phishing a bit — we want humans to see it.
        if case == CaseType.PHISHING and score >= 2.0:
            conf = max(conf, 0.85)
        return conf

    @staticmethod
    def _severity(case: CaseType, scores: dict[CaseType, float]) -> Severity:
        """Severity mapping per spec, plus escalations on strong signals."""
        if case == CaseType.PHISHING:
            # Per spec: phishing is critical.
            return Severity.CRITICAL
        if case == CaseType.WRONG_TRANSFER:
            return Severity.HIGH
        if case == CaseType.PAYMENT_FAILED:
            # Strong "balance deducted" signal → high; otherwise medium.
            return Severity.HIGH if scores[case] >= 4.0 else Severity.MEDIUM
        if case == CaseType.REFUND_REQUEST:
            return Severity.LOW
        # OTHER: low unless repeated/refund-shifted
        return Severity.LOW

    @staticmethod
    def _department(case: CaseType) -> Department:
        """Department mapping per spec table."""
        return {
            CaseType.WRONG_TRANSFER: Department.DISPUTE_RESOLUTION,
            CaseType.PAYMENT_FAILED: Department.PAYMENTS_OPS,
            CaseType.PHISHING: Department.FRAUD_RISK,
            CaseType.REFUND_REQUEST: Department.CUSTOMER_SUPPORT,
            CaseType.OTHER: Department.CUSTOMER_SUPPORT,
        }[case]
