#!/usr/bin/env python3
"""File-based Veil helper for AI agents.

An agent that reads a document has already sent it to its model. This tool
lets an agent work on sensitive files *without* reading them: Veil runs
locally, the anonymized copy is what the agent reads, and the mapping needed
to restore the originals stays in a session file on disk.

Nothing this tool prints contains an original value unless ``--reveal`` is
given: summaries are counts, types, offsets and scores only.

    veil_tool.py check
    veil_tool.py anonymize notes.txt --out notes.anon.txt --session s.json
    veil_tool.py scan notes.txt --profile paranoid
    veil_tool.py reconstruct reply.txt --out reply.final.txt --session s.json
    veil_tool.py session s.json

Exit codes: 0 ok, 1 bad input or configuration, 2 detection unavailable
(fail-closed: a detector could not load, so nothing was written).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

EXIT_ERROR = 1
EXIT_UNAVAILABLE = 2


class ToolError(Exception):
    """A problem to report to the caller (never carries document text)."""


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"cannot read {path}: {exc.strerror}") from None
    except UnicodeDecodeError:
        raise ToolError(f"{path} is not UTF-8 text") from None


def _write(path: str, text: str) -> None:
    if path == "-":
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _write_private(path: Path, text: str) -> None:
    """Session files hold the original values: owner-only, like an SSH key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def _load_session(path: Path) -> Any:
    from veil import MappingStore

    if not path.exists():
        return MappingStore()
    try:
        return MappingStore.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ToolError(f"{path} is not a Veil session file") from None


def _save_session(path: Path, store: Any) -> None:
    _write_private(path, json.dumps(store.to_dict(), indent=2))


def _refuse_overwrite(inputs: list[str], outputs: list[str]) -> None:
    sources = {Path(p).resolve() for p in inputs if p != "-"}
    for out in outputs:
        if out != "-" and Path(out).resolve() in sources:
            raise ToolError(f"refusing to overwrite the input file {out}")


def _build_pipeline(args: argparse.Namespace) -> Any:
    from veil import EntityType, VeilPipeline
    from veil.audit import AuditLogger
    from veil.weighting.config import DetectionProfile, load_profile

    try:
        profile = DetectionProfile(args.profile.lower())
        weight_config = None
    except ValueError:
        if not Path(args.profile).is_file():
            valid = ", ".join(p.value for p in DetectionProfile)
            raise ToolError(
                f"unknown profile {args.profile!r}: use {valid} or a path to a YAML profile"
            ) from None
        profile = DetectionProfile.BALANCED
        weight_config = load_profile(args.profile)

    entity_types = None
    if getattr(args, "types", None):
        try:
            entity_types = [EntityType(t.strip().upper()) for t in args.types.split(",")]
        except ValueError as exc:
            raise ToolError(f"unknown entity type: {exc}") from None

    audit = AuditLogger(args.audit) if getattr(args, "audit", None) else None
    pipeline = VeilPipeline(
        use_ner=not args.no_ner,
        use_patterns=not args.no_patterns,
        use_presidio=args.presidio,
        spacy_model=args.spacy_model,
        min_confidence=args.min_confidence,
        bracket_style=getattr(args, "bracket_style", "square"),
        profile=profile,
        weight_config=weight_config,
        use_weighting=not args.no_weighting,
        replacement_mode=getattr(args, "mode", "token"),
        faker_locale=getattr(args, "locale", "en_US"),
        faker_seed=getattr(args, "seed", None),
        detection_mode="hybrid" if (args.hybrid or args.presidio) else "standard",
        strict=not args.allow_degraded,
        audit=audit,
    )
    return pipeline, entity_types, audit


def _summary(result: Any) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for entity in result.entities:
        label = entity.metadata.get("label") if entity.metadata else None
        counts[label or entity.entity_type.value] += 1
    return {
        "entities": len(result.entities),
        "by_type": dict(sorted(counts.items())),
        "degraded": result.degraded,
        "chars": len(result.original_text),
    }


# -- commands -----------------------------------------------------------------


