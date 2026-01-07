"""Context-aware sensitivity detection.

Analyzes the context around entities to determine if they're
in a sensitive context (e.g., "patient John Smith" is more
sensitive than just "John Smith").
"""

import re
from dataclasses import dataclass
from typing import Optional

from veil.detection.entity import Entity
from veil.weighting.config import ContextPattern, WeightConfig


@dataclass
class ContextMatch:
    """A match of a context pattern near an entity.

    Attributes:
        pattern: The pattern that matched
        matched_text: The actual text that matched
        distance: Distance from entity (characters)
        position: 'before' or 'after' the entity
    """

    pattern: ContextPattern
    matched_text: str
    distance: int
    position: str  # "before" or "after"

    @property
    def boost(self) -> float:
        """Get the sensitivity boost from this match."""
        # Closer matches get full boost, farther matches get reduced boost
        distance_factor = max(0.5, 1.0 - (self.distance / 100))
        return self.pattern.boost * distance_factor


class ContextAnalyzer:
    """Analyze context around entities for sensitivity patterns.

    This analyzer looks for patterns in the surrounding text that
    indicate an entity is being used in a sensitive context.

    Example:
        "patient John Smith" -> high boost (medical context)
        "John Smith said" -> low/no boost (general reference)
    """

    def __init__(
        self,
        patterns: list[ContextPattern] | None = None,
        window_size: int = 100,
    ) -> None:
        """Initialize the context analyzer.

        Args:
            patterns: Context patterns to look for
            window_size: Characters before/after entity to analyze
        """
        self.patterns = patterns or []
        self.window_size = window_size

    def analyze(self, entity: Entity, full_text: str) -> list[ContextMatch]:
        """Analyze context around an entity.

        Args:
            entity: Entity to analyze
            full_text: Full document text

        Returns:
            List of context pattern matches
        """
        matches: list[ContextMatch] = []

        # Extract context window
        before_start = max(0, entity.start - self.window_size)
        after_end = min(len(full_text), entity.end + self.window_size)

        before_text = full_text[before_start:entity.start]
        after_text = full_text[entity.end:after_end]

        # Check each pattern
        for pattern in self.patterns:
            # Check before context
            for match in pattern.pattern.finditer(before_text):
                distance = entity.start - (before_start + match.end())
                matches.append(ContextMatch(
                    pattern=pattern,
                    matched_text=match.group(),
                    distance=distance,
                    position="before",
                ))

            # Check after context
            for match in pattern.pattern.finditer(after_text):
                distance = match.start()
                matches.append(ContextMatch(
                    pattern=pattern,
                    matched_text=match.group(),
                    distance=distance,
                    position="after",
                ))

        return matches

    def calculate_boost(self, entity: Entity, full_text: str) -> float:
        """Calculate total sensitivity boost from context.

        Args:
            entity: Entity to analyze
            full_text: Full document text

        Returns:
            Total boost amount (sum of all matching pattern boosts)
        """
        matches = self.analyze(entity, full_text)

        if not matches:
            return 0.0

        # Sum up boosts, but cap at a reasonable maximum
        total_boost = sum(m.boost for m in matches)
        return min(0.5, total_boost)  # Cap at 0.5 total boost

    def get_matching_patterns(self, entity: Entity, full_text: str) -> list[str]:
        """Get descriptions of matching patterns.

        Args:
            entity: Entity to analyze
            full_text: Full document text

        Returns:
            List of pattern descriptions that matched
        """
        matches = self.analyze(entity, full_text)
        return [m.pattern.description for m in matches if m.pattern.description]

    @classmethod
    def from_config(cls, config: WeightConfig) -> "ContextAnalyzer":
        """Create a ContextAnalyzer from a WeightConfig.

        Args:
            config: Weight configuration with context patterns

        Returns:
            Configured ContextAnalyzer
        """
        return cls(
            patterns=config.context_patterns,
            window_size=config.context_window,
        )


class RelationshipAnalyzer:
    """Analyze relationships between entities.

    Detects when entities are related in ways that increase
    sensitivity, like:
    - "John Smith, CEO of Acme Corp" (person-org relationship)
    - "patient ID 12345 for John Smith" (person-identifier relationship)
    """

    # Patterns indicating relationships
    RELATIONSHIP_PATTERNS = [
        # Person-Organization relationships
        (r"\b(CEO|CTO|CFO|founder|president|director|employee)\s+(?:of|at)\s+",
         "person-org", 0.15),
        (r"\bworks?\s+(?:for|at)\s+",
         "person-org", 0.10),

        # Person-Identifier relationships
        (r"\b(?:SSN|social\s+security|account|ID|patient\s+ID)[\s:]+",
         "person-identifier", 0.20),

        # Person-Location relationships
        (r"\blives?\s+(?:at|in)\s+",
         "person-location", 0.15),
        (r"\bborn\s+(?:in|at)\s+",
         "person-location", 0.10),

        # Organization-Location relationships
        (r"\b(?:based|located|headquartered)\s+(?:in|at)\s+",
         "org-location", 0.10),
    ]

    def __init__(self) -> None:
        """Initialize the relationship analyzer."""
        self.patterns = [
            (re.compile(p, re.IGNORECASE), rel_type, boost)
            for p, rel_type, boost in self.RELATIONSHIP_PATTERNS
        ]

    def find_relationships(
        self,
        entities: list[Entity],
        full_text: str,
    ) -> list[tuple[Entity, Entity, str, float]]:
        """Find relationships between entities.

        Args:
            entities: List of entities to analyze
            full_text: Full document text

        Returns:
            List of (entity1, entity2, relationship_type, boost) tuples
        """
        relationships: list[tuple[Entity, Entity, str, float]] = []

        # Sort entities by position
        sorted_entities = sorted(entities, key=lambda e: e.start)

        # Check pairs of adjacent entities
        for i, e1 in enumerate(sorted_entities[:-1]):
            e2 = sorted_entities[i + 1]

            # Get text between entities
            between = full_text[e1.end:e2.start]

            # Check for relationship patterns
            for pattern, rel_type, boost in self.patterns:
                if pattern.search(between):
                    relationships.append((e1, e2, rel_type, boost))
                    break

        return relationships

    def calculate_relationship_boost(
        self,
        entity: Entity,
        all_entities: list[Entity],
        full_text: str,
    ) -> float:
        """Calculate boost from entity relationships.

        Args:
            entity: Entity to calculate boost for
            all_entities: All entities in the document
            full_text: Full document text

        Returns:
            Boost amount from relationships
        """
        relationships = self.find_relationships(all_entities, full_text)

        total_boost = 0.0
        for e1, e2, rel_type, boost in relationships:
            if e1 == entity or e2 == entity:
                total_boost += boost

        return min(0.3, total_boost)  # Cap relationship boost
