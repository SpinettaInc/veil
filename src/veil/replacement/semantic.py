"""Semantic embedding-based replacement strategy.

Uses word embeddings to find semantically similar replacements
that preserve the meaning and role of entities in context.
"""

import random
from typing import Any, Protocol, cast

from veil.core.mapper import MappingStore
from veil.detection.entity import Entity, EntityType


class EmbeddingModel(Protocol):
    """Protocol for embedding models."""

    def get_vector(self, word: str) -> list[float] | None:
        """Get embedding vector for a word."""
        ...

    def most_similar(
        self,
        word: str,
        topn: int = 10,
        exclude: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Find most similar words to given word."""
        ...


class SpacyEmbeddings:
    """Use spaCy's word vectors for embeddings."""

    def __init__(self, nlp: Any = None) -> None:
        """Initialize with spaCy model.

        Args:
            nlp: spaCy model with word vectors, or None to auto-load
        """
        self.nlp = nlp
        self._vocab_cache: list[str] | None = None

    def _ensure_nlp(self) -> None:
        """Lazy load spaCy model."""
        if self.nlp is None:
            import spacy
            # Try to load model with vectors
            for model in ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]:
                try:
                    self.nlp = spacy.load(model)
                    break
                except OSError:
                    continue

            if self.nlp is None:
                raise RuntimeError(
                    "No spaCy model found. Install with: "
                    "python -m spacy download en_core_web_lg"
                )

    def get_vector(self, word: str) -> list[float] | None:
        """Get embedding vector for a word."""
        self._ensure_nlp()

        token = self.nlp(word)[0]
        if token.has_vector:
            return cast(list[float], token.vector.tolist())
        return None

    def most_similar(
        self,
        word: str,
        topn: int = 10,
        exclude: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Find most similar words using spaCy vectors.

        Args:
            word: Word to find similar words for
            topn: Number of similar words to return
            exclude: Words to exclude from results

        Returns:
            List of (word, similarity) tuples
        """
        self._ensure_nlp()
        exclude = exclude or set()

        token = self.nlp(word)[0]
        if not token.has_vector:
            return []

        # Get similar words from vocabulary
        if self._vocab_cache is None:
            # Cache vocabulary words that have vectors
            self._vocab_cache = [
                lex.text for lex in self.nlp.vocab
                if lex.has_vector and lex.is_alpha and not lex.is_stop
            ][:10000]  # Limit for performance

        # Calculate similarities
        similarities = []
        for vocab_word in self._vocab_cache:
            if vocab_word.lower() == word.lower():
                continue
            if vocab_word.lower() in exclude:
                continue

            vocab_token = self.nlp(vocab_word)[0]
            if vocab_token.has_vector:
                sim = token.similarity(vocab_token)
                similarities.append((vocab_word, sim))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:topn]


class SemanticReplacer:
    """Semantic embedding-based replacement strategy.

    Uses word embeddings to find replacements that:
    1. Are semantically similar to the original
    2. Preserve the contextual role
    3. Are different enough to protect privacy

    Examples:
        - "CEO John Smith" -> "CEO Michael Chen"
          (finds a name with similar "business leader" context)
        - "New York office" -> "Chicago office"
          (replaces with another major city)

    Attributes:
        embeddings: Embedding model for similarity calculations
        similarity_threshold: Minimum similarity for replacements
    """

    def __init__(
        self,
        embeddings: EmbeddingModel | None = None,
        similarity_threshold: float = 0.6,
        use_fallback: bool = True,
    ) -> None:
        """Initialize the semantic replacer.

        Args:
            embeddings: Embedding model to use, or None to auto-initialize
            similarity_threshold: Minimum cosine similarity for replacements
            use_fallback: Whether to use fallback pools when embedding fails
        """
        self.embeddings = embeddings
        self.similarity_threshold = similarity_threshold
        self.use_fallback = use_fallback
        self._initialized = False

        # Fallback pools for common entity types
        self._fallback_pools = self._create_fallback_pools()

        # Track used replacements to avoid duplicates
        self._used_replacements: set[str] = set()

    def _lazy_init(self) -> None:
        """Lazy initialize embeddings model."""
        if self._initialized:
            return

        if self.embeddings is None:
            try:
                self.embeddings = SpacyEmbeddings()
            except Exception:
                # Fall back to pool-based replacement
                self.embeddings = None

        self._initialized = True

    def _create_fallback_pools(self) -> dict[EntityType, list[str]]:
        """Create fallback word pools for each entity type."""
        return {
            EntityType.PERSON: [
                # First names (diverse)
                "James", "Michael", "Robert", "David", "William",
                "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
                "Wei", "Hiroshi", "Raj", "Sofia", "Fatima",
                "Chen", "Kim", "Singh", "Garcia", "Mueller",
            ],
            EntityType.ORG: [
                "Apex Industries", "Summit Corp", "Nova Holdings",
                "Pinnacle Group", "Vertex Solutions", "Catalyst Inc",
                "Synergy Partners", "Momentum LLC", "Horizon Enterprises",
                "Atlas Technologies", "Quantum Systems", "Stellar Dynamics",
            ],
            EntityType.GPE: [
                # Major cities
                "Boston", "Seattle", "Denver", "Atlanta", "Chicago",
                "Phoenix", "Portland", "Austin", "Miami", "Detroit",
                "Toronto", "London", "Berlin", "Tokyo", "Sydney",
            ],
            EntityType.LOC: [
                "Central Park", "Golden Gate", "Blue Ridge Mountains",
                "Crystal Lake", "Oak Valley", "Pine Grove",
                "Sunset Beach", "River North", "Highland District",
            ],
            EntityType.FAC: [
                "Central Tower", "Innovation Center", "Tech Campus",
                "Corporate Plaza", "Business Park", "Research Hub",
            ],
            EntityType.PRODUCT: [
                "ProMax", "TechEdge", "SmartCore", "FlexiPro",
                "UltraSync", "PowerFlow", "CloudBase", "DataStream",
            ],
            EntityType.EVENT: [
                "Annual Summit", "Tech Conference", "Innovation Forum",
                "Industry Meeting", "Leadership Retreat", "Strategy Session",
            ],
        }

    def generate_replacement(
        self,
        entity: Entity,
        mapping_store: MappingStore,
    ) -> str:
        """Generate a semantically similar replacement for an entity.

        Args:
            entity: The entity to replace
            mapping_store: Store for tracking mappings

        Returns:
            Semantic replacement string
        """
        # Check if we already have a mapping for this text
        existing = mapping_store.get_replacement(entity.text)
        if existing:
            return existing

        # Lazy initialize
        self._lazy_init()

        # Try embedding-based replacement first
        if self.embeddings is not None:
            replacement = self._find_similar_replacement(entity)
            if replacement:
                return replacement

        # Fall back to pool-based replacement
        if self.use_fallback:
            return self._get_from_pool(entity.entity_type)

        # Last resort: return token-style
        return f"[{entity.entity_type.value.upper()}]"

    def _find_similar_replacement(self, entity: Entity) -> str | None:
        """Find semantically similar replacement using embeddings.

        Args:
            entity: Entity to replace

        Returns:
            Similar replacement or None
        """
        if self.embeddings is None:
            return None

        try:
            # For multi-word entities, use first word or most important
            words = entity.text.split()
            target_word = words[0] if words else entity.text

            # Find similar words
            similar = self.embeddings.most_similar(
                target_word,
                topn=20,
                exclude=self._used_replacements,
            )

            # Filter by threshold and find best match
            for word, similarity in similar:
                if similarity < self.similarity_threshold:
                    break

                # Check it's not already used
                if word.lower() not in {w.lower() for w in self._used_replacements}:
                    self._used_replacements.add(word)

                    # Reconstruct multi-word entity if needed
                    if len(words) > 1 and entity.entity_type == EntityType.PERSON:
                        # Try to find a matching last name
                        last_similar = self.embeddings.most_similar(
                            words[-1],
                            topn=10,
                            exclude=self._used_replacements,
                        )
                        if last_similar:
                            last_name = last_similar[0][0].title()
                            self._used_replacements.add(last_name)
                            return f"{word.title()} {last_name}"

                    return word.title()

        except Exception:
            # Embedding lookup failed
            pass

        return None

    def _get_from_pool(self, entity_type: EntityType) -> str:
        """Get replacement from fallback pool.

        Args:
            entity_type: Type of entity

        Returns:
            Replacement from pool
        """
        pool = self._fallback_pools.get(entity_type, [])

        # Filter out used replacements
        available = [
            w for w in pool
            if w.lower() not in {u.lower() for u in self._used_replacements}
        ]

        if available:
            replacement = random.choice(available)
            self._used_replacements.add(replacement)
            return replacement

        # Pool exhausted, generate numbered replacement
        count = len([
            u for u in self._used_replacements
            if u.startswith(entity_type.value.title())
        ])
        return f"{entity_type.value.title()}_{count + 1}"

    def get_context_aware_replacement(
        self,
        entity: Entity,
        context: str,
        mapping_store: MappingStore,
    ) -> str:
        """Generate replacement considering surrounding context.

        This enhanced method uses context to find more appropriate
        replacements (e.g., "CEO John Smith" -> find executive-like names).

        Args:
            entity: Entity to replace
            context: Surrounding text context
            mapping_store: Store for tracking mappings

        Returns:
            Context-aware replacement
        """
        # Check existing mapping
        existing = mapping_store.get_replacement(entity.text)
        if existing:
            return existing

        self._lazy_init()

        # Analyze context for role indicators
        role = self._detect_role(context, entity)

        # If we can detect a role, try role-aware replacement
        if role and self.embeddings is not None:
            replacement = self._find_role_aware_replacement(entity, role)
            if replacement:
                return replacement

        # Fall back to standard replacement
        return self.generate_replacement(entity, mapping_store)

    def _detect_role(self, context: str, entity: Entity) -> str | None:
        """Detect the role of an entity from context.

        Args:
            context: Text context
            entity: Entity to analyze

        Returns:
            Detected role or None
        """
        context_lower = context.lower()

        # Role patterns for PERSON
        if entity.entity_type == EntityType.PERSON:
            role_patterns = {
                "executive": ["ceo", "cto", "cfo", "president", "executive", "director"],
                "doctor": ["doctor", "dr.", "physician", "surgeon", "md"],
                "lawyer": ["attorney", "lawyer", "counsel", "esquire"],
                "engineer": ["engineer", "developer", "architect"],
                "scientist": ["scientist", "researcher", "professor", "phd"],
            }

            for role, patterns in role_patterns.items():
                if any(p in context_lower for p in patterns):
                    return role

        return None

    def _find_role_aware_replacement(
        self,
        entity: Entity,
        role: str,
    ) -> str | None:
        """Find replacement appropriate for detected role.

        Args:
            entity: Entity to replace
            role: Detected role

        Returns:
            Role-appropriate replacement
        """
        # Role-specific name pools
        role_names = {
            "executive": [
                "Richard Chen", "Sarah Mitchell", "James Anderson",
                "Michelle Park", "David Brooks", "Jennifer Wu",
            ],
            "doctor": [
                "Dr. Smith", "Dr. Johnson", "Dr. Williams",
                "Dr. Patel", "Dr. Kim", "Dr. Garcia",
            ],
            "lawyer": [
                "Thompson", "Richardson", "Morrison",
                "Sullivan", "Henderson", "Patterson",
            ],
            "engineer": [
                "Alex Chen", "Jordan Lee", "Sam Kumar",
                "Chris Park", "Taylor Singh", "Morgan Liu",
            ],
            "scientist": [
                "Dr. Roberts", "Dr. Yamamoto", "Dr. Mueller",
                "Dr. Andersson", "Dr. Nakamura", "Dr. Costa",
            ],
        }

        names = role_names.get(role, [])
        available = [
            n for n in names
            if n.lower() not in {u.lower() for u in self._used_replacements}
        ]

        if available:
            replacement = random.choice(available)
            self._used_replacements.add(replacement)
            return replacement

        return None

    def clear_used(self) -> None:
        """Clear the set of used replacements."""
        self._used_replacements.clear()


def create_semantic_replacer(
    similarity_threshold: float = 0.6,
    use_fallback: bool = True,
) -> SemanticReplacer:
    """Factory function to create a semantic replacer.

    Args:
        similarity_threshold: Minimum similarity for replacements
        use_fallback: Whether to use fallback pools

    Returns:
        Configured SemanticReplacer instance
    """
    return SemanticReplacer(
        similarity_threshold=similarity_threshold,
        use_fallback=use_fallback,
    )
