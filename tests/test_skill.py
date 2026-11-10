"""The agent skill in skills/veil must keep working and keep its promises.

Its helper prints summaries an AI agent will read, so the central check is
that no original value appears in that output.
"""

import importlib.util
import json
import re
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

from veil.detection.ner import SPACY_AVAILABLE

SKILL = Path(__file__).resolve().parent.parent / "skills" / "veil"
needs_spacy = pytest.mark.skipif(not SPACY_AVAILABLE, reason="the skill helper needs spaCy")

NAME = "Mary Johnson"
EMAIL = "mary.johnson@example.com"
DOC = f"Patient {NAME} can be reached at {EMAIL} or 555-123-4567."


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("veil_tool", SKILL / "scripts" / "veil_tool.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSkillFiles:
    def test_frontmatter(self) -> None:
        text = (SKILL / "SKILL.md").read_text()
        match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
        assert match, "SKILL.md must start with YAML frontmatter"
        fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
        assert fields["name"] == SKILL.name
        assert 0 < len(fields["description"]) <= 1024

    def test_links_resolve(self) -> None:
        for page in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
            for target in re.findall(r"\]\(([^)#]+)\)", page.read_text()):
                if "://" not in target:
                    assert (page.parent / target).exists(), f"{page.name}: broken link {target}"

    def test_mentioned_scripts_exist(self) -> None:
        for script in set(re.findall(r"scripts/\w+\.py", (SKILL / "SKILL.md").read_text())):
            assert (SKILL / script).is_file()


@needs_spacy
class TestVeilTool:
    def test_round_trip_never_prints_originals(
        self, tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = tmp_path / "in.txt"
        source.write_text(DOC)
        anon = tmp_path / "work" / "in.anon.txt"
        session = tmp_path / "work" / "session.json"

        args = ["anonymize", str(source), "--out", str(anon), "--session", str(session)]
        assert tool.main(args) == 0
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["files"][0]["by_type"]["EMAIL"] == 1
        assert not report["degraded"]

        anonymized = anon.read_text()
        for secret in (NAME, EMAIL):
            assert secret not in anonymized
            assert secret not in captured.out + captured.err
        assert "[PERSON_1]" in anonymized and "[EMAIL_1]" in anonymized
        assert stat.S_IMODE(session.stat().st_mode) == 0o600

        reply = tmp_path / "reply.txt"
        reply.write_text("Write to EMAIL_1 and thank <PERSON_1>.")
        final = tmp_path / "final.txt"
        args = ["reconstruct", str(reply), "--out", str(final), "--session", str(session)]
        assert tool.main(args) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out)["replacements_made"] == 2
        assert NAME not in captured.out
        assert final.read_text() == f"Write to {EMAIL} and thank {NAME}."

    def test_session_is_extended_across_runs(self, tool: ModuleType, tmp_path: Path) -> None:
        session = tmp_path / "s.json"
        for i, text in enumerate([DOC, f"{NAME} met Hank Scorpio yesterday."]):
            (tmp_path / f"{i}.txt").write_text(text)
            args = ["anonymize", str(tmp_path / f"{i}.txt"), "--out", str(tmp_path / f"{i}.anon")]
            assert tool.main([*args, "--session", str(session)]) == 0
        second = (tmp_path / "1.anon").read_text()
        assert second.startswith("[PERSON_1] met [PERSON_2]")

    def test_separate_sessions_do_not_link_documents(
        self, tool: ModuleType, tmp_path: Path
    ) -> None:
        (tmp_path / "a.txt").write_text(DOC)
        (tmp_path / "b.txt").write_text("Hank Scorpio signed the contract.")
        args = ["anonymize", str(tmp_path / "a.txt"), str(tmp_path / "b.txt")]
        args += ["--out-dir", str(tmp_path / "out"), "--session-dir", str(tmp_path / "sessions")]
        assert tool.main(args) == 0
        assert (tmp_path / "out" / "b.txt").read_text().startswith("[PERSON_1]")
        sessions = sorted(p.name for p in (tmp_path / "sessions").iterdir())
        assert sessions == ["a.txt.session.json", "b.txt.session.json"]

    def test_scan_hides_text_unless_revealed(
        self, tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = tmp_path / "in.txt"
        source.write_text(DOC)
        assert tool.main(["scan", str(source)]) == 0
        hidden = capsys.readouterr().out
        assert NAME not in hidden and EMAIL not in hidden
        assert json.loads(hidden)["would_anonymize"] >= 2

        assert tool.main(["scan", str(source), "--reveal"]) == 0
        assert EMAIL in capsys.readouterr().out

    def test_session_listing_hides_originals(
        self, tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "in.txt").write_text(DOC)
        session = tmp_path / "s.json"
        args = ["anonymize", str(tmp_path / "in.txt"), "--out", str(tmp_path / "o.txt")]
        tool.main([*args, "--session", str(session)])
        capsys.readouterr()

        assert tool.main(["session", str(session)]) == 0
        listing = capsys.readouterr().out
        assert "[EMAIL_1]" in listing and EMAIL not in listing

        assert tool.main(["session", str(session), "--delete"]) == 0
        assert not session.exists()

    def test_custom_profile_and_type_filter(self, tool: ModuleType, tmp_path: Path) -> None:
        profile = SKILL.parent.parent / "examples" / "custom_profile.yaml"
        (tmp_path / "in.txt").write_text(f"{NAME} has badge EMP-48213.")
        base = ["anonymize", str(tmp_path / "in.txt"), "--profile", str(profile)]

        tool.main([*base, "--out", str(tmp_path / "all.txt"), "--session", str(tmp_path / "1")])
        assert "[EMPLOYEE_ID_1]" in (tmp_path / "all.txt").read_text()

        tool.main(
            [*base, "--out", str(tmp_path / "p.txt"), "--session", str(tmp_path / "2")]
            + ["--types", "PERSON"]
        )
        assert (tmp_path / "p.txt").read_text() == "[PERSON_1] has badge EMP-48213."

    def test_refuses_bad_requests(
        self, tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = tmp_path / "in.txt"
        source.write_text(DOC)
        session = ["--session", str(tmp_path / "s.json")]

        # Overwriting the input would destroy the only copy of the original.
        assert tool.main(["anonymize", str(source), "--out", str(source), *session]) == 1
        assert source.read_text() == DOC
        # A typo in the profile must not fall back to a weaker one.
        out = ["--out", str(tmp_path / "o.txt")]
        assert tool.main(["anonymize", str(source), *out, *session, "--profile", "nope"]) == 1
        assert not (tmp_path / "o.txt").exists()
        # Reconstructing without a session is an error, not a no-op.
        assert tool.main(["reconstruct", str(source), *out, "--session", "missing.json"]) == 1
        assert DOC not in capsys.readouterr().err

    def test_stdin_to_stdout(
        self,
        tool: ModuleType,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import io

        monkeypatch.setattr(sys, "stdin", io.StringIO(DOC))
        session = str(tmp_path / "s.json")
        assert tool.main(["anonymize", "-", "--out", "-", "--session", session]) == 0
        captured = capsys.readouterr()
        assert captured.out.startswith("Patient [PERSON_1]")
        assert json.loads(captured.err)["files"][0]["entities"] >= 2
