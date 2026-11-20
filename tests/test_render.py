"""Tests for table, JSON and Markdown renderers."""

from __future__ import annotations

import json

from envlens.models import Finding, Kind, Report, Severity
from envlens.render import render_json, render_markdown, render_table

_FINDING = Finding(
    kind=Kind.LEAK,
    severity=Severity.CRITICAL,
    name="API_KEY",
    message="credential-like value | committed outside a template",
    locations=(".env:4", "app.py:9"),
)


def _report(*findings: Finding) -> Report:
    return Report(
        root="/tmp/demo",
        findings=findings,
        reference_count=5,
        declaration_count=3,
        files_scanned=4,
    )


def test_render_table_contains_all_columns_and_summary():
    output = render_table(_report(_FINDING))

    assert "SEVERITY" in output
    assert "critical" in output
    assert "leak" in output
    assert "API_KEY" in output
    assert ".env:4, app.py:9" in output
    assert "Scanned 4 files" in output
    assert "1 critical" in output


def test_render_table_color_mode_adds_ansi():
    plain = render_table(_report(_FINDING))
    colored = render_table(_report(_FINDING), color=True)

    assert "\033[" not in plain
    assert "\033[91m" in colored
    assert "\033[0m" in colored


def test_render_table_truncates_many_locations():
    finding = Finding(
        kind=Kind.DRIFT,
        severity=Severity.MEDIUM,
        name="REGION",
        message="differs",
        locations=("a:1", "b:2", "c:3", "d:4"),
    )
    assert "(+more)" in render_table(_report(finding))


def test_render_table_clean_project():
    output = render_table(_report())
    assert "PASS" in output
    assert "No environment configuration issues found." in output


def test_render_json_structure():
    payload = json.loads(render_json(_report(_FINDING)))

    assert payload["root"] == "/tmp/demo"
    assert payload["summary"]["files_scanned"] == 4
    assert payload["summary"]["total_findings"] == 1
    assert payload["findings"][0] == {
        "kind": "leak",
        "severity": "critical",
        "name": "API_KEY",
        "message": "credential-like value | committed outside a template",
        "locations": [".env:4", "app.py:9"],
    }


def test_render_markdown_escapes_pipes():
    output = render_markdown(_report(_FINDING))

    assert output.startswith("## envlens report")
    assert "| Severity | Kind | Variable | Details |" in output
    assert "credential-like value \\| committed" in output
    assert "`API_KEY`" in output


def test_render_markdown_clean_project():
    output = render_markdown(_report())
    assert "No environment configuration issues found." in output
