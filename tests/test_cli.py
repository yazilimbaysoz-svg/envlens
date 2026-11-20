"""End-to-end tests for the command line interface."""

from __future__ import annotations

import json

import pytest

from envlens.cli import build_parser, main
from envlens.sync import sync_example


@pytest.fixture
def vulnerable_project(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("NEVER_DECLARED")\nos.getenv("DOCUMENTED")\n')
    write(tmp_path, ".env.example", "DOCUMENTED=sample\n")
    write(tmp_path, ".env", "DB_PASSWORD=veryrealpassword123\n")
    return tmp_path


def test_scan_table_fails_by_default(vulnerable_project, capsys):
    code = main(["scan", str(vulnerable_project)])
    output = capsys.readouterr().out

    assert code == 1
    assert "NEVER_DECLARED" in output
    assert "Scanned" in output


def test_scan_fail_on_none_returns_zero(vulnerable_project, capsys):
    assert main(["scan", str(vulnerable_project), "--fail-on", "none"]) == 0
    assert "NEVER_DECLARED" in capsys.readouterr().out


def test_scan_fail_on_critical(vulnerable_project):
    assert main(["scan", str(vulnerable_project), "--fail-on", "critical"]) == 1


def test_scan_json_format(vulnerable_project, capsys):
    assert main(["scan", str(vulnerable_project), "--format", "json", "--fail-on", "none"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["total_findings"] >= 2


def test_scan_markdown_format(vulnerable_project, capsys):
    assert main(["scan", str(vulnerable_project), "--format", "markdown", "--fail-on", "none"]) == 0
    assert "## envlens report" in capsys.readouterr().out


def test_bare_command_scans_working_directory(vulnerable_project, capsys, monkeypatch):
    monkeypatch.chdir(vulnerable_project)
    assert main([]) == 1
    assert "NEVER_DECLARED" in capsys.readouterr().out


def test_no_color_flag(vulnerable_project, capsys):
    main(["scan", str(vulnerable_project), "--no-color", "--fail-on", "none"])
    assert "\033[" not in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "envlens 0.1.0" in capsys.readouterr().out


def test_invalid_path_errors(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(tmp_path / "missing")])
    assert exc.value.code == 2


def test_parser_defaults():
    args = build_parser().parse_args([])
    assert args.command is None


def test_sync_example_adds_only_empty_values(tmp_path, write, capsys):
    write(tmp_path, "app.py", 'os.getenv("NEW_KEY")\n')
    write(tmp_path, ".env", "SECRET_PASSWORD=supersecretvalue\n")

    added = sync_example(tmp_path)
    example = (tmp_path / ".env.example").read_text(encoding="utf-8")

    assert added == ["NEW_KEY", "SECRET_PASSWORD"]
    assert "NEW_KEY=\n" in example
    assert "SECRET_PASSWORD=\n" in example
    assert "supersecretvalue" not in example
    assert main(["sync-example", str(tmp_path)]) == 0


def test_sync_example_is_idempotent(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("STABLE_KEY")\n')
    assert sync_example(tmp_path) == ["STABLE_KEY"]
    assert sync_example(tmp_path) == []


def test_sync_example_preserves_existing_template(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("EXISTING_KEY")\nos.getenv("ADDED_KEY")\n')
    write(tmp_path, ".env.example", "EXISTING_KEY=your_value\n# keep this comment\n")

    assert sync_example(tmp_path) == ["ADDED_KEY"]
    example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "# keep this comment" in example
    assert "EXISTING_KEY=your_value" in example


def test_sync_cli_reports_up_to_date(tmp_path, capsys):
    assert main(["sync-example", str(tmp_path)]) == 0
    assert "already up to date" in capsys.readouterr().out
