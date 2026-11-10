# Troubleshooting and limits

## The agent does not use the skill

- Confirm the folder is where the runtime loads skills from and that
  `SKILL.md` is directly inside it (`.../skills/veil/SKILL.md`).
- Start a new session; most runtimes list skills at startup.
- Skills are picked by their description. Asking to "anonymize", "redact" or
  "use Veil" matches it. For a task where the sensitivity is not obvious from
  the request, say so, or add a standing instruction (see
  [Installation](installation.md#agents-without-skill-support)).

## `error: the 'veil' package is not importable`

The Python that runs the script cannot find Veil. Install it into that
environment, or inside a checkout prefix the command with `PYTHONPATH=src`.
`veil_tool.py check` shows which copy is in use (`veil_path`).

## Exit code 2: detection unavailable

A requested detector could not load, and nothing was written. This is
deliberate: Veil fails closed rather than passing text through unprotected.

| Message mentions | Fix |
|---|---|
| a spaCy model | `python -m spacy download en_core_web_sm` |
| Presidio | `pip install presidio-analyzer`, or drop `--presidio` |

`--allow-degraded` overrides this. The output may then still contain
sensitive data, and the summary reports `"degraded": true`. Use it only when
the user accepts that.

## Something sensitive was not replaced

Detection is statistical. Find out why with `scan`:

```bash
python veil_tool.py scan input.txt --profile balanced
```

| What `scan` shows | Do |
|---|---|
| The value is listed with `would_anonymize: false` | It scored below the threshold. Use `--profile paranoid` or `--no-weighting`. |
| The value is not listed at all | It was not detected. Try `--hybrid` or `--presidio`, install `en_core_web_lg`, or add a custom pattern. |
| It is a house identifier (employee ID, case number) | Add it as a [custom pattern](choosing-options.md#profile). |

To locate a value without printing it, compare offsets from `scan` with the
position you expect. `--reveal` prints the matched text and is meant for a
person, not the agent.

## Too much was replaced

- Use `--profile minimal`, or `balanced` if you were on `paranoid`.
- Restrict types: `--types PERSON,EMAIL,PHONE`.
- Raise `--min-confidence`.

## Reconstruction left tokens in place

`replacements_made` is lower than expected, or tokens remain in the output.

- **Wrong session.** The session file must be the one used to anonymize.
  `veil_tool.py session FILE` lists the tokens it knows.
- **Changed number.** `[PERSON_3]` when the session has only two people.
  The model invented or renumbered a token; it cannot be restored.
- **Token reworded.** "person 1" in prose without the type name in capitals,
  or "the patient". Bracket style, case and `_`/`-`/space separators are
  tolerated; paraphrases are not.
- **Fake value rewritten.** In `faker` or `semantic` mode the model
  abbreviated or altered a fake value. Use token mode for text that goes
  through a model.
- **`--session-dir` was used.** Each document has its own session; use the
  matching `<name>.session.json`.

## `refusing to overwrite the input file`

`--out` points at one of the inputs. Write the anonymized copy somewhere
else; the original is the only copy of the real data.

## `several inputs need --out-dir`

`--out` takes one input. Use `--out-dir` for more, and note that two inputs
with the same file name must be anonymized in separate runs.

## The first run is slow

Loading the spaCy model takes a few seconds per invocation. For many files,
pass them all to one `anonymize` call, which also runs detection in batch
mode. For many calls over time, run `veil serve` and use the
[HTTP API](../guide/api-server.md), which loads the model once.

## Limits

- **Languages.** The default models are English. Structured identifiers
  (e-mail, card, IBAN, IP, phone) are detected in any language; names in
  other languages need a matching spaCy model.
- **File types.** UTF-8 text only. Convert PDFs, spreadsheets and office
  documents to text locally first. File names and metadata are not
  anonymized.
- **Coverage.** No detector finds everything. Veil reduces what a model sees;
  it does not certify a document as free of personal data.
- **Quasi-identifiers.** A job title plus a small town can identify a person
  even when every name is replaced.
- **Instructions, not enforcement.** The skill cannot stop an agent that
  ignores it. Where that matters, restrict the agent's file access to the
  anonymized copies.
- **The session file is the secret.** Anyone who can read it can undo the
  anonymization. Keep it local, out of version control, and delete it when
  it is no longer needed.