def cmd_check(args: argparse.Namespace) -> int:
    import veil

    def has(module: str) -> bool:
        return importlib.util.find_spec(module) is not None

    models = [
        name
        for name in ("en_core_web_trf", "en_core_web_lg", "en_core_web_md", "en_core_web_sm")
        if has(name)
    ]
    report: dict[str, Any] = {
        "veil_version": veil.__version__,
        "veil_path": str(Path(veil.__file__).parent),
        "spacy_models": models,
        "presidio": has("presidio_analyzer"),
        "faker": has("faker"),
        "semantic_embeddings": has("gensim"),
        "wordfreq": has("wordfreq"),
        "guardrails": has("guardrails"),
        "desktop_app": has("gradio"),
    }
    from veil.core.detector import DetectionUnavailableError

    for name, kwargs in (
        ("standard", {}),
        ("hybrid", {"detection_mode": "hybrid", "use_presidio": True}),
    ):
        try:
            veil.VeilPipeline(**kwargs)
            report[f"{name}_mode"] = "ready"
        except (DetectionUnavailableError, ImportError) as exc:
            report[f"{name}_mode"] = f"unavailable: {exc}"
    _emit(report)
    return 0 if report["standard_mode"] == "ready" else EXIT_UNAVAILABLE


def cmd_anonymize(args: argparse.Namespace) -> int:
    inputs: list[str] = args.inputs
    if len(inputs) > 1 and not args.out_dir:
        raise ToolError("several inputs need --out-dir")
    if len(inputs) == 1 and not (args.out or args.out_dir):
        raise ToolError("give --out FILE (or --out - to print the anonymized text)")
    if bool(args.session) == bool(args.session_dir):
        raise ToolError("give exactly one of --session FILE or --session-dir DIR")
    if "-" in inputs and (len(inputs) > 1 or args.out_dir):
        raise ToolError("stdin input takes a single --out")

    if args.out_dir:
        outputs = [str(Path(args.out_dir) / Path(p).name) for p in inputs]
        if len(set(outputs)) != len(outputs):
            raise ToolError("two inputs share a file name; anonymize them separately")
    else:
        outputs = [args.out]
    _refuse_overwrite(inputs, outputs)

    pipeline, entity_types, audit = _build_pipeline(args)
    texts = [_read(p) for p in inputs]

    separate = bool(args.session_dir)
    if not separate:
        pipeline.mapping_store = _load_session(Path(args.session))
    results = pipeline.anonymize_batch(texts, entity_types, separate_sessions=separate)

    files = []
    for source, target, result in zip(inputs, outputs, results):
        _write(target, result.anonymized_text)
        entry = {"input": source, "output": target, **_summary(result)}
        if separate:
            session_path = Path(args.session_dir) / f"{Path(source).name}.session.json"
            _save_session(session_path, result.mapping_store)
            entry["session"] = str(session_path)
        files.append(entry)
    if not separate:
        _save_session(Path(args.session), pipeline.mapping_store)
    if audit:
        audit.close()

    report: dict[str, Any] = {"files": files, "degraded": any(f["degraded"] for f in files)}
    if not separate:
        report["session"] = args.session
        report["session_mappings"] = pipeline.mapping_store.get_stats()["by_type"]
    stream = sys.stderr if "-" in outputs else sys.stdout
    print(json.dumps(report, indent=2, sort_keys=True), file=stream)
    return 0


def cmd_reconstruct(args: argparse.Namespace) -> int:
    session = Path(args.session)
    if not session.exists():
        raise ToolError(f"session file {session} does not exist")
    _refuse_overwrite([args.input], [args.out])
    restored, count = _load_session(session).restore(_read(args.input))
    _write(args.out, restored)
    if args.out != "-":
        _emit({"input": args.input, "output": args.out, "replacements_made": count})
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    pipeline, _, _ = _build_pipeline(args)
    text = _read(args.input)
    rows = []
    for score in pipeline.score_entities(text):
        entity = score.entity
        row: dict[str, Any] = {
            "type": entity.entity_type.value,
            "start": entity.start,
            "end": entity.end,
            "source": entity.source,
            "confidence": round(entity.confidence, 2),
            "score": round(score.total_score, 3),
            "would_anonymize": score.above_threshold,
            "factors": score.contributing_factors,
        }
        if args.reveal:
            row["text"] = entity.text
        rows.append(row)
    stats = pipeline.get_stats()
    _emit(
        {
            "input": args.input,
            "threshold": stats["scorer"]["threshold"],
            "detection": {k: stats["detector"][k] for k in ("mode", "ner_model", "pattern_count")},
            "degraded": pipeline.detector.degraded,
            "would_anonymize": sum(r["would_anonymize"] for r in rows),
            "kept": sum(not r["would_anonymize"] for r in rows),
            "entities": rows,
        }
    )
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    path = Path(args.session)
    if not path.exists():
        raise ToolError(f"session file {path} does not exist")
    if args.delete:
        path.unlink()
        _emit({"session": str(path), "deleted": True})
        return 0
    store = _load_session(path)
    report: dict[str, Any] = {"session": str(path), **store.get_stats()}
    if args.reveal:
        report["mappings"] = {entry.replacement: entry.original for entry in store}
    else:
        report["replacements"] = sorted(entry.replacement for entry in store)
    _emit(report)
    return 0


