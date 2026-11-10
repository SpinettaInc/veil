# Changelog

## Unreleased

### Agent skill
- `skills/veil/`: an Agent Skill (instructions, reference pages and `scripts/veil_tool.py`) that lets an AI agent anonymize files by path, work on the anonymized copy and reconstruct the result without reading the originals. The helper prints counts, offsets and scores only; session files are written `0600`.

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

### Fixes from the code review
- **Fail-closed gaps:** hybrid mode ignored a missing spaCy model or a failed Presidio load (no error, no `degraded` flag); unknown `detection_mode`, `replacement_mode` and profile names silently fell back to defaults. All now raise.
- **Proxy leaks:** the system prompt and non-user turns of a caller-supplied history were sent un-anonymised; the desktop app passed its displayed (reconstructed) history back to the provider. Streaming now also reconstructs replacements split across chunks in faker mode and in rewritten forms (`Person_` + `1`), and a failed stream still records the turn.
- **Round trip:** two originals could receive the same fake value (and be restored as one); semantic mode gave every e-mail `Email_1`; URLs differing only in case were merged; `anonymize_batch(separate_sessions=True)` wiped the mappings of earlier results (each result now keeps its own store, `reconstruct(text, mapping_store=...)`).
- **Overlap merge:** an entity could be dropped because of a neighbour that itself lost; untyped store lookups missed non-person values ending in `'s`.
- **Patterns:** IBAN followed by `BIC`/`EUR`, IPv6 with `::`, `MRN: 123`, Mastercard 2-series / Diners / UnionPay, `+44 7911 123456`. No longer matched: `2 steps that way` as an address, cue words inside other words (`capacity`, `hotel`, `statement`, `accounting`), bare nine-digit numbers as SSNs without a cue. The e-mail regex was quadratic on long dotted runs.
- **CLI:** `--json` printed wrapped, markup-mangled JSON; tracebacks printed the input text; `veil reconstruct` could not read any file the CLI produces and ignored rewritten tokens.
- **Server:** non-string `session_id`, negative `Content-Length` and unexpected errors left requests unanswered; `reconstruct` could create an empty session for an expired id.
- **Settings:** the file holding the API key was world-readable; an unknown key discarded the whole file.
- Faker seeding no longer reseeds the global `random`/Faker generators.
- **Rarity:** a multi-term entity (`New York`, an e-mail address) was always scored as unseen; the term sequence is now counted in the document.
- Fake values are no longer restored from inside a longer word (`West` in `Western`); lowercase IBANs are detected; custom labels with digits or hyphens (`SKU2`, `EMPLOYEE-ID`) round-trip when the model drops the brackets.
- Guardrails validators run each validation in its own session and reject unknown entity types; `veil stats` takes `--profile`/`--hybrid` instead of always describing an empty default pipeline.
- Removed the part-of-speech multipliers (`pos_multipliers`), which were never applied; the key is ignored in existing profile files.

### Features
- YAML profiles are the source of truth; custom profiles with `custom_patterns` and custom token labels; `--profile path.yaml`.
- `anonymize_batch` (batched spaCy), `veil serve` HTTP API with per-session mappings, `veil.audit` JSONL audit log + `summarize()`.
- Optional `wordfreq`-based rarity (`[rarity]` extra).

### Performance
- spaCy models cached and shared (also with Presidio); NER-only pipeline in standard mode.
- Relationship scoring O(n) per document; hybrid grouping O(n log n); 60 KB document 7.0 s → 0.65 s.

### Tooling
- mypy strict clean, ruff clean, `desktop` pytest marker, GitHub Actions CI, runnable `examples/` executed by the test suite.
