"""Tests for the analyzer: all five finding rules and their policies."""

from __future__ import annotations

from envlens.analysis import analyze
from envlens.config import Config
from envlens.models import Kind, Severity


def _fixture(tmp_path, write):
    write(
        tmp_path,
        "app.py",
        """
import os
DATABASE_URL = os.getenv("DATABASE_URL")
STRIPE_SECRET_KEY = os.environ["STRIPE_SECRET_KEY"]
APP_MODE = os.environ.get("APP_MODE", "dev")
LEGACY_FLAG = os.environ["LEGACY_FLAG"]
""",
    )
    write(
        tmp_path,
        ".env",
        """DATABASE_URL=postgres://localhost/db
STRIPE_SECRET_KEY=sk_live_abcdefghijklmnop
APP_MODE=dev
REDIS_URL=redis://localhost:6379
""",
    )
    write(
        tmp_path,
        ".env.example",
        """DATABASE_URL=your_database_url
APP_MODE=dev
LEGACY_FLAG=
STALE_FLAG=false
""",
    )
    write(
        tmp_path,
        "docker-compose.yml",
        """services:
  api:
    environment:
      - DATABASE_URL=postgres://compose/db
      - REDIS_URL=redis://compose:6379
""",
    )
    return analyze(tmp_path)


def test_fixture_produces_all_expected_findings(tmp_path, write):
    report = _fixture(tmp_path, write)
    by_kind = {
        kind: [finding for finding in report.findings if finding.kind == kind] for kind in Kind
    }

    assert [finding.name for finding in by_kind[Kind.MISSING]] == []
    assert [finding.name for finding in by_kind[Kind.UNDECLARED]] == ["STRIPE_SECRET_KEY"]
    assert [finding.name for finding in by_kind[Kind.STALE]] == ["STALE_FLAG"]
    assert [finding.name for finding in by_kind[Kind.LEAK]] == ["STRIPE_SECRET_KEY"]
    assert [finding.name for finding in by_kind[Kind.DRIFT]] == ["DATABASE_URL", "REDIS_URL"]


def test_findings_are_sorted_by_severity_then_name(tmp_path, write):
    report = _fixture(tmp_path, write)
    severities = [finding.severity.rank for finding in report.findings]
    assert severities == sorted(severities, reverse=True)
    assert report.max_severity is Severity.CRITICAL
    assert report.counts == {"info": 0, "low": 1, "medium": 2, "high": 1, "critical": 1}


def test_missing_variable_is_critical(tmp_path, write):
    write(tmp_path, "app.py", 'value = os.getenv("NEVER_DECLARED")\n')
    report = analyze(tmp_path)

    missing = [finding for finding in report.findings if finding.kind is Kind.MISSING]
    assert len(missing) == 1
    assert missing[0].severity is Severity.CRITICAL
    assert missing[0].locations == ("app.py:1",)


def test_workflow_secret_reference_is_a_reference(tmp_path, write):
    write(
        tmp_path,
        ".github/workflows/deploy.yml",
        "steps:\n  - uses: x\n    with:\n      token: ${{ secrets.DEPLOY_TOKEN }}\n",
    )
    report = analyze(tmp_path)
    missing = [finding for finding in report.findings if finding.kind is Kind.MISSING]
    assert [finding.name for finding in missing] == ["DEPLOY_TOKEN"]


def test_example_only_declaration_is_not_missing(tmp_path, write):
    write(tmp_path, "app.py", 'value = os.getenv("DOCUMENTED_ONLY")\n')
    write(tmp_path, ".env.example", "DOCUMENTED_ONLY=sample\n")
    report = analyze(tmp_path)

    assert not [finding for finding in report.findings if finding.kind is Kind.MISSING]


def test_no_template_suppresses_undeclared(tmp_path, write):
    write(tmp_path, "app.py", 'value = os.getenv("ONLY_IN_ENV")\n')
    write(tmp_path, ".env", "ONLY_IN_ENV=real\n")
    report = analyze(tmp_path)

    assert not [finding for finding in report.findings if finding.kind is Kind.UNDECLARED]


def test_drift_needs_two_distinct_concrete_values(tmp_path, write):
    write(tmp_path, ".env", "REGION=eu-west\n")
    write(tmp_path, ".env.local", "REGION=eu-west\n")
    assert not analyze(tmp_path).findings

    write(tmp_path, ".env.prod", "REGION=us-east\n")
    drift = [finding for finding in analyze(tmp_path).findings if finding.kind is Kind.DRIFT]
    assert len(drift) == 1
    assert "2 different values" in drift[0].message


def test_placeholders_do_not_trigger_leaks_or_drift(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("API_KEY")\n')
    write(tmp_path, ".env", "API_KEY=changeme\nDB_PASSWORD=your_password\n")
    write(tmp_path, ".env.example", "API_KEY=your_api_key\n")
    assert analyze(tmp_path).findings == ()


def test_ignore_list_suppresses_named_findings(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("IGNORED_VAR")\n')
    config = Config.load(tmp_path)
    config = Config(root=config.root, exclude=config.exclude, ignore=frozenset({"IGNORED_VAR"}))
    assert analyze(tmp_path, config).findings == ()


def test_config_loads_tool_section(tmp_path, write):
    write(
        tmp_path,
        "pyproject.toml",
        '[tool.envlens]\nexclude = ["fixtures"]\nignore = ["KNOWN_DYNAMIC"]\n',
    )
    config = Config.load(tmp_path)
    assert "fixtures" in config.exclude
    assert config.ignore == frozenset({"KNOWN_DYNAMIC"})


def test_broken_pyproject_is_ignored(tmp_path, write):
    write(tmp_path, "pyproject.toml", "this is not = valid toml [\n")
    assert Config.load(tmp_path).ignore == frozenset()


def test_excluded_directory_is_not_scanned(tmp_path, write):
    write(tmp_path, "generated/app.py", 'os.getenv("GENERATED_VAR")\n')
    config = Config.load(tmp_path)
    config = Config(root=config.root, exclude=frozenset({*config.exclude, "generated"}))
    assert analyze(tmp_path, config).findings == ()


def test_report_metadata(tmp_path, write):
    write(tmp_path, "app.py", 'os.getenv("VAR")\n')
    write(tmp_path, ".env", "VAR=ok\n")
    report = analyze(tmp_path)

    assert report.reference_count == 1
    assert report.declaration_count == 1
    assert report.files_scanned == 2
    assert report.root == tmp_path.as_posix()
    assert report.counts["critical"] == 0
