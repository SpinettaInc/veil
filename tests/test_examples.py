"""Every script in examples/ must run to completion."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from veil.detection.ner import SPACY_AVAILABLE

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))


@pytest.mark.skipif(not SPACY_AVAILABLE, reason="examples need spaCy")
@pytest.mark.parametrize("script", EXAMPLES, ids=[p.name for p in EXAMPLES])
def test_example_runs(script: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, env=env, timeout=300
    )
    assert proc.returncode == 0, f"{script.name} failed:\n{proc.stdout}\n{proc.stderr}"
