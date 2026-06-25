"""Safety subsystem.

Two responsibilities:

1. `SafetyInspector` — *input* scanning. Detects:
   - prompt-injection-like attempts
   - explicit PII (card numbers, phone-OTP-like sequences)
   It NEVER blocks legitimate complaints; it only flags suspicious content.

2. `SafetyFilter` — *output* sanitization. Guarantees that
   `agent_summary` does not contain:
   - requests for OTP / PIN / password / CVV / card number
   - raw card or phone numbers
   - unsafe language

This is a defense-in-depth boundary; the spec is explicit that any
agent_summary asking for credentials will fail that test case.
"""
from __future__ import annotations

from app.services.safety.inspector import SafetyInspector, SafetyVerdict, get_safety_inspector
from app.services.safety.filter import SafetyFilter, SafetyResult, get_safety_filter

__all__ = [
    "SafetyFilter",
    "SafetyInspector",
    "SafetyResult",
    "SafetyVerdict",
    "get_safety_filter",
    "get_safety_inspector",
]