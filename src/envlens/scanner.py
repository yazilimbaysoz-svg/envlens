"""Language-aware extraction of environment variable reads from source code."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from envlens.config import SOURCE_SUFFIXES, Config, iter_files
from envlens.models import Reference

IGNORE_MARKER = "envlens:ignore"


@dataclass(frozen=True)
class _Pattern:
    language: str
    regex: re.Pattern[str]


_VAR = r"([A-Z][A-Z0-9_]*)"
_QUOTE = r"[\"']"

_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("python", re.compile(rf"\bos\.environ\.get\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("python", re.compile(rf"\bos\.environ\[\s*{_QUOTE}{_VAR}{_QUOTE}\s*\]")),
    _Pattern("python", re.compile(rf"\b(?:os\.)?getenv\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("python", re.compile(rf"\benviron\.get\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("javascript", re.compile(rf"\bprocess\.env\.{_VAR}\b")),
    _Pattern("javascript", re.compile(rf"\bprocess\.env\[\s*{_QUOTE}{_VAR}{_QUOTE}\s*\]")),
    _Pattern("javascript", re.compile(rf"\b(?:Deno|Bun)\.env\.get\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("javascript", re.compile(rf"\b(?:Deno|Bun)\.env\.{_VAR}\b")),
    _Pattern("go", re.compile(rf"\bos\.(?:Getenv|LookupEnv)\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("rust", re.compile(rf"\b(?:std::)?env::var(?:_os)?\(\s*{_QUOTE}{_VAR}{_QUOTE}")),
    _Pattern("ruby", re.compile(rf"\bENV\[\s*{_QUOTE}{_VAR}{_QUOTE}\s*\]")),
    _Pattern("php", re.compile(rf"\$_ENV\[\s*{_QUOTE}{_VAR}{_QUOTE}\s*\]")),
    _Pattern("java", re.compile(rf'\bSystem\.getenv\(\s*"{_VAR}"')),
    _Pattern("dotnet", re.compile(rf'\bEnvironment\.GetEnvironmentVariable\(\s*"{_VAR}"')),
    _Pattern("shell", re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::[-+][^}]*)?\}")),
)


def scan_sources(root: Path, config: Config) -> list[Reference]:
    """Find every env var read in the project's source files."""
    references: list[Reference] = []
    for path in iter_files(root, config, suffixes=SOURCE_SUFFIXES):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        relative = config.relative(path)
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*", "/*", "--")):
                continue
            if IGNORE_MARKER in stripped:
                continue
            for pattern in _PATTERNS:
                for match in pattern.regex.finditer(line):
                    references.append(
                        Reference(
                            name=match.group(1),
                            path=relative,
                            line=line_number,
                            context=stripped[:120],
                        )
                    )
    return sorted(set(references), key=lambda ref: (ref.name, ref.path, ref.line))


def scan_workflow_references(root: Path, config: Config) -> list[Reference]:
    """Extract ${{ secrets.X }} / ${{ env.X }} references from GitHub Actions."""
    expression = re.compile(r"\$\{\{\s*(?:secrets|env|vars)\.([A-Z][A-Z0-9_]*)\s*\}\}")
    references: list[Reference] = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return references
    for path in sorted(workflow_dir.glob("*.y*ml")):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        relative = config.relative(path)
        for line_number, line in enumerate(lines, start=1):
            if IGNORE_MARKER in line:
                continue
            for match in expression.finditer(line):
                references.append(
                    Reference(
                        name=match.group(1),
                        path=relative,
                        line=line_number,
                        context=line.strip()[:120],
                    )
                )
    return references
