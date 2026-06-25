"""Integration tests — exercise the FastAPI app via TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code in (200, 503)
    body = r.json()
    assert "status" in body
    assert body["service"] == "queuestorm"
    assert "classifier_ready" in body


def test_sort_ticket_wrong_transfer(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-001",
            "channel": "app",
            "locale": "en",
            "message": "I sent 5000 taka to a wrong number this morning, please help me get it back",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ticket_id"] == "T-001"
    assert body["case_type"] == "wrong_transfer"
    assert body["severity"] == "high"
    assert body["department"] == "dispute_resolution"
    assert body["human_review_required"] is False
    assert 0.0 <= body["confidence"] <= 1.0
    # Safety guarantee
    summary_lower = body["agent_summary"].lower()
    for forbidden in ("otp", "pin", "password", "cvv"):
        assert forbidden not in summary_lower or "[redacted]" in summary_lower


def test_sort_ticket_payment_failed(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-002",
            "message": "Payment failed but balance was deducted",
        },
    )
    body = r.json()
    assert body["case_type"] == "payment_failed"
    assert body["severity"] == "high"
    assert body["department"] == "payments_ops"


def test_sort_ticket_phishing(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-003",
            "message": "Someone called asking my OTP, is that bKash?",
        },
    )
    body = r.json()
    assert body["case_type"] == "phishing_or_social_engineering"
    assert body["severity"] == "critical"
    assert body["department"] == "fraud_risk"
    assert body["human_review_required"] is True
    # Safety: never asks customer to share credentials
    summary_lower = body["agent_summary"].lower()
    assert "otp" not in summary_lower or "[redacted]" in summary_lower


def test_sort_ticket_refund_request(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-004",
            "message": "Please refund my last transaction, I changed my mind",
        },
    )
    body = r.json()
    assert body["case_type"] == "refund_request"
    assert body["severity"] == "low"
    assert body["department"] == "customer_support"


def test_sort_ticket_other(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={"ticket_id": "T-005", "message": "App crashed when I opened it"},
    )
    body = r.json()
    assert body["case_type"] == "other"
    assert body["severity"] == "low"


def test_validation_error_on_missing_message(client: TestClient):
    r = client.post("/sort-ticket", json={"ticket_id": "T-X"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_validation_error_on_empty_message(client: TestClient):
    r = client.post("/sort-ticket", json={"ticket_id": "T-X", "message": ""})
    assert r.status_code == 422


def test_validation_error_on_unknown_field(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={"ticket_id": "T-X", "message": "hello", "evil": True},
    )
    assert r.status_code == 422


def test_response_includes_request_id(client: TestClient):
    r = client.post(
        "/sort-ticket",
        json={"ticket_id": "T-RID", "message": "Payment failed and money was deducted"},
    )
    assert "x-request-id" in r.headers


def test_summary_never_asks_for_credentials(client: TestClient):
    """Property test: 20 random-ish phishy inputs → summaries stay safe."""
    samples = [
        "He told me to send my OTP",
        "Please share PIN and password",
        "Click the link and enter your CVV",
        "Send your card number for verification",
        "Give me your OTP code right now",
    ]
    for msg in samples:
        r = client.post("/sort-ticket", json={"ticket_id": f"P-{hash(msg)}", "message": msg})
        assert r.status_code == 200
        summary = r.json()["agent_summary"].lower()
        for forbidden in ("otp", "pin", "password", "cvv"):
            assert forbidden not in summary or "[redacted]" in summary
