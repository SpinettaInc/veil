# Helper script reference

`skills/veil/scripts/veil_tool.py` is a file-based front end to the pipeline,
written for agents. Unless `--reveal` is given, nothing it prints contains an
original value: summaries are counts, types, offsets and scores.

```bash
python veil_tool.py <command> [options]
python veil_tool.py <command> --help
```

| Command | Does | Prints |
|---|---|---|
| [`check`](#check) | Reports installed models and backends | Versions and readiness |
| [`anonymize`](#anonymize) | Writes anonymized copies and saves the session | Entity counts by type |
| [`scan`](#scan) | Scores detections without changing anything | Type, offsets, score and reasons |
| [`reconstruct`](#reconstruct) | Restores originals into a file | Number of replacements |
| [`session`](#session) | Inspects or deletes a session file | Counts and tokens |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Bad input or configuration: unreadable file, unknown profile or entity type, missing session, missing optional package |
| `2` | A requested detector could not load. Nothing was written. |

Error messages go to stderr and never quote document text.

## check

```bash
python veil_tool.py check
```

Prints the Veil version and install path, the spaCy models found, which
optional packages are present, and whether `standard` and `hybrid` detection
can start. Exits `2` if standard detection is not ready. See
[Installation](installation.md#3-check-it) for sample output.

## anonymize

```bash
python veil_tool.py anonymize INPUT [INPUT ...] (--out FILE | --out-dir DIR)
                              (--session FILE | --session-dir DIR) [options]
```

| Option | Meaning |
|---|---|
| `INPUT` | UTF-8 text files, or `-` for stdin |
| `--out FILE` | Output for a single input; `-` prints the anonymized text |
| `--out-dir DIR` | Output directory; files keep their names. Required for several inputs. |
| `--session FILE` | Mapping file shared by all inputs. Created if missing, extended if present. |
| `--session-dir DIR` | One session per input, saved as `<name>.session.json`; documents are not linkable |
| `--mode token\|faker\|semantic` | Replacement mode. Default `token`. |
| `--seed N` | Faker seed, for reproducible fake values |
| `--locale LOCALE` | Faker locale, default `en_US` |
| `--bracket-style square\|angle\|curly` | `[PERSON_1]`, `<PERSON_1>` or `{PERSON_1}` |
| `--types A,B` | Replace only these entity types, e.g. `PERSON,EMAIL` |
| `--audit FILE` | Append a counts-only JSONL [audit log](../guide/audit.md) |

Plus the [detection options](#detection-options).

Exactly one of `--session` and `--session-dir` is required. The command
refuses to write an output over one of its inputs.

Output:

```json
{
  "degraded": false,
  "files": [
    {
      "by_type": {"EMAIL": 1, "PERSON": 1, "PHONE": 1},
      "chars": 80,
      "degraded": false,
      "entities": 3,
      "input": "in.txt",
      "output": "work/in.anon.txt"
    }
  ],
  "session": "work/session.json",
  "session_mappings": {"EMAIL": 1, "PERSON": 1, "PHONE": 1}
}
```

`by_type` counts what was replaced in that file; `session_mappings` counts
everything the session now holds. With `--session-dir`, each file entry has
its own `session` path instead. With `--out -`, this summary goes to stderr.

## scan

```bash
python veil_tool.py scan INPUT [--reveal] [detection options]
```

Runs detection and scoring and changes nothing. Use it to compare profiles,
to see why something was or was not replaced, and to test a custom profile.

```json
{
  "degraded": false,
  "detection": {"mode": "standard", "ner_model": "en_core_web_sm", "pattern_count": 25},
  "entities": [
    {
      "confidence": 0.95,
      "end": 20,
      "factors": [
        "Entity type PERSON: 1.00",
        "Term rarity: +0.112",
        "Context patterns: +0.200 (Patient reference)"
      ],
      "score": 1.0,
      "source": "spacy",
      "start": 8,
      "type": "PERSON",
      "would_anonymize": true
    }
  ],
  "input": "notes.txt",
  "kept": 0,
  "threshold": 0.3,
  "would_anonymize": 1
}
```

`start` and `end` are character offsets into the input. `would_anonymize` is
true when `score` reaches `threshold`. `--reveal` adds the matched `text` to
each entity; it is meant for a person at a terminal.

## reconstruct

```bash
python veil_tool.py reconstruct INPUT --out FILE --session FILE
```

Replaces every token or fake value known to the session with its original.
`INPUT` may be `-` for stdin. `--out -` prints the restored text, which puts
the originals in front of whoever reads the output.

```json
{"input": "work/reply.md", "output": "reply.md", "replacements_made": 2}
```

A missing session file is an error, not an empty reconstruction.

## session

```bash
python veil_tool.py session FILE [--reveal] [--delete]
```

```json
{
  "by_type": {"EMAIL": 1, "PERSON": 2},
  "replacements": ["[EMAIL_1]", "[PERSON_1]", "[PERSON_2]"],
  "session": "work/session.json",
  "total_mappings": 3,
  "unique_originals": 3,
  "unique_replacements": 3
}
```

`--reveal` prints the replacement → original mapping. `--delete` removes the
file; after that, nothing anonymized with it can be reconstructed.

## Detection options

Accepted by `anonymize` and `scan`.

| Option | Meaning |
|---|---|
| `--profile NAME\|PATH` | `paranoid`, `balanced` (default), `minimal`, or a [YAML profile](../guide/profiles.md#custom-profiles-yaml) |
| `--hybrid` | Merge spaCy and pattern detections, boosting those several detectors agree on |
| `--presidio` | Add Microsoft Presidio to the ensemble; implies `--hybrid` |
| `--no-ner` | Patterns only |
| `--no-patterns` | Named-entity recognition only |
| `--no-weighting` | Replace every detection, skip scoring |
| `--spacy-model NAME` | Use a specific spaCy model; default is the best installed |
| `--min-confidence X` | Drop detections below this detector confidence |
| `--allow-degraded` | Continue when a detector cannot load. The output may still contain sensitive data and the summary says `"degraded": true`. |

## Session file format

The session file is the JSON form of a `MappingStore` (`to_dict()`), so it
also works with `veil reconstruct --mapping` and `MappingStore.from_dict()`.

```json
{
  "mappings": [
    {"original": "...", "replacement": "[PERSON_1]", "entity_type": "PERSON", "count": 2}
  ]
}
```
