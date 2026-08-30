"""Replacement strategies for anonymizing entities."""

from veil.replacement.engine import ReplacementEngine, ReplacementMode, create_engine
from veil.replacement.token import TokenReplacer, apply_replacements

# Optional imports (require additional dependencies)
try:
    from veil.replacement.faker_gen import FakerReplacer, create_faker_replacer
except ImportError:
    FakerReplacer = None  # type: ignore[assignment,misc]
    create_faker_replacer = None  # type: ignore[assignment]

try:
    from veil.replacement.semantic import SemanticReplacer, create_semantic_replacer
except ImportError:
    SemanticReplacer = None  # type: ignore[assignment,misc]
    create_semantic_replacer = None  # type: ignore[assignment]

__all__ = [
    "TokenReplacer",
    "apply_replacements",
    "ReplacementEngine",
    "ReplacementMode",
    "create_engine",
    "FakerReplacer",
    "create_faker_replacer",
    "SemanticReplacer",
    "create_semantic_replacer",
]
