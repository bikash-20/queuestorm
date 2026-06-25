"""Classifier factory + LLM stub.

The factory pattern lets the API controller stay agnostic of which
classifier is in use. New strategies plug in here.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.exceptions import ClassifierUnavailableError
from app.core.logging import get_logger
from app.services.classifier.base import Classification, ClassifierStrategy
from app.services.classifier.rule_based import RuleBasedClassifier

logger = get_logger(__name__)


class LLMClassifier(ClassifierStrategy):
    """Stub LLM-backed classifier.

    Plugs into the same interface as `RuleBasedClassifier`. To enable in
    production, set `CLASSIFIER_BACKEND=llm` and provide `LLM_API_KEY`.
    The actual API call is intentionally not implemented in this submission
    to keep the service hermetic and dependency-free (no network, no GPU).
    """

    name = "llm"

    def __init__(self, api_key: str, model: str, timeout: int) -> None:
        if not api_key:
            raise ClassifierUnavailableError(
                "LLM_API_KEY is not set; cannot enable llm backend"
            )
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def classify(self, message: str, *, locale: str | None = None) -> Classification:  # noqa: D401
        raise ClassifierUnavailableError(
            "LLM backend not wired in this build; configure a real provider "
            "or switch CLASSIFIER_BACKEND=rule_based",
            details={"model": self._model},
        )


@lru_cache(maxsize=1)
def get_classifier() -> ClassifierStrategy:
    """Return the configured classifier (singleton)."""
    settings = get_settings()
    backend = settings.classifier_backend

    if backend == "rule_based":
        logger.info("classifier.factory.selected", backend=backend)
        return RuleBasedClassifier()
    if backend == "llm":
        logger.info("classifier.factory.selected", backend=backend)
        return LLMClassifier(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )

    raise ClassifierUnavailableError(f"Unknown classifier backend: {backend}")
