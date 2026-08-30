"""Randomised round-trip, persistence and idempotence properties (see benchmarks/fuzz.py)."""

import subprocess
import sys
from pathlib import Path

import pytest

from veil.detection.ner import SPACY_AVAILABLE

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not SPACY_AVAILABLE, reason="needs spaCy")
def test_round_trip_fuzz() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "benchmarks" / "fuzz.py"), "--trials", "40", "--seed", "11"],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
        timeout=600,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
