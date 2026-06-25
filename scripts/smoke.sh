#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Smoke test — assumes the service is running on $HOST (default: localhost)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

HOST="${HOST:-http://localhost:8000}"

echo "▶ GET $HOST/health"
curl -sf "$HOST/health" | python3 -m json.tool
echo

echo "▶ POST $HOST/sort-ticket (wrong_transfer)"
curl -sf -X POST "$HOST/sort-ticket" \
    -H 'Content-Type: application/json' \
    -d '{
      "ticket_id": "T-001",
      "channel": "app",
      "locale": "en",
      "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
    }' | python3 -m json.tool
echo

echo "▶ POST $HOST/sort-ticket (payment_failed)"
curl -sf -X POST "$HOST/sort-ticket" \
    -H 'Content-Type: application/json' \
    -d '{
      "ticket_id": "T-002",
      "message": "Payment failed but balance was deducted from my account"
    }' | python3 -m json.tool
echo

echo "▶ POST $HOST/sort-ticket (phishing)"
curl -sf -X POST "$HOST/sort-ticket" \
    -H 'Content-Type: application/json' \
    -d '{
      "ticket_id": "T-003",
      "message": "Someone called asking my OTP, is that bKash?"
    }' | python3 -m json.tool
echo

echo "▶ POST $HOST/sort-ticket (refund_request)"
curl -sf -X POST "$HOST/sort-ticket" \
    -H 'Content-Type: application/json' \
    -d '{
      "ticket_id": "T-004",
      "message": "Please refund my last transaction, I changed my mind"
    }' | python3 -m json.tool
echo

echo "▶ POST $HOST/sort-ticket (other)"
curl -sf -X POST "$HOST/sort-ticket" \
    -H 'Content-Type: application/json' \
    -d '{
      "ticket_id": "T-005",
      "message": "App crashed when I opened it"
    }' | python3 -m json.tool
echo

echo "All sample cases succeeded."
