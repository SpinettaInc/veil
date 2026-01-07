"""Detection modules for identifying sensitive entities."""

from veil.detection.entity import Entity, EntityType
from veil.detection.ner import SpacyNER
from veil.detection.patterns import PatternDetector
from veil.detection.hybrid import HybridDetector, DetectorConfig, DetectorType
from veil.detection.presidio import PresidioDetector, PRESIDIO_AVAILABLE

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
