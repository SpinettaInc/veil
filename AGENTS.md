# Repository Guidelines

## Project Structure & Module Organization

Veil is a Python privacy proxy that anonymizes sensitive text before LLM requests and reconstructs responses. Source lives in `src/veil/`: `core/` orchestrates pipelines and mappings; `detection/`, `weighting/`, and `replacement/` implement processing; `llm/` contains provider integrations. Entry points are `cli.py`, `server.py`, and `app/desktop.py`. YAML profiles live in `src/veil/config/profiles/`. Tests and fixtures are in `tests/`; labeled corpora and fuzz checks are in `benchmarks/`. See `examples/` for runnable usage and `docs/` for MkDocs documentation.

## Build, Test, and Development Commands

Use Python 3.10+; CI tests Python 3.10 and 3.12. Run commands from the repository root.

- `pip install -e ".[dev,faker,rarity]" presidio-analyzer`: install the development dependencies used in CI.
- `python -m spacy download en_core_web_sm`: install the NER model used in CI.
- `pip wheel . --no-deps -w dist`: build the package wheel with Hatchling.
- `veil anonymize "Email test@example.com"`: exercise the CLI locally.
- `veil serve --port 8787`: start the local HTTP API.
- `pytest -m "not desktop"`: run the CI test selection with coverage.
- `ruff check src/ tests/ benchmarks/`: run CI lint checks.
- `ruff format src/ tests/` and `mypy src/veil/`: format Python and check strict typing.

## Coding Style & Naming Conventions

Use four-space indentation, a 100-character line limit, and Python 3.10-compatible syntax. Follow `snake_case` for modules/functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Add type annotations and public API docstrings. Ruff enforces import ordering and naming; configuration lives in `pyproject.toml`.

## Testing Guidelines

Use pytest files named `test_*.py` and functions named `test_*`; keep reusable sample data in `tests/fixtures/`. Run focused checks with `pytest tests/test_pipeline.py`. Coverage reports missing lines; no minimum percentage is configured. Install `.[desktop]` before running desktop tests with `pytest`.

For detection or scoring changes, add regression corpus cases and run `python benchmarks/run.py --corpus all --min-f1 0.95`, then repeat with `--mode hybrid`. Both modes must meet the CI threshold. Run `python benchmarks/fuzz.py --trials 100` for reconstruction checks.

## Commit & Pull Request Guidelines

History uses descriptive subjects, including `feature: ...` and `Update README.md`; no strict commit format is established. Keep commits focused. PRs should describe behavior changes, link relevant issues, report validation, and update affected documentation. Include screenshots for desktop UI changes.

## Privacy & Configuration

Preserve fail-closed detection and session-isolated mappings. Keep audit logs limited to counts and timings; never log original text or tokens. Use synthetic fixtures and keep credentials out of commits.
