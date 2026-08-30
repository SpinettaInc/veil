# Changelog

## Unreleased

### Precision
- Overlap resolution ranks by type specificity (structured PII > named entity > generic NER label), then confidence, then length; hybrid agreement groups use the same rank.
- Loose regexes (bank account, ZIP codes, generic phone, driver licence) require a nearby cue word; IBANs are mod-97 validated and accept spaces; phones with parentheses/`+` and DD/MM/YYYY / ISO-timestamp dates are recognised.
- NER filter drops relative dates and durations, field labels and job titles, version strings, fiscal quarters, compass points, numbered roads, sentence-initial verbs and anything shaped like a Veil token; applied to Presidio's spaCy spans too.
- Detector confidence feeds the privacy score; bare numbers get no context boosts; well-known brands get a low weight (`public_entities`).
- Labeled benchmark (`benchmarks/`) with a CI gate; F1 0.79 → 0.99 on it.

### Correctness / safety
- Fail-closed: `DetectionUnavailableError` when a requested detector cannot load (`strict=False` → `degraded=True`).
- One token per person across spellings/titles/partial names; canonical original is the fullest form.
- Tolerant reconstruction of LLM-rewritten tokens; input that already contains tokens is never clobbered; second passes never alter existing tokens (fuzz-tested).
- `VeilProxy` owns the conversation history and anonymises caller-supplied history; streaming yields reconstructed text and never splits a token.
- Fake replacement values never collide with the input.

### Features
- YAML profiles are the source of truth; custom profiles with `custom_patterns` and custom token labels; `--profile path.yaml`.
- `anonymize_batch` (batched spaCy), `veil serve` HTTP API with per-session mappings, `veil.audit` JSONL audit log + `summarize()`.
- Optional `wordfreq`-based rarity (`[rarity]` extra).

### Performance
- spaCy models cached and shared (also with Presidio); NER-only pipeline in standard mode.
- Relationship scoring O(n) per document; hybrid grouping O(n log n); 60 KB document 7.0 s → 0.65 s.

### Tooling
- mypy strict clean, ruff clean, `desktop` pytest marker, GitHub Actions CI, runnable `examples/` executed by the test suite.
