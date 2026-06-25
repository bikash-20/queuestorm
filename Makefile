.PHONY: help install test run docker-build docker-up docker-down lint clean

PYTHON ?= python3
HOST ?= 0.0.0.0
PORT ?= 8000

help:
	@echo "QueueStorm — common commands"
	@echo "  make install      create venv and install deps"
	@echo "  make test         run pytest"
	@echo "  make run          run uvicorn locally"
	@echo "  make docker-build build the container image"
	@echo "  make docker-up    build + start the container (port 8000)"
	@echo "  make docker-down  stop and remove the container"
	@echo "  make smoke        run scripts/smoke.sh against a running server"
	@echo "  make clean        remove caches and build artifacts"

install:
	uv venv --python 3.12 .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest

run:
	.venv/bin/uvicorn app.main:app --host $(HOST) --port $(PORT) --reload

docker-build:
	docker build -t queuestorm:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

smoke:
	bash scripts/smoke.sh

clean:
	rm -rf .pytest_cache .coverage htmlcov **/__pycache__ */__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
