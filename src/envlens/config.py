"""Configuration loading and filesystem traversal helpers."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDES: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "dist",
        "build",
        "site-packages",
        "vendor",
        ".idea",
        ".vscode",
        ".envlens-cache",
    }
)

SOURCE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".py",
        ".pyi",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".java",
        ".kt",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".sh",
        ".bash",
        ".zsh",
        ".tf",
        ".toml",
    }
)

MANIFEST_NAMES: frozenset[str] = frozenset(
    {
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "dockerfile",
        "containerfile",
    }
)


@dataclass(frozen=True)
class Config:
    """Effective settings for one scan."""

    root: Path
    exclude: frozenset[str] = DEFAULT_EXCLUDES
    ignore: frozenset[str] = frozenset()

    @classmethod
    def load(cls, root: Path) -> Config:
        """Load ``[tool.envlens]`` overrides from the project's pyproject.toml."""
        exclude = set(DEFAULT_EXCLUDES)
        ignore: set[str] = set()
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            try:
                with pyproject.open("rb") as handle:
                    data = tomllib.load(handle)
            except (OSError, tomllib.TOMLDecodeError):
                data = {}
            settings = data.get("tool", {}).get("envlens", {})
            if isinstance(settings, dict):
                exclude.update(_string_list(settings.get("exclude")))
                ignore.update(_string_list(settings.get("ignore")))
        return cls(root=root, exclude=frozenset(exclude), ignore=frozenset(ignore))

    def relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def iter_files(
    root: Path,
    config: Config,
    *,
    suffixes: frozenset[str] | None = None,
    names: frozenset[str] | None = None,
    predicate: Callable[[Path], bool] | None = None,
) -> list[Path]:
    """Return a sorted list of files below ``root`` matching the given filters."""
    matches: list[Path] = []
    if not root.is_dir():
        return matches
    for path in root.rglob("*"):
        if not path.is_file() or any(
            part in config.exclude for part in path.relative_to(root).parts[:-1]
        ):
            continue
        matches_extension = suffixes is not None and path.suffix.lower() in suffixes
        matches_name = names is not None and path.name.lower() in names
        matches_predicate = predicate is not None and predicate(path)
        if matches_extension or matches_name or matches_predicate:
            matches.append(path)
    return sorted(set(matches))


def is_env_file(path: Path) -> bool:
    """Recognise ``.env``, ``.env.local``, ``prod.env`` and friends."""
    name = path.name
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


def is_example_file(path: Path) -> bool:
    """Recognise template env files that must never contain real values."""
    lowered = path.name.lower()
    return any(token in lowered for token in ("example", "sample", "template", "dist"))
