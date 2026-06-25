"""Input inspector — flags risky content in the customer message.

Important: this does NOT reject tickets. Customers reporting phishing are
exactly the audience we want to hear from. The inspector only records a
risk score that feeds `confidence` and `human_review_required`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache


# 13–19 digit sequences (cards) and 4–8 digit sequences (likely OTP/PIN)
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SHORT_DIGITS_RE = re.compile(r"\b\d{4,8}\b")

# Patterns that look like prompt-injection / abuse.
_INJECTION_PATTERNS = [
    re.compile(r"ignore (all )?previous instructions", re.IGNORECASE),
    re.compile(r"disregard (the )?(system|above) prompt", re.IGNORECASE),
    re.compile(r"you are now", re.IGNORECASE),
    re.compile(r"</?\s*system\s*>", re.IGNORECASE),
]


@dataclass(frozen=True, slots=True)
class SafetyVerdict:
    """Result of inspecting a message."""

    risk_score: float  # 0..1
    contains_pii_like: bool
    contains_injection_like: bool
    reasons: tuple[str, ...]

    @property
    def is_high_risk(self) -> bool:
        return self.risk_score >= 0.7


class SafetyInspector:
    """Reads a message and returns a `SafetyVerdict`."""

    def inspect(self, message: str) -> SafetyVerdict:
        reasons: list[str] = []
        pii = bool(_CARD_RE.search(message))
        inj = any(p.search(message) for p in _INJECTION_PATTERNS)
        short_digits = _SHORT_DIGITS_RE.findall(message)

        if pii:
            reasons.append("looks_like_card_number")
        if inj:
            reasons.append("looks_like_prompt_injection")
        if len(short_digits) >= 2:
            reasons.append("multiple_short_digit_sequences")

        # Risk is a saturating function of the number of distinct reasons.
        score = min(1.0, 0.4 * len(reasons))
        return SafetyVerdict(
            risk_score=score,
            contains_pii_like=pii,
            contains_injection_like=inj,
            reasons=tuple(reasons),
        )


@lru_cache(maxsize=1)
def get_safety_inspector() -> SafetyInspector:
    return SafetyInspector()