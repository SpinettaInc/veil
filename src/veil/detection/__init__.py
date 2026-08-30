"""Detection modules for identifying sensitive entities."""

from veil.detection.entity import Entity, EntityType
from veil.detection.hybrid import DetectorConfig, DetectorType, HybridDetector
from veil.detection.ner import SpacyNER
from veil.detection.patterns import PatternDetector
from veil.detection.presidio import PRESIDIO_AVAILABLE, PresidioDetector

__all__ = [
    "Entity",
    "EntityType",
    "SpacyNER",
    "PatternDetector",
    "HybridDetector",
    "DetectorConfig",
    "DetectorType",
    "PresidioDetector",
    "PRESIDIO_AVAILABLE",
]
