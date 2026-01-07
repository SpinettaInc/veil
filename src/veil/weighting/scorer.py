"""Privacy score calculator combining all weighting factors."""

from dataclasses import dataclass
from typing import Optional

from veil.detection.entity import Entity
from veil.weighting.config import WeightConfig, DetectionProfile, get_profile_config
from veil.weighting.tfidf import DocumentStats, GlobalRarityScorer
from veil.weighting.context import ContextAnalyzer, RelationshipAnalyzer


@dataclass
class PrivacyScore:
    """Detailed privacy score breakdown for an entity.

    Attributes:
        entity: The entity being scored
        total_score: Final combined score (0.0 to 1.0)
        base_score: Score from entity type weight
        pos_multiplier: Multiplier from POS tag
        rarity_boost: Boost from term rarity
        context_boost: Boost from context patterns
        relationship_boost: Boost from entity relationships
        above_threshold: Whether score exceeds anonymization threshold
        contributing_factors: Human-readable list of factors
    """

    entity: Entity
    total_score: float
    base_score: float
    pos_multiplier: float
    rarity_boost: float
    context_boost: float
    relationship_boost: float
    above_threshold: bool
    contributing_factors: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "entity_text": self.entity.text,
            "entity_type": self.entity.entity_type.value,
            "total_score": round(self.total_score, 3),
            "base_score": round(self.base_score, 3),
            "pos_multiplier": round(self.pos_multiplier, 2),
            "rarity_boost": round(self.rarity_boost, 3),
            "context_boost": round(self.context_boost, 3),
            "relationship_boost": round(self.relationship_boost, 3),
            "above_threshold": self.above_threshold,
            "factors": self.contributing_factors,
        }


