# The `veil` command line

Use the CLI for text that may be shown in the conversation. For files you
must not read, use `scripts/veil_tool.py` instead: several commands here print
the original values.

Run `veil` or, without the entry point on `PATH`, `python -m veil.cli`.

| Command | Prints originals? | Purpose |
|---|---|---|
| `veil anonymize` | only with `--mapping` or `--json` | Replace sensitive values |
| `veil detect` | yes | List what is detected |
| `veil score` | yes | Show the score breakdown per entity |
| `veil reconstruct` | yes (that is its job) | Restore originals from a mapping file |
| `veil stats` | no | Show the configuration a profile runs with |
| `veil version` | no | Version and profile names |
| `veil serve` | no | HTTP API, see [http-api.md](http-api.md) |
| `veil app` | n/a | Desktop chat UI |

## anonymize

```bash
veil anonymize "Jane Example works at Acme, jane@example.com"
veil anonymize --input notes.txt --output notes.anon.txt
veil anonymize "text" --profile paranoid
veil anonymize "text" --profile ./corp.yaml        # custom YAML profile
veil anonymize "text" --mode faker --seed 42
veil anonymize "text" --mode semantic
veil anonymize "text" --hybrid                     # spaCy + patterns, merged
veil anonymize "text" --presidio                   # adds Presidio, implies --hybrid
veil anonymize "text" --no-ner                     # patterns only
veil anonymize "text" --no-patterns                # NER only
veil anonymize "text" --no-weighting               # replace every detection
veil anonymize "text" --mapping                    # also show the mapping table
veil anonymize "text" --json > run.json            # machine-readable, includes originals
```

`--json` output has `original`, `anonymized`, `entities`, `mappings`
(original → replacement), `profile`, `replacement_mode`, `detection_mode`.
Treat that file like the original document.

## reconstruct

Mappings live only inside a running process, so the CLI needs a mapping file:
the saved output of `veil anonymize --json`, or `MappingStore.to_dict()` from
Python.

```bash
veil anonymize "Jane Example, jane@example.com" --json > run.json
veil reconstruct "Reply to EMAIL_1 and cc [PERSON_1]" --mapping run.json
```

Token matching is tolerant of bracket style, case and `_`/`-`/space
separators, because models rewrite tokens.

## detect and score

```bash
veil detect "Jane Example, SSN 123-45-6789" --hybrid
veil score "Patient Jane Example, SSN 123-45-6789" --profile paranoid
```

`detect` shows type, text, confidence and source. `score` shows base weight,
context boost, rarity boost, total and whether the entity clears the profile
threshold. Both accept `--no-ner`, `--no-patterns`, `--profile`; `detect` also
accepts `--hybrid` and `--presidio`.

## stats and version

```bash
veil stats --profile paranoid
veil stats --profile ./corp.yaml --hybrid
veil version
```

`stats` reports which detectors and spaCy model load on this machine, the
pattern count, the threshold and the replacement mode.

## serve

```bash
veil serve --host 127.0.0.1 --port 8787 --profile balanced \
    --detection-mode hybrid --session-ttl 3600 --audit veil-audit.jsonl
```

## app

```bash
pip install "veil[desktop]"
veil app --port 7860            # --host, --share for a public Gradio link
```

A local chat UI: the user types real data, the configured provider (OpenAI,
Anthropic or a local Ollama model) receives tokens, and replies are shown
reconstructed. Provider, model, API key, profile and detection mode are set in
the UI and saved to `~/.config/veil/settings.json` (owner-only). `--share`
publishes the UI on a public URL; do not use it without the user asking.

## Errors

An unknown profile, mode or detection mode is an error, never a silent
fallback. A missing spaCy model or Presidio install stops the command with a
message naming what to install.
