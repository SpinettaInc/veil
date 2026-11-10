---
name: veil
description: Anonymize personal and sensitive data (names, e-mails, phones, IDs, cards, IBANs, addresses, medical record numbers, custom identifiers) locally with Veil before a model or external service sees it, then restore the originals in the result. Use when the user asks to anonymize, redact, pseudonymize, mask or de-identify text or files; when a task involves documents that contain or may contain PII, client data or secrets that must not reach a hosted model; when wiring privacy protection into an LLM call, an HTTP service or a Guardrails pipeline; or when the user mentions Veil.
license: GPL-3.0-only
---

# Veil

Veil detects sensitive values in text, replaces them with tokens such as
`[PERSON_1]` (or with fake values), and can put the originals back afterwards.
Detection runs on this machine. The mapping from token to original never
leaves it.

This skill works with any model and any agent runtime. It needs a shell and
Python 3.10+. Paths below are relative to this skill's directory.

## The rule that makes this useful

**Anything you read has already reached your model.** So when a file may
contain sensitive data:

1. Do not open, print, `cat` or grep the original file.
2. Run Veil on it by path and read only the anonymized copy.
3. Do your work on the anonymized copy, keeping its tokens intact.
4. Restore the originals into an output file with Veil. Do not read that file
   back; give the user its path.

`scripts/veil_tool.py` exists for this: it takes file paths and prints only
counts, types, offsets and scores. The plain `veil` CLI is for text that is
already in the conversation or that the user wants shown, because `veil
detect`, `veil score`, `--mapping` and `--json` all print the original values.

If the user pasted sensitive text straight into the conversation, it has
already been seen. Say so, anonymize it for any further processing or
sub-agent hand-off, and do not repeat the raw values in your replies.

## 1. Check the install

```bash
python scripts/veil_tool.py check
```

This prints the Veil version, which spaCy models and optional backends are
installed, and whether `standard` and `hybrid` detection are ready. If `veil`
is not importable:

```bash
pip install "git+https://github.com/SpinettaInc/veil.git"
python -m spacy download en_core_web_sm        # en_core_web_lg is more accurate
pip install faker presidio-analyzer            # optional: faker mode, hybrid mode
```

Inside a checkout of the Veil repository, `PYTHONPATH=src` in front of the
command uses that checkout.

Veil is **fail-closed**. If a detector that was asked for cannot load, the
tool exits with code 2 and writes nothing. Install the missing piece; do not
reach for `--allow-degraded` unless the user accepts that the output may
still contain sensitive data.

## 2. Anonymize, work, reconstruct

```bash
# 1. Anonymize. The session file holds the token -> original mapping.
python scripts/veil_tool.py anonymize input.txt \
    --out work/input.anon.txt --session work/session.json

# 2. Read work/input.anon.txt and do the task. Write your result to a file,
#    e.g. work/result.anon.md, using the tokens exactly as they appear.

# 3. Restore the originals. Hand the user the output path.
python scripts/veil_tool.py reconstruct work/result.anon.md \
    --out result.md --session work/session.json
```

Several files that belong together share one session, so the same person gets
the same token in all of them:

```bash
python scripts/veil_tool.py anonymize a.txt b.txt c.txt \
    --out-dir work/anon --session work/session.json
```

Run it again later with the same `--session` and the mapping is extended, not
replaced. Use `--session-dir DIR` instead to give every input its own
session, so nothing links one document to another.

Text from stdin and to stdout: `anonymize - --out - --session s.json` (the
summary then goes to stderr).

The session file contains the original values. It is written owner-only
(`0600`). Never read it, print it, commit it or send it anywhere. When the
task is finished and the user no longer needs to reconstruct, delete it:
`python scripts/veil_tool.py session work/session.json --delete`.

### Working with tokens

- Keep tokens verbatim: `[PERSON_1]`, not "person 1" or "the first person".
  Reconstruction tolerates `PERSON_1`, `<PERSON_1>`, `[person 1]` and
  `[PERSON-1]`, but never a changed number.
- A token stands for one real value everywhere in the session. `[PERSON_1]`
  and `[PERSON_2]` are different people.
- Do not invent tokens. One with no mapping is left as it is.
- Do not guess what a token stands for.
- Tokens already present in an input are left alone and their numbers are not
  reused.

## 3. Choose the options

All of these apply to `anonymize` and `scan`.

