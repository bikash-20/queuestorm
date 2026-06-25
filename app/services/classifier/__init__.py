"""Classifier subsystem.

The classifier is the only piece that decides *case_type*, *severity*,
*department*, and *confidence*. Everything else (summary, safety, routing)
composes on top.

Design (Open/Closed Principle):
    New strategies (LLM, BERT, external API) can be added without modifying
    the API controller — only `factory.get_classifier()` and a new subclass.
"""
from __future__ import annotations

from app.services.classifier.base import (
    Classification,
    ClassifierStrategy,
    classifier_ready,
)
from app.services.classifier.factory import get_classifier
from app.services.classifier.rule_based import RuleBasedClassifier

__all__ = [
    "Classification",
    "ClassifierStrategy",
    "RuleBasedClassifier",
    "classifier_ready",
    "get_classifier",
]
