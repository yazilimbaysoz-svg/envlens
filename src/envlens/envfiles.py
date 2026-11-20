"""Dotenv parsing and secret-shape heuristics (standard library only)."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from envlens.models import Declaration

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INLINE_COMMENT = re.compile(r"\s+#")
_SECRET_KEY = re.compile(
    r"(SECRET|PASSWORD|PASSWD|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|TOKEN|CREDENTIAL|AUTH|SESSION|COOKIE)",
    re.IGNORECASE,
)
_TOKEN_PREFIX = re.compile(
    r"^(sk[_-](live|test|proj)?[-_]|rk[_-]|gh[pousr]_|github_pat_|AKIA|ASIA|xox[baprs]-|AIza|eyJ|-----BEGIN)"
)
_PLACEHOLDER_WORDS = frozenset(
    {
        "changeme",
        "change_me",
        "change-me",
        "example",
        "placeholder",
        "sample",
        "dummy",
        "fake",
        "todo",
        "tbd",
        "null",
        "none",
        "nil",
        "test",
        "value",
        "your_value",
        "yourvalue",
        "insert_value_here",
        "replace_me",
    }
)


def parse_dotenv(path: Path, *, is_example: bool | None = None) -> list[Declaration]:
    """Parse KEY=VALUE lines, ``export`` prefixes, quotes and inline comments."""
    declarations: list[Declaration] = []
    example = is_example if is_example is not None else ("example" in path.name.lower())
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return declarations
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        key = key.strip()
        if not _KEY_PATTERN.fullmatch(key):
            continue
        declarations.append(
            Declaration(
                name=key,
                path=path.name,
                line=line_number,
                value=clean_value(raw_value),
                is_example=example,
            )
        )
    return declarations


def clean_value(raw: str) -> str:
    """Remove surrounding quotes and unquoted inline comments from a dotenv value."""
    value = raw.strip()
    if value and value[0] in ("'", '"'):
        quote = value[0]
        end = 1
        while end < len(value):
            if value[end] == quote and value[end - 1] != "\\":
                break
            end += 1
        inner = value[1:end]
        if quote == '"':
            inner = inner.replace('\\"', '"').replace("\\n", "\n")
        else:
            inner = inner.replace("\\'", "'")
        return inner
    comment = _INLINE_COMMENT.search(value)
    if comment:
        value = value[: comment.start()]
    return value.strip()


def is_placeholder(value: str) -> bool:
    """Return True for empty, templated or documentation-only values."""
    candidate = value.strip().strip("'\"")
    if not candidate:
        return True
    lowered = candidate.lower()
    if lowered in _PLACEHOLDER_WORDS:
        return True
    if re.fullmatch(r"[xX*_-]{3,}", candidate):
        return True
    if "${" in candidate or "{{" in candidate or ("<" in candidate and ">" in candidate):
        return True
    return lowered.startswith(
        ("your_", "your-", "replace", "insert", "change", "example", "dummy", "fake", "set_me")
    )


def shannon_entropy(value: str) -> float:
    """Calculate Shannon entropy in bits per character."""
    if not value:
        return 0.0
    length = len(value)
    counts = Counter(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def looks_like_secret(name: str, value: str) -> bool:
    """Flag credential-shaped keys, known token prefixes and high-entropy blobs."""
    if is_placeholder(value):
        return False
    if len(value) < 8:
        return False
    if _TOKEN_PREFIX.match(value):
        return True
    if bool(_SECRET_KEY.search(name)):
        return True
    if "://" in value:
        return False
    return len(value) >= 20 and shannon_entropy(value) >= 4.0