| Need | Option |
|---|---|
| Medical, legal, financial, HR, anything regulated | `--profile paranoid` (threshold 0.3) |
| General business text (default) | `--profile balanced` (threshold 0.5) |
| Only unmistakable identifiers; keep names of public bodies and places | `--profile minimal` (threshold 0.8) |
| House identifiers (employee IDs, ticket or project codes) | `--profile path/to/profile.yaml`, see [references/profiles.md](references/profiles.md) |
| Replace everything detected, no scoring | `--no-weighting` |
| Best recall, several detectors voting | `--hybrid`, or `--presidio` to add Microsoft Presidio |
| Only some kinds of entity | `--types PERSON,EMAIL,PHONE` |
| Structured identifiers only, fastest | `--no-ner` |
| Named entities only | `--no-patterns` |
| A specific spaCy model | `--spacy-model en_core_web_lg` |
| Drop low-confidence detections | `--min-confidence 0.6` |

Replacement mode (`anonymize` only):

| Mode | Output | Use it when |
|---|---|---|
| `--mode token` (default) | `[PERSON_1]`, `[EMAIL_1]` | Almost always. Safest to reconstruct, and plainly not real data. |
| `--mode faker` | realistic fake values | The result must look natural, such as demo or test data. `--seed N` makes it reproducible, `--locale de_DE` localizes it. Needs `faker`. |
| `--mode semantic` | similar-looking substitutes | Analysis that depends on the kind of name or organization. Needs `gensim` for embeddings and falls back to fixed pools without it. |

`--bracket-style angle|curly` changes token brackets to `<PERSON_1>` or
`{PERSON_1}` for formats where square brackets collide with the syntax.

In faker and semantic modes the output reads like real data, and a model that
rewrites a fake name ("Mr. Hamilton" for "Benjamin Hamilton") breaks
reconstruction. Prefer token mode whenever the text goes through a model.

`--audit audit.jsonl` appends one line per operation with counts, timing,
profile and the degraded flag. It never records text, so it can be kept.

## 4. Check what Veil will do

```bash
python scripts/veil_tool.py scan input.txt --profile balanced
```

`scan` lists each detection with its type, position, detector, confidence,
privacy score, the reasons behind the score, and whether it clears the
profile threshold. It does not print the matched text. Use it to:

- compare profiles before choosing one;
- explain why something was or was not anonymized;
- confirm a custom profile catches the house identifiers.

Detection is statistical. After anonymizing, skim the anonymized copy: if
something that looks sensitive survived, do not quote it. Re-run with
`--profile paranoid`, `--hybrid` or `--no-weighting`, or add a custom pattern,
and tell the user what was missed.

## 5. Other ways to run Veil

Pick the interface that fits the task. Each has a reference page with the
details.

| Task | Use | Reference |
|---|---|---|
| Short text already in the conversation, a quick demo, showing the user what is detected | `veil` CLI | [references/cli.md](references/cli.md) |
| Custom entity types and tuning weights | profile YAML | [references/profiles.md](references/profiles.md) |
| Writing Python: pipelines, batches, sessions, custom patterns, audit | `VeilPipeline` | [references/python-api.md](references/python-api.md) |
| Calling an LLM from code so it only ever sees tokens, with streaming and history | `VeilProxy` | [references/llm-proxy.md](references/llm-proxy.md) |
| Other languages, several tools or agents sharing sessions | `veil serve` HTTP API | [references/http-api.md](references/http-api.md) |
| Validating model input or output in Guardrails AI | `VeilPIIValidator`, `VeilAnonymizer` | [references/python-api.md](references/python-api.md) |
| A person chatting with a model behind Veil | `veil app` desktop UI | [references/cli.md](references/cli.md) |

## 6. Handing work to another model or service

Before sending text to a sub-agent, a hosted API, a search query, a ticket or
any other external system, send the anonymized copy. Tell the recipient to
keep bracketed tokens unchanged. Reconstruct its reply locally with the same
session.

## Limits

- English models by default. Structured identifiers (e-mail, card, IBAN, IP,
  phone) are language-independent; names in other languages need a matching
  spaCy model.
- Plain UTF-8 text only. Convert PDFs, spreadsheets and office documents to
  text locally first, and remember that file names and metadata are not
  anonymized.
- No detector finds everything. Veil reduces what a model sees; it does not
  certify a document as free of personal data.
- Quasi-identifiers (a job title plus a small town) can identify a person
  even with every name replaced.
- `veil serve` has no authentication and no TLS. Keep it on `127.0.0.1` or
  behind a gateway.
