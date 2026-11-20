"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def write() -> Callable[[Path, str, str], Path]:
    """Write a UTF-8 file below a temporary project root."""

    def _write(root: Path, relative: str, content: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    return _write