class PrivacyScorer:
    """Calculate privacy sensitivity scores for entities.

    This scorer combines multiple signals to determine how sensitive
    an entity is and whether it should be anonymized:

    1. **Entity Type Weight**: Base score from entity type (PERSON=0.95, etc.)
    2. **POS Multiplier**: Adjust based on part-of-speech (proper nouns=1.2)
    3. **Rarity Boost**: Rare terms are more identifying (TF-IDF inspired)
    4. **Context Boost**: Sensitive context patterns increase score
    5. **Relationship Boost**: Relationships between entities add sensitivity

    Final score formula:
        score = (base * pos_mult) + (rarity * rarity_factor) + context + relationship

    Example:
        >>> scorer = PrivacyScorer()
        >>> score = scorer.score_entity(entity, "full document text")
        >>> if score.above_threshold:
        ...     anonymize(entity)
    """

    def __init__(
        self,
        config: Optional[WeightConfig] = None,
        profile: Optional[DetectionProfile] = None,
    ) -> None:
        """Initialize the privacy scorer.

        Args:
            config: Custom weight configuration
            profile: Use a pre-defined profile (paranoid, balanced, minimal)
                    If both config and profile are provided, config takes precedence.
        """
        if config:
            self.config = config
        elif profile:
            self.config = get_profile_config(profile)
        else:
            self.config = WeightConfig()  # Default balanced config

        # Initialize component scorers
        self.rarity_scorer = GlobalRarityScorer()
        self.context_analyzer = ContextAnalyzer.from_config(self.config)
        self.relationship_analyzer = RelationshipAnalyzer()

        # Cache for document stats
        self._doc_stats_cache: dict[int, DocumentStats] = {}

    def _get_doc_stats(self, text: str) -> DocumentStats:
        """Get or compute document statistics.

        Uses caching to avoid recomputing for the same document.

        Args:
            text: Document text

        Returns:
            DocumentStats for the text
        """
        text_hash = hash(text)
        if text_hash not in self._doc_stats_cache:
            self._doc_stats_cache[text_hash] = DocumentStats.from_text(text)
        return self._doc_stats_cache[text_hash]

    def score_entity(
        self,
        entity: Entity,
        full_text: str,
        all_entities: Optional[list[Entity]] = None,
        pos_tag: Optional[str] = None,
    ) -> PrivacyScore:
        """Calculate privacy score for an entity.

        Args:
            entity: Entity to score
            full_text: Full document text (for context/rarity analysis)
            all_entities: All entities in document (for relationship analysis)
            pos_tag: Part-of-speech tag (if known from NLP)

        Returns:
            Detailed PrivacyScore object
        """
        contributing_factors: list[str] = []

        # 1. Base score from entity type
        base_score = self.config.get_entity_weight(entity.entity_type)
        contributing_factors.append(
            f"Entity type {entity.entity_type.value}: {base_score:.2f}"
        )

        # 2. POS multiplier
        pos_multiplier = 1.0
        if pos_tag:
            pos_multiplier = self.config.get_pos_multiplier(pos_tag)
            if pos_multiplier != 1.0:
                contributing_factors.append(
                    f"POS tag {pos_tag}: x{pos_multiplier:.2f}"
                )

        # 3. Rarity boost
        doc_stats = self._get_doc_stats(full_text)
        rarity_raw = self.rarity_scorer.score_multi_word(entity.text, doc_stats)
        rarity_boost = rarity_raw * self.config.rarity_factor
        if rarity_boost > 0.01:
            contributing_factors.append(
                f"Term rarity: +{rarity_boost:.3f}"
            )

        # 4. Context boost
        context_boost = self.context_analyzer.calculate_boost(entity, full_text)
        if context_boost > 0:
            patterns = self.context_analyzer.get_matching_patterns(entity, full_text)
            contributing_factors.append(
                f"Context patterns: +{context_boost:.3f} ({', '.join(patterns[:2])})"
            )

        # 5. Relationship boost
        relationship_boost = 0.0
        if all_entities and len(all_entities) > 1:
            relationship_boost = self.relationship_analyzer.calculate_relationship_boost(
                entity, all_entities, full_text
            )
            if relationship_boost > 0:
                contributing_factors.append(
                    f"Entity relationships: +{relationship_boost:.3f}"
                )

        # Calculate total score
        total_score = (base_score * pos_multiplier) + rarity_boost + context_boost + relationship_boost

        # Clamp to [0, 1]
        total_score = max(0.0, min(1.0, total_score))

        # Check threshold
        above_threshold = total_score >= self.config.threshold

        return PrivacyScore(
            entity=entity,
            total_score=total_score,
            base_score=base_score,
            pos_multiplier=pos_multiplier,
            rarity_boost=rarity_boost,
            context_boost=context_boost,
            relationship_boost=relationship_boost,
            above_threshold=above_threshold,
            contributing_factors=contributing_factors,
        )

    def score_entities(
        self,
        entities: list[Entity],
        full_text: str,
    ) -> list[PrivacyScore]:
        """Score multiple entities.

        More efficient than scoring individually as it reuses
        document statistics and considers relationships.

        Args:
            entities: List of entities to score
            full_text: Full document text

        Returns:
            List of PrivacyScore objects
        """
        scores = []
        for entity in entities:
            score = self.score_entity(
                entity=entity,
                full_text=full_text,
                all_entities=entities,
            )
            scores.append(score)
        return scores

    def filter_by_threshold(
        self,
        entities: list[Entity],
        full_text: str,
    ) -> list[Entity]:
        """Filter entities to only those above the threshold.

        Args:
            entities: List of entities to filter
            full_text: Full document text

        Returns:
            List of entities that should be anonymized
        """
        scores = self.score_entities(entities, full_text)
        return [s.entity for s in scores if s.above_threshold]

    def get_stats(self) -> dict:
        """Get scorer statistics.

        Returns:
            Dictionary with configuration info
        """
        return {
            "threshold": self.config.threshold,
            "rarity_factor": self.config.rarity_factor,
            "context_patterns_count": len(self.config.context_patterns),
            "entity_type_weights_count": len(self.config.entity_weights),
        }

    def clear_cache(self) -> None:
        """Clear the document statistics cache."""
        self._doc_stats_cache.clear()


def score_text(
    text: str,
    entities: list[Entity],
    profile: DetectionProfile = DetectionProfile.BALANCED,
) -> list[PrivacyScore]:
    """Convenience function to score entities in text.

    Args:
        text: Document text
        entities: Entities to score
        profile: Detection profile to use

    Returns:
        List of privacy scores
    """
    scorer = PrivacyScorer(profile=profile)
    return scorer.score_entities(entities, text)
