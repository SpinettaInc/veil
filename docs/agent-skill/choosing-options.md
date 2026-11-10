# Choosing options

The defaults (`balanced` profile, standard detection, token replacement) suit
general business text that goes through a model. Change them when the task
calls for it. Use `scan` to see the effect before anonymizing:

```bash
python veil_tool.py scan input.txt --profile paranoid
```

## Profile

A profile sets how sensitive a detection must be before it is replaced.

| Profile | Threshold | Replaces | Use for |
|---|---|---|---|
| `paranoid` | 0.3 | Almost everything detected, including dates, places and organizations | Medical, legal, financial, HR, anything regulated |
| `balanced` | 0.5 | People and identifiers; well-known brands and bare numbers stay | General business text |
| `minimal` | 0.8 | Only unmistakable identifiers | Text where names of public bodies and places must stay readable |

`--no-weighting` skips scoring and replaces every detection.

House identifiers such as employee numbers or project codes need a custom
profile:

```yaml
# corp.yaml
threshold: 0.45
entity_weights:
  EMPLOYEE_ID: 0.95
custom_patterns:
  - name: employee_id
    entity_type: EMPLOYEE_ID        # token becomes [EMPLOYEE_ID_1]
    regex: "\\bEMP-\\d{5}\\b"
    confidence: 0.95
```

```bash
python veil_tool.py anonymize in.txt --out out.txt --session s.json --profile corp.yaml
```

See [Detection Profiles](../guide/profiles.md) for the scoring formula and
the full YAML format.

## Detection

| Option | Trade-off |
|---|---|
| default (standard) | spaCy names plus validated patterns. Fast, no extra installs. |
| `--hybrid` | Detectors vote; agreement raises confidence. Better recall, somewhat slower. |
| `--presidio` | Adds Microsoft Presidio's recognizers to the vote. Needs `presidio-analyzer`. |
| `--no-ner` | Structured identifiers only (e-mail, phone, card, IBAN, IP). Fastest; names are not detected. |
| `--no-patterns` | Names, organizations and places only. |
| `--types PERSON,EMAIL` | Replace only the listed types and leave the rest readable. |
| `--spacy-model en_core_web_lg` | The larger model finds more names. Used automatically when installed. |
| `--min-confidence 0.6` | Fewer false positives, at the cost of recall. |

On the project's benchmark, the small spaCy model scores F1 0.96 and the
large one 0.99 or better. Install `en_core_web_lg` when names matter.

## Replacement mode

| Mode | Output | Use it when |
|---|---|---|
| `token` (default) | `[PERSON_1]`, `[EMAIL_1]` | The text goes through a model. Tokens are copied faithfully and are plainly not real data. |
| `faker` | Realistic fake values | The result must look natural: demos, test fixtures, screenshots. Needs `faker`. |
| `semantic` | Substitutes of a similar kind | Analysis that depends on what kind of name or organization appears. Needs `gensim`; without it, fixed pools are used. |

Faker options: `--seed N` gives the same fake values on every run, and
`--locale de_DE` produces values for that locale.

`--bracket-style angle` or `curly` changes tokens to `<PERSON_1>` or
`{PERSON_1}` for formats where square brackets clash with the syntax.

!!! warning "Fake values and models"
    In `faker` and `semantic` modes the output reads like real data. A model
    that shortens or "corrects" a fake name ("Mr. Hamilton" for "Benjamin
    Hamilton") produces a variant that cannot be mapped back. Use `token`
    whenever a model will rewrite the text.

## Sessions

| Situation | Option |
|---|---|
| Files about the same case; the same person should have the same token | `--session FILE` |
| A long task run in several steps | The same `--session FILE` each time |
| Unrelated documents that must not be linkable | `--session-dir DIR` |

## Audit

`--audit audit.jsonl` appends one line per operation with entity counts,
timing, profile and the degraded flag. It never records text, values or
tokens, so it can be retained. See [Audit Log](../guide/audit.md).

## Which interface

The helper script covers files. For other shapes of task the skill points the
agent to a reference page:

| Task | Interface | Guide |
|---|---|---|
| Short text already in the conversation, a demo | `veil` CLI | [CLI Reference](../guide/cli.md) |
| Python code: pipelines, batches, custom patterns | `VeilPipeline` | [Python API](../guide/python-api.md) |
| Calling a model from code so it only sees tokens | `VeilProxy` | [LLM Providers](../integrations/llm-providers.md) |
| Other languages, several tools sharing sessions | `veil serve` | [API Server](../guide/api-server.md) |
| Guardrails AI pipelines | Validators | [Guardrails AI](../integrations/guardrails.md) |
| A person chatting with a model | `veil app` | [Desktop App](../guide/desktop-app.md) |
