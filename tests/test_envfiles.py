"""Tests for dotenv parsing and secret heuristics."""

from __future__ import annotations

import pytest

from envlens.config import is_env_file, is_example_file
from envlens.envfiles import (
    clean_value,
    is_placeholder,
    looks_like_secret,
    parse_dotenv,
    shannon_entropy,
)


def test_parse_dotenv_handles_export_quotes_and_comments(tmp_path, write):
    path = write(
        tmp_path,
        ".env.local",
        """
# database settings
export DB_HOST="localhost"
API_KEY='abc123' # inline comment
PLAIN=value#not_a_comment
EMPTY=
1INVALID=nope
SPACED KEY=nope
""",
    )

    parsed = parse_dotenv(path)

    assert [(item.name, item.value, item.line) for item in parsed] == [
        ("DB_HOST", "localhost", 3),
        ("API_KEY", "abc123", 4),
        ("PLAIN", "value#not_a_comment", 5),
        ("EMPTY", "", 6),
    ]
    assert all(not item.is_example for item in parsed)


def test_parse_dotenv_example_flag_and_escapes(tmp_path, write):
    path = write(tmp_path, ".env.example", "TOKEN=\"line\\nnext\"\nQUOTED='it\\'s ok'\n")
    parsed = parse_dotenv(path)

    assert parsed[0].value == "line\nnext"
    assert parsed[1].value == "it's ok"
    assert all(item.is_example for item in parsed)


def test_parse_dotenv_missing_file_returns_empty(tmp_path):
    assert parse_dotenv(tmp_path / "missing.env") == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (".env", True),
        (".env.local", True),
        (".env.production", True),
        ("prod.env", True),
        ("settings.txt", False),
        ("environment.yml", False),
    ],
)
def test_is_env_file(name, expected):
    from pathlib import Path

    assert is_env_file(Path(name)) is expected


@pytest.mark.parametrize(
    "name",
    [".env.example", ".env.sample", ".env.template", "app.env.dist"],
)
def test_is_example_file(name):
    from pathlib import Path

    assert is_example_file(Path(name)) is True


def test_is_example_file_negative():
    from pathlib import Path

    assert is_example_file(Path(".env.production")) is False


@pytest.mark.parametrize(
    "value", ["", "changeme", "your_api_key", "<insert>", "${OTHER}", "xxx", "TODO"]
)
def test_is_placeholder(value):
    assert is_placeholder(value) is True


@pytest.mark.parametrize("value", ["postgres://localhost/db", "sk_live_abcdefgh1234", "prod-value"])
def test_is_placeholder_negative(value):
    assert is_placeholder(value) is False


def test_clean_value_variants():
    assert clean_value('  "quoted"  ') == "quoted"
    assert clean_value("'single'") == "single"
    assert clean_value("value   # note") == "value"
    assert clean_value("value#note") == "value#note"


def test_shannon_entropy():
    assert shannon_entropy("") == 0.0
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("abcd") == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DB_PASSWORD", "supersecretvalue"),
        ("API_KEY", "abcdefgh12345678"),
        ("TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz"),
        ("TOKEN", "sk_live_abcdefghijklmnop"),
        ("CONFIG", "aB3dE5gH7jK9mN2pQ4rS"),
    ],
)
def test_looks_like_secret_positive(name, value):
    assert looks_like_secret(name, value) is True


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DB_PASSWORD", "changeme"),
        ("SHORT_TOKEN", "abc"),
        ("DATABASE_URL", "postgres://user:pass@localhost/db"),
        ("API_KEY", "${SECRET_API_KEY}"),
    ],
)
def test_looks_like_secret_negative(name, value):
    assert looks_like_secret(name, value) is False
