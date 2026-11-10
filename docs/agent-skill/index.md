# Agent skill

`skills/veil/` is an [Agent Skill](https://agentskills.io): a folder of
instructions that teaches an AI coding agent to use Veil. It is plain Markdown
plus one Python script, so it works with any model and any runtime that can
read files and run a shell command.

## Why an agent needs it

An agent that opens a document has already sent it to its model. Anonymizing
afterwards is too late. The skill teaches the agent a different order:

1. Run Veil on the file **by path**, without opening it.
2. Read only the anonymized copy.
3. Do the work, keeping tokens such as `[PERSON_1]` intact.
4. Restore the originals into an output file, and hand over its path without
   reading it back.

Detection runs on the machine the agent runs on. The mapping from token to
original stays in a session file on disk.

## What is in the folder

| File | Purpose |
|---|---|
| `SKILL.md` | The workflow, the option tables and the rules for handling tokens. This is what the agent loads first. |
| `scripts/veil_tool.py` | File-based helper that prints counts and scores, never the original values |
| `references/cli.md` | Every `veil` command, and which ones print originals |
| `references/profiles.md` | Scoring, entity types, custom YAML profiles and patterns |
| `references/python-api.md` | `VeilPipeline`, sessions, batches, audit, Guardrails |
| `references/llm-proxy.md` | `VeilProxy`, providers, streaming |
| `references/http-api.md` | `veil serve` |

The agent reads `SKILL.md` when a task matches its description, and opens a
reference page only when the task needs that interface.

## In this section

| Page | Read it to |
|---|---|
| [Installation](installation.md) | Put the skill where your agent finds it and install Veil |
| [Workflow](workflow.md) | See the anonymize → work → reconstruct cycle step by step |
| [Helper script](helper-script.md) | Look up every `veil_tool.py` command, option and output |
| [Choosing options](choosing-options.md) | Pick a profile, detection mode and replacement mode |
| [Troubleshooting](troubleshooting.md) | Fix common failures and understand the limits |

## What it does not do

The skill reduces what a model sees. It is a set of instructions, so it
cannot stop an agent that ignores it from opening the original file, and no
detector finds every sensitive value. For a hard guarantee, keep the
originals where the agent cannot read them and give it only anonymized
copies.
