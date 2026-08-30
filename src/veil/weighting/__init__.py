"""Weighting modules for scoring entity sensitivity."""

from veil.weighting.config import (
    ContextPattern,
    DetectionProfile,
    WeightConfig,
    get_balanced_config,
    get_minimal_config,
    get_paranoid_config,
    get_profile_config,
)
from veil.weighting.context import ContextAnalyzer, ContextMatch, RelationshipAnalyzer
from veil.weighting.scorer import PrivacyScore, PrivacyScorer, score_text
from veil.weighting.tfidf import DocumentStats, GlobalRarityScorer, RarityScorer

__all__ = [
    # Config
    "WeightConfig",
    "DetectionProfile",
    "ContextPattern",
    "get_profile_config",
    "get_paranoid_config",
    "get_balanced_config",
    "get_minimal_config",
    # Scorer
    "PrivacyScorer",
    "PrivacyScore",
    "score_text",
    # TF-IDF
    "DocumentStats",
    "RarityScorer",
    "GlobalRarityScorer",
    # Context
    "ContextAnalyzer",
    "ContextMatch",
    "RelationshipAnalyzer",
]
