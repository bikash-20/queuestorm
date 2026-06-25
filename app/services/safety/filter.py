"""Output safety filter — guarantees `agent_summary` is safe to send.

The hackathon spec is explicit:

    "The agent_summary field must never ask the customer to share PIN, OTP,
    password, or full card number. Any response that does will fail that
    test case automatically."

This module is the single source of truth for that guarantee.

Strategy: refuse to emit ANY phrase that *requests* a credential. We
detect by:
  1. Lexicon — verbs + sensitive nouns in proximity
  2. Pattern  — explicit "send/enter/type your OTP|PIN|password|CVV" phrases
  3. Number-mask — replace digit sequences with placeholders

If a sentence would be unsafe, it is rewritten to a safe neutral form.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# ─────────────────────────────────────────────────────────────────────────────
# Lexicon
# ─────────────────────────────────────────────────────────────────────────────
_REQUEST_VERBS = (
    "share",
    "send",
    "give",
    "tell",
    "provide",
    "submit",
    "enter",
    "type",
    "input",
    "confirm",
    "verify",
    "disclose",
    "reply with",
)

_SENSITIVE_NOUNS = (
    "otp",
    "pin",
    "password",
    "cvv",
    "cvc",
    "card number",
    "credit card",
    "card no",
    "card details",
    "bank details",
    "secret code",
    "one time password",
    "one-time password",
)

# A "request" pattern: optional adverb + verb + ... + sensitive noun.
_REQUEST_PATTERN = re.compile(
    r"\b(?P<verb>"
    + "|".join(re.escape(v) for v in _REQUEST_VERBS)
    + r")\b.{0,40}\b(?P<noun>"
    + "|".join(re.escape(n) for n in _SENSITIVE_NOUNS)
    + r")\b",
    re.IGNORECASE,
)

_DIGITS_RE = re.compile(r"\b\d{4,19}\b")


# ─────────────────────────────────────────────────────────────────────────────
# Public surface
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SafetyResult:
    is_safe: bool
    sanitized_text: str
    redactions: tuple[str, ...]


class SafetyFilter:
    """Stateless output sanitizer."""

    def sanitize(self, text: str) -> SafetyResult:
        redactions: list[str] = []

        # 1) Remove any sentence that requests a credential.
        sentences = self._split_sentences(text)
        kept: list[str] = []
        for s in sentences:
            if _REQUEST_PATTERN.search(s):
                redactions.append("credential_request_removed")
                continue
            kept.append(s)

        cleaned = " ".join(kept).strip()
        if not cleaned:
            cleaned = (
                "Customer concern recorded. An agent will follow up to assist "
                "through the official secure channel."
            )

        # 2) Mask any leftover digit sequences (potential cards / phone).
        original_cleaned = cleaned
        cleaned = _DIGITS_RE.sub("[REDACTED]", cleaned)
        if cleaned != original_cleaned:
            redactions.append("digits_masked")

        # 3) Belt-and-suspenders: drop any literal sensitive noun that
        #    remains (e.g. "Please share your PIN" survives if verb and
        #    noun are >40 chars apart; this catches the residual).
        for noun in _SENSITIVE_NOUNS:
            if noun in cleaned.lower():
                cleaned = re.sub(
                    rf"\b{re.escape(noun)}\b",
                    "[redacted]",
                    cleaned,
                    flags=re.IGNORECASE,
                )
                redactions.append(f"redacted_{noun.replace(' ', '_')}")

        return SafetyResult(
            is_safe=len(redactions) == 0,
            sanitized_text=cleaned,
            redactions=tuple(redactions),
        )

    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        # Lightweight splitter — good enough for short agent summaries.
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p for p in parts if p]


@lru_cache(maxsize=1)
def get_safety_filter() -> SafetyFilter:
    return SafetyFilter()