# Installing the skill

Two things are needed: the skill folder where the agent looks for skills, and
the Veil package in the environment where the agent runs commands.

## 1. Install Veil

```bash
pip install "git+https://github.com/SpinettaInc/veil.git"
python -m spacy download en_core_web_sm
```

Optional pieces:

| Install | Enables |
|---|---|
| `python -m spacy download en_core_web_lg` | More accurate name detection (used automatically when present) |
| `pip install faker` | `--mode faker` |
| `pip install presidio-analyzer` | `--presidio` and full hybrid detection |
| `pip install gensim` | Embedding-based `--mode semantic` |
| `pip install wordfreq` | Corpus-based rarity scoring in short texts |

Requires Python 3.10 or newer.

## 2. Put the skill where the agent finds it

Copy or symlink `skills/veil/`. A symlink keeps it up to date with the
checkout.

```bash
ln -s "$PWD/skills/veil" ~/.claude/skills/veil      # Claude Code, all projects
ln -s "$PWD/skills/veil" .claude/skills/veil        # Claude Code, one project
ln -s "$PWD/skills/veil" ~/.codex/skills/veil       # Codex CLI
ln -s "$PWD/skills/veil" .agents/skills/veil        # runtimes that read .agents/skills
```

Skill directories differ between runtimes and versions. If yours is not
listed, check its documentation for where it loads skills from.

### Agents without skill support

Point the agent at the file from whatever instructions it does read
(`AGENTS.md`, a system prompt, a rules file):

```markdown
When a task involves personal or confidential data, read and follow
/path/to/veil/skills/veil/SKILL.md before opening any file.
```

The skill only assumes the agent can read a Markdown file and run a shell
command.

## 3. Check it

```bash
python skills/veil/scripts/veil_tool.py check
```

```json
{
  "desktop_app": false,
  "faker": true,
  "guardrails": false,
  "hybrid_mode": "ready",
  "presidio": true,
  "semantic_embeddings": false,
  "spacy_models": ["en_core_web_sm"],
  "standard_mode": "ready",
  "veil_path": "/path/to/site-packages/veil",
  "veil_version": "0.1.0",
  "wordfreq": false
}
```

`standard_mode` must be `ready`. `hybrid_mode` matters only if you use
`--hybrid` or `--presidio`. When a mode is not ready, its value names what is
missing.

`veil_path` shows which copy of Veil is being used. If you work inside a
checkout of this repository and it points elsewhere, prefix commands with
`PYTHONPATH=src`.

## Updating

With a symlink, `git pull` in the checkout updates the skill. With a copy,
copy the folder again. Upgrade the package with the same `pip install`
command.
