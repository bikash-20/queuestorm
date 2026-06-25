"""Unit tests for the safety filter and inspector."""
from __future__ import annotations

import pytest

from app.services.safety import SafetyFilter, SafetyInspector


@pytest.fixture()
def sf() -> SafetyFilter:
    return SafetyFilter()


@pytest.fixture()
def inspector() -> SafetyInspector:
    return SafetyInspector()


@pytest.mark.parametrize(
    "dangerous",
    [
        "Please share your OTP with us.",
        "Kindly send us your PIN code.",
        "You should enter your password to verify.",
        "Please provide your card number.",
        "Tell me your CVV.",
        "Type your one time password below.",
    ],
)
def test_safety_filter_removes_credential_requests(sf, dangerous):
    result = sf.sanitize(dangerous)
    assert not result.is_safe
    assert "credential_request_removed" in result.redactions
    lowered = result.sanitized_text.lower()
    for noun in ("otp", "pin", "password", "cvv"):
        assert noun not in lowered or "[redacted]" in lowered.lower()


def test_safety_filter_keeps_safe_text(sf):
    text = "Customer reports a failed payment and wants a refund."
    result = sf.sanitize(text)
    assert result.is_safe
    assert result.sanitized_text == text


def test_safety_filter_masks_digits(sf):
    text = "Card 4111 1111 1111 1111 was charged twice."
    result = sf.sanitize(text)
    assert "4111" not in result.sanitized_text
    assert "[REDACTED]" in result.sanitized_text


def test_safety_filter_handles_far_apart_phrase(sf):
    # verb and noun > 40 chars apart — regex might miss, but noun-level
    # scrub catches the residual.
    text = "Please " + ("x" * 60) + " your OTP"
    result = sf.sanitize(text)
    assert "otp" not in result.sanitized_text.lower()


def test_safety_inspector_flags_card_number(inspector):
    v = inspector.inspect("My card 4111111111111111 was charged")
    assert v.contains_pii_like
    assert v.risk_score > 0


def test_safety_inspector_clean_message(inspector):
    v = inspector.inspect("I sent 500 taka to wrong number please help")
    assert not v.contains_pii_like
    assert not v.contains_injection_like
    assert v.risk_score == 0.0
