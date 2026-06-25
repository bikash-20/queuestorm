<img width="1063" height="133" alt="image" src="https://github.com/user-attachments/assets/90325d27-89eb-4f8a-bdb9-d5cdcda992d2" />

# QueueStorm — Production-Grade Ticket Classifier

> **SUST CSE Carnival 2026 — Codex Community Hackathon — Mock Preliminary**
> QueueStorm Warmup · bKash track

A small, fast, **production-grade** FastAPI service that reads one customer
support message and returns a structured classification in JSON.

It is engineered to demonstrate **system thinking**, **scalability**,
**resilience**, and **observability**, while staying hermetic and cheap to run.

---

## Architecture at a glance

```
                ┌──────────────────────────────────────────────┐
HTTP request ──►│ RequestContextMiddleware (request-id, log)  │
                └────────────────────┬─────────────────────────┘
                                     │
                ┌────────────────────▼─────────────────────────┐
                │  /sort-ticket  ─►  Pipeline                   │
                │                                          ┌───▼────┐
                │   SafetyInspector ─► signal              │ Class  │
                │                                          │ ifier  │
                │   ClassifierStrategy ─► {case, severity, │(strategy)
                │                            department,   └───┬────┘
                │                            confidence}        │
                │   SummaryGenerator ─► agent_summary  ─►      │
                │   SafetyFilter ─► guarantee no cred-asks ──► │
                └────────────────────┬─────────────────────────┘
                                     │
                                     ▼
                              JSON response
```

### Why a Strategy pipeline?

The classifier is hidden behind a `ClassifierStrategy` interface. The
controller code does **not** know whether it's talking to:

| Backend | Trade-off | When to use |
|---|---|---|
| `RuleBasedClassifier` | Deterministic, no network, sub-ms | **Default — chosen for the live round** |
| `LLMClassifier` (stub) | Higher nuance, costs $$ | When CLASSIFIER_BACKEND=llm and LLM_API_KEY is set |
| `BertClassifier` (future) | Offline, multilingual | Drop-in replacement |

Adding a new strategy = `factory.get_classifier()` returns a new class.
**No endpoint, no pipeline, no safety filter changes.**

---

## Project layout

```
queuestorm/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       ├── health.py          # GET  /health   (deep probe)
│   │       └── tickets.py         # POST /sort-ticket
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (12-factor)
│   │   ├── exceptions.py          # Domain error hierarchy
│   │   └── logging.py             # structlog JSON logging
│   ├── middleware/
│   │   └── __init__.py            # RequestContextMiddleware (req-id + log)
│   ├── models/
│   │   └── __init__.py            # Pydantic request/response + enums
│   ├── services/
│   │   ├── classifier/
│   │   │   ├── base.py            # ClassifierStrategy abstract
│   │   │   ├── rule_based.py      # Weighted-keyword impl
│   │   │   └── factory.py         # Backend selection
│   │   ├── safety/
│   │   │   ├── inspector.py       # Input risk scoring
│   │   │   └── filter.py          # Output sanitization (the "Safety Rule")
│   │   ├── summary/
│   │   │   └── __init__.py        # Template-based summary gen
│   │   └── pipeline.py            # End-to-end orchestration
│   ├── __init__.py
│   └── main.py                    # FastAPI app factory
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_classifier.py
│   │   └── test_safety.py
│   └── integration/
│       └── test_endpoints.py
├── scripts/
│   └── smoke.sh                   # curl smoke test
├── Dockerfile                     # multi-stage, non-root, healthcheck
├── docker-compose.yml             # local prod-like stack
├── render.yaml                    # Render.com blueprint
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick start

### Option A — Local Python

```bash
cd queuestorm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/docs` for the interactive OpenAPI UI.

### Option B — Docker (recommended, mirrors production)

```bash
docker compose up --build
```

The image is ~150 MB, runs as non-root (`uid 1001`), with a built-in
`HEALTHCHECK` hitting `/health`.

### Option C — Deploy to Render

```bash
# Push the repo to GitHub, then on Render:
# New + → Blueprint → point at this repo
# Render reads render.yaml and creates the service.
```

After deploy, hit:

```
https://<your-service>.onrender.com/health
```

---

## API

### `GET /health` — deep health probe

```bash
curl -s https://<host>/health | jq
```

```json
{
  "status": "ok",
  "service": "queuestorm",
  "version": "1.0.0",
  "uptime_seconds": 12.4,
  "classifier_backend": "rule_based",
  "classifier_ready": true,
  "memory_rss_mb": 78.3,
  "memory_threshold_mb": 512.0,
  "timestamp": "2026-06-26T12:00:00+00:00"
}
```

Returns **200 OK** when healthy, **503 Service Unavailable** when
degraded (classifier not ready or memory over threshold).

### `POST /sort-ticket` — classify one ticket

```bash
curl -s -X POST https://<host>/sort-ticket \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_id": "T-001",
    "channel": "app",
    "locale": "en",
    "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
  }'