# -- argument parsing ---------------------------------------------------------


def _detection_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("detection")
    group.add_argument(
        "--profile", default="balanced", help="paranoid, balanced, minimal, or a YAML profile path"
    )
    group.add_argument(
        "--hybrid", action="store_true", help="merge spaCy + patterns (+ Presidio) with agreement"
    )
    group.add_argument("--presidio", action="store_true", help="add Presidio (implies --hybrid)")
    group.add_argument("--no-ner", action="store_true", help="patterns only")
    group.add_argument("--no-patterns", action="store_true", help="NER only")
    group.add_argument(
        "--no-weighting", action="store_true", help="anonymize every detection, skip scoring"
    )
    group.add_argument("--spacy-model", default=None, help="default: best installed")
    group.add_argument("--min-confidence", type=float, default=0.0)
    group.add_argument(
        "--allow-degraded",
        action="store_true",
        help="continue when a detector cannot load (output may still contain PII)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="veil_tool.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="report what is installed and usable").set_defaults(func=cmd_check)

    anon = sub.add_parser("anonymize", help="anonymize files; prints counts only")
    anon.add_argument("inputs", nargs="+", help="input files, or - for stdin")
    anon.add_argument("--out", help="output file for a single input (- prints it)")
    anon.add_argument("--out-dir", help="output directory (same file names)")
    anon.add_argument("--session", help="mapping file shared by all inputs; created or extended")
    anon.add_argument("--session-dir", help="one unlinkable session per input, stored here")
    anon.add_argument("--mode", default="token", choices=["token", "faker", "semantic"])
    anon.add_argument("--seed", type=int, default=None, help="faker seed")
    anon.add_argument("--locale", default="en_US", help="faker locale")
    anon.add_argument("--bracket-style", default="square", choices=["square", "angle", "curly"])
    anon.add_argument("--types", help="only these entity types, e.g. PERSON,EMAIL,PHONE")
    anon.add_argument("--audit", help="append a counts-only JSONL audit log here")
    _detection_options(anon)
    anon.set_defaults(func=cmd_anonymize)

    recon = sub.add_parser("reconstruct", help="restore originals using a session file")
    recon.add_argument("input", help="text containing tokens/fake values, or - for stdin")
    recon.add_argument("--out", required=True, help="output file (- prints originals)")
    recon.add_argument("--session", required=True)
    recon.set_defaults(func=cmd_reconstruct)

    scan = sub.add_parser("scan", help="what would be detected and why, without the values")
    scan.add_argument("input", help="input file, or - for stdin")
    scan.add_argument("--reveal", action="store_true", help="include the matched text")
    _detection_options(scan)
    scan.set_defaults(func=cmd_scan)

    session = sub.add_parser("session", help="inspect or delete a session file")
    session.add_argument("session")
    session.add_argument("--reveal", action="store_true", help="include the original values")
    session.add_argument("--delete", action="store_true", help="delete the session file")
    session.set_defaults(func=cmd_session)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from veil.core.detector import DetectionUnavailableError
    except ImportError:
        print(
            "error: the 'veil' package is not importable. Install it "
            '(pip install "git+https://github.com/SpinettaInc/veil.git") '
            "or set PYTHONPATH to a checkout's src/ directory.",
            file=sys.stderr,
        )
        return EXIT_ERROR
    try:
        return int(args.func(args))
    except DetectionUnavailableError as exc:
        print(f"error: detection unavailable, nothing written: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except (ImportError, ValueError) as exc:
        # Configuration problems (missing extra, bad mode, malformed profile).
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
