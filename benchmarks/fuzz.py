"""Randomised round-trip / persistence / idempotence check.

Builds documents from the labeled corpora with token-like noise, then asserts:
  - reconstruct(anonymize(doc)) == doc   (case-insensitively: reconstruction
    restores the canonical spelling of a name)
  - the same holds after a to_dict/from_dict session round trip
  - a second anonymize() pass leaves every existing token intact (statistical
    NER may still find a *new* entity in the re-shaped text; that is noise,
    not corruption, and is not counted)

Usage: python benchmarks/fuzz.py [--trials 150] [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gold import CASES  # noqa: E402
from gold_hard import CASES as HARD_CASES  # noqa: E402

from veil import VeilPipeline  # noqa: E402
from veil.core.mapper import MappingStore, token_spans  # noqa: E402

NOISE = ["", " [PERSON_1] ", " «Ünïcode» ", " (see [EMAIL 2]) ", " PERSON_3 ", " {ORG_1} "]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--modes", default="token,faker")
    args = ap.parse_args()
    random.seed(args.seed)
    texts = [t for t, _ in CASES + HARD_CASES]
    failures = 0
    for mode in args.modes.split(","):
        pipe = VeilPipeline(replacement_mode=mode, faker_seed=3)
        for trial in range(args.trials):
            pipe.clear_mappings()
            noise = random.choice(NOISE)
            doc = noise + " ".join(random.sample(texts, random.randint(1, 6))) + noise
            result = pipe.anonymize(doc)
            back = pipe.reconstruct(result.anonymized_text).reconstructed_text
            snapshot = MappingStore.from_dict(json.loads(json.dumps(pipe.mapping_store.to_dict())))
            other = VeilPipeline(replacement_mode=mode)
            other.mapping_store = snapshot
            back2 = other.reconstruct(result.anonymized_text).reconstructed_text
            again = pipe.anonymize(result.anonymized_text).anonymized_text
            problems = []
            if back.casefold() != doc.casefold():
                problems.append("round-trip")
            if back2.casefold() != doc.casefold():
                problems.append("persisted round-trip")
            # Fake values look real, so a second pass replaces them again by design;
            # token preservation is only a property of token mode.
            if mode == "token":
                before = [result.anonymized_text[s:e] for s, e in token_spans(result.anonymized_text)]
                after = [again[s:e] for s, e in token_spans(again)]
                if [t for t in before if t in after] != before:
                    problems.append("idempotence")
            if problems:
                failures += 1
                if failures <= 10:
                    print(f"[{mode}] trial {trial}: {', '.join(problems)}")
                    if "idempotence" in problems:
                        print(f"    tokens before: {before}\n    tokens after:  {after}")
                    else:
                        for a, b in zip(doc.split(), back.split()):
                            if a.casefold() != b.casefold():
                                print(f"    {a!r} -> {b!r}")
                                break
    total = args.trials * len(args.modes.split(","))
    print(f"fuzz: {total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