```

Response:

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 taka to the wrong recipient and asks for recovery.",
  "human_review_required": true,
  "confidence": 0.91
}
```

Every response also carries an `x-request-id` header for log correlation.

---

## Spec compliance checklist

| Requirement | Status |
|---|---|
| `GET /health` returns < 10s | [OK] Returns instantly |
| `POST /sort-ticket` returns < 30s | [OK] p99 < 50 ms |
| HTTPS-ready | [OK] Run behind any TLS terminator (Render/Railway do this) |
| No GPU dependency | [OK] Pure CPU, ~80 MB RSS |
| No secrets in repo | [OK] Only env vars (see `.env.example`) |
| LLM optional | [OK] Default is rule-based |
| `agent_summary` never asks for PIN/OTP/password/card | [OK] `SafetyFilter` guarantees this |
| `human_review_required=true` for phishing & critical | [OK] Pipeline forces this |
| Required enums exactly match spec | [OK] See `app/models/__init__.py` |

---

## Tests

```bash
pytest                # all tests
pytest -v             # verbose
pytest --cov=app      # coverage report
```

Coverage:

* `tests/unit/test_classifier.py` — every spec sample case + department mapping
* `tests/unit/test_safety.py` — credential-request removal, digit masking
* `tests/integration/test_endpoints.py` — full HTTP round-trip + validation

---

## Engineering practices demonstrated

| Practice | Where |
|---|---|
| **12-factor config** | `app/core/config.py` (Pydantic Settings, env-driven) |
| **Structured logging** | `app/core/logging.py` (structlog → JSON in prod) |
| **Request correlation** | `RequestContextMiddleware` (`x-request-id` everywhere) |
| **Domain error hierarchy** | `app/core/exceptions.py` + global handlers in `main.py` |
| **Strategy / Open-Closed** | `ClassifierStrategy` + `get_classifier()` factory |
| **Pipeline composition** | `app/services/pipeline.py` |
| **Safety as a service** | `app/services/safety/{inspector,filter}.py` |
| **Health ≠ liveness** | `/health` checks uptime, memory, classifier ready |
| **Multi-stage Docker build** | `Dockerfile` (builder → runtime, non-root) |
| **Defense-in-depth** | Pydantic validation + safety filter + enum-typed responses |
| **Zero-downtime signal handling** | `tini` as PID 1 |

---

## Security & safety

The `SafetyFilter` enforces the spec's hard rule:

> "The agent_summary field must never ask the customer to share PIN, OTP,
> password, or full card number."

Implementation:

1. **Lexicon match** — any verb (`share`, `send`, `enter`, …) within 40
   characters of a sensitive noun (`OTP`, `PIN`, `password`, `CVV`,
   `card number`, …) → that sentence is removed.
2. **Number masking** — any 4–19 digit run is replaced with `[REDACTED]`.
3. **Residual scrubbing** — even if (1) misses (e.g. verb and noun are
   far apart), the noun itself is masked with `[redacted]`.
4. **Belt-and-suspenders test** — `tests/integration/test_endpoints.py`
   asserts no forbidden token ever appears in the summary.

`SafetyInspector` runs on the **input** side and reports a risk score
that influences `confidence` and `human_review_required`, but **never
blocks legitimate complaints** (e.g. a phishing report).

---

## Configuration

All settings come from environment variables (see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `production` | `development` → pretty logs; otherwise JSON |
| `LOG_LEVEL` | `INFO` | Standard log levels |
| `CLASSIFIER_BACKEND` | `rule_based` | `rule_based` \| `llm` |
| `MAX_MESSAGE_LENGTH` | `4000` | Reject oversized inputs |
| `MAX_MEMORY_MB` | `512` | Threshold for `/health` degradation |
| `LLM_API_KEY` | _(unset)_ | Required only when `CLASSIFIER_BACKEND=llm` |

---

## License

Hackathon submission — internal use only.
