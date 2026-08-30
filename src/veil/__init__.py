"""Veil - Privacy-preserving proxy for LLMs."""

__version__ = "0.1.0"

from veil.core.mapper import MappingStore
from veil.core.pipeline import VeilPipeline
from veil.detection.entity import Entity, EntityType

__all__ = ["VeilPipeline", "MappingStore", "Entity", "EntityType"]
