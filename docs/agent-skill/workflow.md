# Workflow

This is the cycle the skill teaches. The examples use `veil_tool.py` from
`skills/veil/scripts/`; the data in them is made up.

## One file

Say `notes.txt` contains:

```
Patient Mary Johnson (MRN-12345678), DOB March 15, 1985.
Email mary.johnson@example.com, phone 555-123-4567.
```

**1. Anonymize.** The agent runs Veil on the path. It does not open the file.

```bash
python veil_tool.py anonymize notes.txt \
    --out work/notes.anon.txt --session work/session.json
```

The command prints a summary with counts only:

```json
{
  "degraded": false,
  "files": [
    {
      "by_type": {"DATE": 1, "EMAIL": 1, "MEDICAL_RECORD": 1, "PERSON": 1, "PHONE": 1},
      "chars": 109,
      "degraded": false,
      "entities": 5,
      "input": "notes.txt",
      "output": "work/notes.anon.txt"
    }
  ],
  "session": "work/session.json",
  "session_mappings": {"DATE": 1, "EMAIL": 1, "MEDICAL_RECORD": 1, "PERSON": 1, "PHONE": 1}
}
```

**2. Work on the anonymized copy.** `work/notes.anon.txt` now reads:

```
Patient [PERSON_1] ([MEDICAL_RECORD_1]), DOB [DATE_1].
Email [EMAIL_1], phone [PHONE_1].
```

The agent reads this file and writes its result to another file, for example
`work/summary.anon.md`:

```
[PERSON_1] should be contacted at [EMAIL_1] to confirm the appointment.
```

**3. Reconstruct.**

```bash
python veil_tool.py reconstruct work/summary.anon.md \
    --out summary.md --session work/session.json
```

```json
{"input": "work/summary.anon.md", "output": "summary.md", "replacements_made": 2}
```

`summary.md` holds the real values. The agent gives the user the path and
does not read the file back.

**4. Clean up** once nothing more needs reconstructing:

```bash
python veil_tool.py session work/session.json --delete
```

## Several files

Files that belong together share a session, so one person has one token
across all of them:

```bash
python veil_tool.py anonymize a.txt b.txt c.txt \
    --out-dir work/anon --session work/session.json
```

Outputs keep their file names inside `--out-dir`. Running the command again
later with the same `--session` extends the mapping: known values keep their
tokens and new ones get the next free number.

For documents that must not be linkable to one another, give each its own
session:

```bash
python veil_tool.py anonymize a.txt b.txt \
    --out-dir work/anon --session-dir work/sessions
```

Token numbering restarts in every file, and each session is saved as
`work/sessions/<file name>.session.json`.

## Text instead of files

```bash
some-command | python veil_tool.py anonymize - --out - --session work/session.json
```

The anonymized text goes to stdout and the summary to stderr.

## Rules for tokens

The agent must:

- Keep tokens verbatim: `[PERSON_1]`, not "person 1" or "the first patient".
- Treat a token as one real value everywhere in the session; `[PERSON_1]` and
  `[PERSON_2]` are different people.
- Never invent a token or guess what one stands for.

Reconstruction is tolerant of how models rewrite tokens. All of these restore
correctly:

```
[PERSON_1]   PERSON_1   <PERSON_1>   [person 1]   [PERSON-1]
```

A changed number does not: `[PERSON_2]` is a different person, and a token
with no mapping is left as it is.

Tokens that are already in an input file are left alone, and their numbers
are not reused for new values.

## The session file

The session file contains every original value. The helper writes it
readable by the owner only (`0600`). It must not be read by the agent,
printed, committed or sent anywhere. Add the work directory to `.gitignore`.

## Handing work to another model or service

Before text goes to a sub-agent, a hosted API, a web search or a ticket
system, the agent sends the anonymized copy and asks the recipient to keep
bracketed tokens unchanged. The reply is reconstructed locally with the same
session.

## Sensitive text pasted into the chat

If the user pastes raw data into the conversation, the model has already seen
it. The skill tells the agent to say so, to anonymize the text before any
further processing or hand-off, and not to repeat the raw values.
