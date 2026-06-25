"""Abstract base for the classifier strategy.

This is the boundary that lets us swap implementations:
    RuleBasedClassifier  → deterministic, fast, no network
    LLMClassifier        → optional, requires API key
    BERTClassifier       → future, swap without touching controllers
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import CaseType, Department, Severity


@dataclass(frozen=True, slots=True)
class Classification:
    """Pure data result of classifying a single message."""

    case_type: CaseType
    severity: Severity
    department: Department
    confidence: float
    signals: dict[str, float | str | int]


class ClassifierStrategy(ABC):
    """Strategy interface for any classifier backend.

    Implementations MUST be:
      * deterministic given the same input (or document non-determinism)
      * safe — never request sensitive info, never echo credentials
      * bounded in latency
    """

    name: str = "abstract"

    @abstractmethod
    def classify(self, message: str, *, locale: str | None = None) -> Classification:
        """Classify the given free-text message.

        Args:
            message: Raw customer message.
            locale: Optional hint ("bn", "en", "mixed").

        Returns:
            A `Classification` value object.

        Raises:
            ClassifierUnavailableError: if the backend cannot serve the request.
        """

    def health(self) -> bool:
        """Return True if the backend is ready to serve traffic."""
        return True


# A trivial readiness flag — strategies that need warmup can override.
def classifier_ready(strategy: ClassifierStrategy) -> bool:
    return strategy.health()
