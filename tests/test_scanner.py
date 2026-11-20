"""Tests for multi-language source scanning."""

from __future__ import annotations

import pytest

from envlens.config import Config
from envlens.scanner import scan_sources, scan_workflow_references


def _scan(tmp_path, write, filename: str, content: str) -> list[str]:
    write(tmp_path, filename, content)
    return sorted({ref.name for ref in scan_sources(tmp_path, Config.load(tmp_path))})


@pytest.mark.parametrize(
    ("filename", "code", "expected"),
    [
        ("app.py", 'x = os.getenv("ALPHA")', ["ALPHA"]),
        ("app.py", 'x = os.environ["BETA"]', ["BETA"]),
        ("app.py", 'x = os.environ.get("GAMMA", "d")', ["GAMMA"]),
        ("app.py", "from os import getenv\nx = getenv('DELTA')", ["DELTA"]),
        ("index.js", "const x = process.env.EPSILON", ["EPSILON"]),
        ("index.ts", 'const x = process.env["ZETA"]', ["ZETA"]),
        ("main.ts", 'const x = Deno.env.get("ETA")', ["ETA"]),
        ("main.js", "const x = Bun.env.THETA", ["THETA"]),
        ("main.go", 'v := os.Getenv("IOTA")', ["IOTA"]),
        ("main.go", 'v, ok := os.LookupEnv("KAPPA")', ["KAPPA"]),
        ("main.rs", 'let v = env::var("LAMBDA")?;', ["LAMBDA"]),
        ("main.rs", 'let v = std::env::var_os("MU")?;', ["MU"]),
        ("app.rb", 'v = ENV["NU"]', ["NU"]),
        ("app.php", '$v = $_ENV["XI"];', ["XI"]),
        ("App.java", 'String v = System.getenv("OMICRON");', ["OMICRON"]),
        ("App.cs", 'var v = Environment.GetEnvironmentVariable("PI");', ["PI"]),
        ("run.sh", 'echo "${RHO:-default}"', ["RHO"]),
        ("run.sh", "echo $NO_BRACES", []),
    ],
)
def test_language_patterns(tmp_path, write, filename, code, expected):
    assert _scan(tmp_path, write, filename, code) == expected


def test_comments_and_ignore_marker_are_skipped(tmp_path, write):
    content = """
# os.getenv("COMMENTED")
// process.env.JS_COMMENT
* os.getenv("DOC_COMMENT")
value = os.getenv("DYNAMIC")  # envlens:ignore
real = os.getenv("REAL_KEY")
"""
    assert _scan(tmp_path, write, "app.py", content) == ["REAL_KEY"]


def test_multiple_references_are_deduplicated_and_have_locations(tmp_path, write):
    write(tmp_path, "a.py", 'os.getenv("SAME")\nos.getenv("SAME")\n')
    write(tmp_path, "b.py", 'os.getenv("SAME")\nos.getenv("OTHER")\n')
    references = scan_sources(tmp_path, Config.load(tmp_path))

    assert sorted({ref.name for ref in references}) == ["OTHER", "SAME"]
    same = [ref for ref in references if ref.name == "SAME"]
    assert {(ref.path, ref.line) for ref in same} == {("a.py", 1), ("a.py", 2), ("b.py", 1)}


def test_excluded_directories_are_skipped(tmp_path, write):
    write(tmp_path, "node_modules/pkg/index.js", "process.env.VENDOR_KEY")
    write(tmp_path, ".venv/lib/mod.py", 'os.getenv("VENV_KEY")')
    write(tmp_path, "app.py", 'os.getenv("APP_KEY")')
    assert _scan(tmp_path, write, "app.py", 'os.getenv("APP_KEY")') == ["APP_KEY"]


def test_scan_workflow_references(tmp_path, write):
    write(
        tmp_path,
        ".github/workflows/deploy.yml",
        """
env:
  APP_ENV: ${{ vars.APP_ENV }}
steps:
  - uses: action
    with:
      token: ${{ secrets.DEPLOY_TOKEN }}
      ignorable: ${{ secrets.IGNORED }} # envlens:ignore
  - run: echo ${{ env.APP_ENV }}
""",
    )
    references = scan_workflow_references(tmp_path, Config.load(tmp_path))
    assert sorted({ref.name for ref in references}) == ["APP_ENV", "DEPLOY_TOKEN"]


def test_no_workflows_returns_empty(tmp_path):
    assert scan_workflow_references(tmp_path, Config.load(tmp_path)) == []
