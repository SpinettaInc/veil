"""Regression tests for detection precision and scoring behaviour.

These pin down the fixes measured by benchmarks/run.py: structured PII must win
over generic NER labels, loose regexes need context, non-identifying temporal
and numeric spans are dropped, and weak detections do not inherit full weight.
"""

import pytest

from veil.detection.entity import Entity, EntityType, merge_overlapping_entities
from veil.detection.ner import SPACY_AVAILABLE, is_false_positive
from veil.detection.patterns import PatternDetector, validate_iban
from veil.weighting.context import RelationshipAnalyzer
from veil.weighting.scorer import PrivacyScorer


def _pattern_hits(text: str) -> dict[str, str]:
    return {e.text: e.entity_type.value for e in PatternDetector().detect(text)}


class TestMergeSpecificity:
    def test_structured_pii_beats_more_confident_generic_label(self):
        card = Entity(
            "4111111111111111", EntityType.CREDIT_CARD, 0, 16, confidence=0.8, source="pattern"
        )
        cardinal = Entity(
            "4111111111111111", EntityType.CARDINAL, 0, 16, confidence=0.9, source="spacy"
        )
        merged = merge_overlapping_entities([cardinal, card])
        assert [e.entity_type for e in merged] == [EntityType.CREDIT_CARD]

    def test_named_entity_beats_date(self):
        person = Entity("May Johnson", EntityType.PERSON, 0, 11, confidence=0.85)
        date = Entity("May", EntityType.DATE, 0, 3, confidence=0.95)
        merged = merge_overlapping_entities([date, person])
        assert [e.entity_type for e in merged] == [EntityType.PERSON]

    def test_same_specificity_falls_back_to_confidence_then_length(self):
        a = Entity("John", EntityType.PERSON, 0, 4, confidence=0.9)
        b = Entity("John Smith", EntityType.PERSON, 0, 10, confidence=0.9)
        assert merge_overlapping_entities([a, b])[0].text == "John Smith"
        c = Entity("John Smith", EntityType.PERSON, 0, 10, confidence=0.7)
        assert merge_overlapping_entities([a, c])[0].text == "John"

    def test_chain_of_overlaps_is_linear_and_non_overlapping(self):
        entities = [
            Entity(f"e{i}", EntityType.PERSON, i * 3, i * 3 + 5, confidence=0.5 + (i % 3) / 10)
            for i in range(500)
        ]
        merged = merge_overlapping_entities(entities)
        for prev, nxt in zip(merged, merged[1:]):
            assert prev.end <= nxt.start


class TestContextGatedPatterns:
    def test_long_digit_run_is_not_a_bank_account_without_context(self):
        assert "BANK_ACCOUNT" not in _pattern_hits("Order #12345678 shipped yesterday.").values()

    def test_long_digit_run_is_a_bank_account_with_context(self):
        assert _pattern_hits("Bank account 12345678 is closed.")["12345678"] == "BANK_ACCOUNT"

    def test_five_digits_are_not_a_zip_without_context(self):
        assert _pattern_hits("The SKU is 55512.") == {}

    def test_phone_tail_is_not_a_japanese_postal_code(self):
        hits = _pattern_hits("Call us at (555) 123-4567 today.")
        assert hits == {"(555) 123-4567": "PHONE"}

    def test_generic_phone_needs_context(self):
        assert _pattern_hits("ISBN 978-3-16-148410-0 is out of print.") == {}


class TestPatternFormats:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Fax: +1 (212) 555-0188", "+1 (212) 555-0188"),
            ("Call 1-800-555-0199 now", "1-800-555-0199"),
            ("Tel: 555.867.5309", "555.867.5309"),
            ("Reach me on +61412345678 anytime.", "+61412345678"),
        ],
    )
    def test_phone_formats(self, text, expected):
        assert _pattern_hits(text).get(expected) == "PHONE"

    def test_amex_with_spaces(self):
        assert (
            _pattern_hits("Amex 3782 822463 10005 was declined.")["3782 822463 10005"]
            == "CREDIT_CARD"
        )

    def test_iban_with_spaces_and_checksum(self):
        assert validate_iban("DE89 3704 0044 0532 0130 00")
        assert not validate_iban("DE89 3704 0044 0532 0130 01")
        assert (
            _pattern_hits("IBAN: DE89 3704 0044 0532 0130 00")["DE89 3704 0044 0532 0130 00"]
            == "IBAN"
        )

    def test_iso_timestamp_and_dmy_dates(self):
        hits = _pattern_hits("ERROR 2024-01-15T10:30:00Z admitted 15/03/2024")
        assert hits["2024-01-15"] == "DATE"
        assert hits["15/03/2024"] == "DATE"


