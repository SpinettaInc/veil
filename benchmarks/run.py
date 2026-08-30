"""Precision/recall/latency benchmark for the Veil pipeline.

Usage: python benchmarks/run.py [--profile balanced] [--mode standard|hybrid] [-v]
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import importlib  # noqa: E402

from veil import VeilPipeline  # noqa: E402
from veil.weighting.config import DetectionProfile  # noqa: E402

LOC_GROUP = {"LOC", "GPE", "FAC"}


def norm(t: str) -> str:
    return "LOC" if t in LOC_GROUP else t


def gold_spans(text: str, gold: list[tuple[str, str]]) -> list[tuple[int, int, str]]:
    spans = []
    for sub, typ in gold:
        start = 0
        while True:
            i = text.find(sub, start)
            if i < 0:
                break
            spans.append((i, i + len(sub), typ))
            start = i + 1
    return spans


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="balanced")
    ap.add_argument("--mode", default="standard")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--model", default=None, help="spaCy model name (default: best installed)")
    ap.add_argument("--corpus", default="gold", help="gold | gold_hard | all")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument(
        "--min-f1", type=float, default=None, help="exit 1 if overall F1 is below this"
    )
    args = ap.parse_args()

    names = ["gold", "gold_hard"] if args.corpus == "all" else [args.corpus]
    CASES = [c for n in names for c in importlib.import_module(n).CASES]

    t0 = time.perf_counter()
    pipe = VeilPipeline(
        profile=DetectionProfile(args.profile), detection_mode=args.mode, spacy_model=args.model
    )
    init_s = time.perf_counter() - t0

    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    type_err = 0
    fps: list[str] = []
    fns: list[str] = []
    latencies: list[float] = []
    recon_fail = 0

    for text, gold in CASES:
        gspans = gold_spans(text, gold)
        pipe.clear_mappings()
        best = None
        for _ in range(args.repeat):
            pipe.clear_mappings()
            t1 = time.perf_counter()
            res = pipe.anonymize(text)
            dt = time.perf_counter() - t1
            best = dt if best is None else min(best, dt)
        latencies.append(best)

        # round-trip check
        back = pipe.reconstruct(res.anonymized_text).reconstructed_text
        if back != text:
            recon_fail += 1
            if args.verbose:
                print(f"  RECON FAIL: {text!r} -> {back!r}")

        matched_gold: set[int] = set()
        for e in res.entities:
            hit = None
            for gi, (gs, ge, gt) in enumerate(gspans):
                if overlaps((e.start, e.end), (gs, ge)):
                    hit = gi
                    break
            if hit is None:
                fp[norm(e.entity_type.value)] += 1
                fps.append(f"{e.text!r} as {e.entity_type.value} in {text[:60]!r}")
            else:
                matched_gold.add(hit)
                gt = gspans[hit][2]
                if norm(e.entity_type.value) == norm(gt):
                    tp[norm(gt)] += 1
                else:
                    type_err += 1
                    tp[norm(gt)] += 1  # span found, type off: count as hit but note it
                    if args.verbose:
                        print(f"  TYPE: {e.text!r} got {e.entity_type.value}, want {gt}")
        for gi, (gs, ge, gt) in enumerate(gspans):
            if gi not in matched_gold:
                fn[norm(gt)] += 1
                fns.append(f"{text[gs:ge]!r} ({gt}) in {text[:60]!r}")

    types = sorted(set(tp) | set(fp) | set(fn))
    print(
        f"\ncorpus={args.corpus} ({len(CASES)} cases) profile={args.profile} mode={args.mode} model={pipe.detector.ner_detector.model_name if pipe.detector.ner_detector else '-'}"
    )
    print(
        f"init {init_s:.2f}s | per-call median {statistics.median(latencies) * 1000:.1f}ms "
        f"max {max(latencies) * 1000:.1f}ms total {sum(latencies) * 1000:.0f}ms"
    )
    print(f"{'type':<15}{'tp':>5}{'fp':>5}{'fn':>5}{'P':>8}{'R':>8}{'F1':>8}")
    TP = FP = FN = 0
    for t in types:
        p = tp[t] / (tp[t] + fp[t]) if tp[t] + fp[t] else 0.0
        r = tp[t] / (tp[t] + fn[t]) if tp[t] + fn[t] else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        print(f"{t:<15}{tp[t]:>5}{fp[t]:>5}{fn[t]:>5}{p:>8.2f}{r:>8.2f}{f:>8.2f}")
        TP += tp[t]
        FP += fp[t]
        FN += fn[t]
    P = TP / (TP + FP) if TP + FP else 0.0
    R = TP / (TP + FN) if TP + FN else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    print(
        f"{'ALL':<15}{TP:>5}{FP:>5}{FN:>5}{P:>8.2f}{R:>8.2f}{F:>8.2f}   type-mismatch={type_err} recon-fail={recon_fail}"
    )
    if args.verbose or True:
        print("\nFalse positives:")
        for s in fps:
            print("  -", s)
        print("False negatives:")
        for s in fns:
            print("  -", s)
    if args.min_f1 is not None and F < args.min_f1:
        print(f"\nFAIL: F1 {F:.3f} < required {args.min_f1}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
