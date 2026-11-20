"""Extraction of env declarations from compose files, workflows and Dockerfiles."""

from __future__ import annotations

import re
from pathlib import Path

from envlens.config import MANIFEST_NAMES, Config, iter_files
from envlens.models import Declaration

_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ENV_SECTION = re.compile(r"^(environment|env):\s*(.*)$")
_ENV_INSTRUCTION = re.compile(r"^ENV\s+", re.IGNORECASE)


def _valid(name: str) -> bool:
    return bool(_KEY_PATTERN.fullmatch(name))


def _add(declarations: list[Declaration], path: str, line: int, key: str, value: str) -> None:
    key = key.strip().strip("'\"")
    if _valid(key):
        declarations.append(
            Declaration(name=key, path=path, line=line, value=value.strip().strip("'\""))
        )


def parse_yaml_env(path: Path, config: Config) -> list[Declaration]:
    """Read simple ``environment:``/``env:`` mappings used by compose and Actions."""
    declarations: list[Declaration] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return declarations
    relative = config.relative(path)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        candidate = stripped[2:].strip() if stripped.startswith("- ") else stripped
        section = _ENV_SECTION.match(candidate)
        if section is None:
            continue
        base_indent = len(line) - len(line.lstrip())
        remainder = section.group(2).strip()
        if remainder.startswith("{"):
            for pair in remainder.strip("{}").split(","):
                if "=" in pair:
                    key, _, value = pair.partition("=")
                elif ":" in pair:
                    key, _, value = pair.partition(":")
                else:
                    continue
                _add(declarations, relative, index + 1, key, value)
            continue
        for following in lines[index + 1 :]:
            if not following.strip():
                continue
            indent = len(following) - len(following.lstrip())
            if indent <= base_indent:
                break
            item = following.strip()
            if item.startswith("#"):
                continue
            if item.startswith("- "):
                item = item[2:].strip()
            if "=" in item:
                key, _, value = item.partition("=")
            elif ":" in item:
                key, _, value = item.partition(":")
            else:
                key, value = item, ""
            _add(declarations, relative, index + 1, key, value)
    return declarations


def parse_dockerfile(path: Path, config: Config) -> list[Declaration]:
    """Parse both ``ENV KEY=value`` and legacy ``ENV KEY value`` forms."""
    declarations: list[Declaration] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return declarations
    relative = config.relative(path)
    logical: list[tuple[int, str]] = []
    buffer = ""
    start_line = 0
    for number, line in enumerate(lines, start=1):
        if not buffer:
            start_line = number
        buffer += line.strip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1]
            continue
        logical.append((start_line, buffer))
        buffer = ""
    for line_number, text in logical:
        if not _ENV_INSTRUCTION.match(text):
            continue
        payload = _ENV_INSTRUCTION.sub("", text).strip()
        if "=" in payload:
            pairs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\"[^\"]*\"|'[^']*'|\S+)", payload)
            for key, value in pairs:
                _add(declarations, relative, line_number, key, value.strip("'\""))
        else:
            parts = payload.split(None, 1)
            if len(parts) == 2:
                _add(declarations, relative, line_number, parts[0], parts[1])
    return declarations


def scan_manifests(root: Path, config: Config) -> list[Declaration]:
    """Collect declarations from compose files, GitHub workflows and Dockerfiles."""
    declarations: list[Declaration] = []
    yaml_paths = [
        path
        for path in iter_files(root, config, suffixes=frozenset({".yml", ".yaml"}))
        if path.name.lower() in MANIFEST_NAMES or ".github" in path.relative_to(root).parts
    ]
    for path in yaml_paths:
        declarations.extend(parse_yaml_env(path, config))
    for path in iter_files(root, config, names=frozenset({"dockerfile", "containerfile"})):
        declarations.extend(parse_dockerfile(path, config))
    return declarations