class TestNerFalsePositiveFilter:
    @pytest.mark.parametrize(
        "text,label",
        [
            ("yesterday", "DATE"),
            ("Friday", "DATE"),
            ("2019", "DATE"),
            ("3-5 days", "DATE"),
            ("the year 1999", "DATE"),
            ("45 minutes", "TIME"),
            ("12345678", "MONEY"),
            ("Connect", "NORP"),
            ("v1.2.3", "ORG"),
            ("Email", "PERSON"),
            ("NW", "GPE"),
            ("Q3", "GPE"),
            ("Highway 101", "FAC"),
            ("Highway 101", "LOC"),
        ],
    )
    def test_dropped(self, text, label):
        assert is_false_positive(text, label)

    @pytest.mark.parametrize(
        "text,label",
        [
            ("March 15, 1985", "DATE"),
            ("1985-03-15", "DATE"),
            ("10:30", "TIME"),
            ("$50 million", "MONEY"),
            ("Acme Corporation", "ORG"),
            ("Aisha Al-Rashid", "PERSON"),
            ("New York", "GPE"),
        ],
    )
    def test_kept(self, text, label):
        assert not is_false_positive(text, label)


class TestScoring:
    def test_weak_detection_does_not_inherit_full_weight(self):
        scorer = PrivacyScorer()
        strong = Entity("X", EntityType.BANK_ACCOUNT, 0, 1, confidence=0.9)
        weak = Entity("X", EntityType.BANK_ACCOUNT, 0, 1, confidence=0.4)
        s_strong = scorer.score_entity(strong, "X")
        s_weak = scorer.score_entity(weak, "X")
        assert s_strong.confidence_factor == 1.0
        assert s_weak.confidence_factor == pytest.approx(0.55)
        assert s_weak.total_score < s_strong.total_score

    def test_bare_numbers_get_no_context_boost(self):
        scorer = PrivacyScorer()
        text = "Bank account 12345678 sort code 40-47-84."
        num = Entity(
            "40", EntityType.CARDINAL, text.index("40"), text.index("40") + 2, confidence=0.85
        )
        score = scorer.score_entity(num, text)
        assert score.context_boost == 0.0
        assert not score.above_threshold

    def test_relationship_boost_precomputed_matches_per_entity(self):
        text = "John Smith, CEO of Acme Corp, lives in Boston."
        ents = [
            Entity("John Smith", EntityType.PERSON, 0, 10),
            Entity("Acme Corp", EntityType.ORG, 19, 28),
            Entity("Boston", EntityType.GPE, 39, 45),
        ]
        analyzer = RelationshipAnalyzer()
        by_id = analyzer.boosts_by_entity(ents, text)
        for e in ents:
            assert by_id.get(id(e), 0.0) == analyzer.calculate_relationship_boost(e, ents, text)
        assert by_id[id(ents[0])] > 0

    def test_score_entities_uses_precomputed_boosts(self):
        scorer = PrivacyScorer()
        text = "John Smith, CEO of Acme Corp."
        ents = [
            Entity("John Smith", EntityType.PERSON, 0, 10),
            Entity("Acme Corp", EntityType.ORG, 19, 28),
        ]
        scores = scorer.score_entities(ents, text)
        assert scores[0].relationship_boost == scores[1].relationship_boost > 0

    def test_doc_stats_cache_is_bounded(self):
        scorer = PrivacyScorer()
        e = Entity("x", EntityType.PERSON, 0, 1)
        for i in range(100):
            scorer.score_entity(e, f"document number {i}")
        assert len(scorer._doc_stats_cache) <= scorer._doc_stats_cache_size


@pytest.mark.skipif(not SPACY_AVAILABLE, reason="spaCy not installed")
class TestPipelineEndToEnd:
    @pytest.fixture(scope="class")
    def pipeline(self):
        from veil import VeilPipeline

        try:
            return VeilPipeline()
        except OSError:
            pytest.skip("no spaCy model installed")

    def test_spacy_model_is_shared_between_pipelines(self, pipeline):
        from veil import VeilPipeline

        other = VeilPipeline()
        assert other.detector.ner_detector.nlp is pipeline.detector.ner_detector.nlp

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Payment card: 4111111111111111", "[CREDIT_CARD_1]"),
            ("Tel: 555.867.5309", "[PHONE_1]"),
            ("Connect to 2001:0db8:85a3:0000:0000:8a2e:0370:7334 now.", "[IP_ADDRESS_1]"),
        ],
    )
    def test_structured_pii_is_anonymized(self, pipeline, text, expected):
        pipeline.clear_mappings()
        assert expected in pipeline.anonymize(text).anonymized_text

    @pytest.mark.parametrize(
        "text",
        [
            "Order #12345678 shipped yesterday and should arrive in 3-5 days.",
            "We upgraded to version 2.3.1 and the build number is 20240115.",
            "The meeting is at 10:30 and lasts 45 minutes.",
            "Your one-time code is 483920. It expires in 10 minutes.",
            "Take exit 42 onto Highway 101 north.",
        ],
    )
    def test_non_pii_text_is_untouched(self, pipeline, text):
        pipeline.clear_mappings()
        assert pipeline.anonymize(text).anonymized_text == text

    def test_round_trip(self, pipeline):
        pipeline.clear_mappings()
        text = "Email maria.garcia@hospital.org or call 212-555-0147 about patient Luis Ortega."
        result = pipeline.anonymize(text)
        assert result.entity_count == 3
        assert pipeline.reconstruct(result.anonymized_text).reconstructed_text == text
