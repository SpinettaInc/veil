"""TF-IDF inspired rarity scoring for entity importance.

Rare terms in a document are more likely to be identifying,
similar to how TF-IDF works in information retrieval.
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class DocumentStats:
    """Statistics about a document for rarity calculation.

    Attributes:
        term_counts: Count of each term (lowercased, normalized)
        total_terms: Total number of terms in document
        unique_terms: Number of unique terms
    """

    term_counts: Counter[str]
    total_terms: int
    unique_terms: int

    @classmethod
    def from_text(cls, text: str) -> "DocumentStats":
        """Calculate document statistics from text.

        Args:
            text: Document text to analyze

        Returns:
            DocumentStats instance
        """
        # Tokenize: split on whitespace and punctuation
        tokens = re.findall(r"\b\w+\b", text.lower())

        term_counts = Counter(tokens)
        total_terms = len(tokens)
        unique_terms = len(term_counts)

        return cls(
            term_counts=term_counts,
            total_terms=total_terms,
            unique_terms=unique_terms,
        )

    def term_frequency(self, term: str) -> int:
        """Get the frequency of a term in the document.

        Args:
            term: Term to look up

        Returns:
            Number of occurrences
        """
        return self.term_counts.get(term.lower(), 0)

    def term_frequency_normalized(self, term: str) -> float:
        """Get normalized term frequency (TF).

        Normalized by total terms in document.

        Args:
            term: Term to look up

        Returns:
            Normalized frequency (0.0 to 1.0)
        """
        if self.total_terms == 0:
            return 0.0
        return self.term_frequency(term) / self.total_terms

    def is_hapax(self, term: str) -> bool:
        """Check if term appears only once (hapax legomenon).

        Hapax legomena (words appearing once) are often more identifying.

        Args:
            term: Term to check

        Returns:
            True if term appears exactly once
        """
        return self.term_frequency(term) == 1


class RarityScorer:
    """Calculate rarity scores for terms.

    Rarity is inverse of frequency - rare terms get higher scores
    because they're more likely to be identifying.

    The scoring is inspired by TF-IDF but simplified for our use case:
    - We only care about within-document frequency
    - Rare terms = higher privacy risk
    """

    def __init__(
        self,
        min_score: float = 0.0,
        max_score: float = 1.0,
        hapax_boost: float = 0.1,
    ) -> None:
        """Initialize the rarity scorer.

        Args:
            min_score: Minimum rarity score
            max_score: Maximum rarity score
            hapax_boost: Extra boost for terms appearing only once
        """
        self.min_score = min_score
        self.max_score = max_score
        self.hapax_boost = hapax_boost

    def score(self, term: str, doc_stats: DocumentStats) -> float:
        """Calculate rarity score for a term.

        Higher score = rarer term = more identifying.

        Scoring formula:
        - Base score from inverse frequency
        - Boost for hapax legomena (single occurrences)
        - Normalized to [min_score, max_score]

        Args:
            term: Term to score
            doc_stats: Document statistics

        Returns:
            Rarity score (higher = rarer = more sensitive)
        """
        freq = doc_stats.term_frequency(term)

        if freq == 0:
            # Term not in document - treat as maximally rare
            return self.max_score

        # Inverse frequency: 1/freq gives higher scores to rare terms
        # Using log to smooth the curve for very frequent terms
        if doc_stats.total_terms > 0:
            # Log-scaled inverse frequency
            inverse_freq = math.log(doc_stats.total_terms / freq + 1)
            max_inverse = math.log(doc_stats.total_terms + 1)
            score = inverse_freq / max_inverse if max_inverse > 0 else 0.5
        else:
            score = 0.5

        # Boost for hapax legomena
        if doc_stats.is_hapax(term):
            score += self.hapax_boost

        # Clamp to range
        return max(self.min_score, min(self.max_score, score))

    def score_multi_word(self, phrase: str, doc_stats: DocumentStats) -> float:
        """Calculate rarity score for a multi-word phrase.

        For phrases like "John Smith", we consider:
        - Rarity of the complete phrase
        - Average rarity of individual words

        Args:
            phrase: Multi-word phrase to score
            doc_stats: Document statistics

        Returns:
            Combined rarity score
        """
        # Score the full phrase
        phrase_score = self.score(phrase.lower().replace(" ", "_"), doc_stats)

        # Score individual words
        words = phrase.lower().split()
        if not words:
            return phrase_score

        word_scores = [self.score(word, doc_stats) for word in words]
        avg_word_score = sum(word_scores) / len(word_scores)

        # Combine: weight phrase score higher if it's a true multi-word entity
        if len(words) > 1:
            # Multi-word phrases: 70% phrase score, 30% word average
            return 0.7 * phrase_score + 0.3 * avg_word_score
        else:
            return phrase_score


class GlobalRarityScorer(RarityScorer):
    """Rarity scorer that considers global (corpus) statistics.

    In addition to document-level rarity, this scorer can consider
    how rare a term is across a larger corpus (like common names
    vs. unusual names).
    """

    # Common English words that should get low rarity scores
    COMMON_WORDS = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her",
        "she", "or", "an", "will", "my", "one", "all", "would", "there",
        "their", "what", "so", "up", "out", "if", "about", "who", "get",
        "which", "go", "me", "is", "are", "was", "were", "been", "has",
    }

    # Common first names (lowered rarity = more common)
    COMMON_NAMES = {
        "john", "james", "michael", "david", "robert", "william", "richard",
        "joseph", "thomas", "charles", "mary", "patricia", "jennifer", "linda",
        "elizabeth", "barbara", "susan", "jessica", "sarah", "karen", "emma",
        "olivia", "ava", "sophia", "isabella", "mia", "charlotte", "amelia",
        "harper", "evelyn", "liam", "noah", "oliver", "elijah", "lucas",
        "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
        "davis", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    }

    def __init__(
        self,
        min_score: float = 0.0,
        max_score: float = 1.0,
        hapax_boost: float = 0.1,
        common_word_penalty: float = 0.3,
        common_name_penalty: float = 0.15,
    ) -> None:
        """Initialize the global rarity scorer.

        Args:
            min_score: Minimum rarity score
            max_score: Maximum rarity score
            hapax_boost: Extra boost for hapax legomena
            common_word_penalty: Penalty for common English words
            common_name_penalty: Penalty for common names
        """
        super().__init__(min_score, max_score, hapax_boost)
        self.common_word_penalty = common_word_penalty
        self.common_name_penalty = common_name_penalty

    def score(self, term: str, doc_stats: DocumentStats) -> float:
        """Calculate rarity score with global adjustments.

        Args:
            term: Term to score
            doc_stats: Document statistics

        Returns:
            Adjusted rarity score
        """
        base_score = super().score(term, doc_stats)
        term_lower = term.lower()

        # Penalize common words
        if term_lower in self.COMMON_WORDS:
            base_score -= self.common_word_penalty

        # Slight penalty for very common names (still identifiable, just less unique)
        if term_lower in self.COMMON_NAMES:
            base_score -= self.common_name_penalty

        return max(self.min_score, min(self.max_score, base_score))
