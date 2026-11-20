"""Turn raw references and declarations into actionable findings."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from envlens.config import (
    MANIFEST_NAMES,
    SOURCE_SUFFIXES,
    Config,
    is_env_file,
    iter_files,
)
from envlens.envfiles import is_placeholder, looks_like_secret, parse_dotenv
from envlens.manifests import scan_manifests
from envlens.models import Declaration, Finding, Kind, Reference, Report, Severity
from envlens.scanner import scan_sources, scan_workflow_references


def _locations(references: list[Reference]) -> tuple[str, ...]:
    return tuple(sorted({f"{ref.path}:{ref.line}" for ref in references}))


def _declaration_locations(declarations: list[Declaration]) -> tuple[str, ...]:
    return tuple(sorted({f"{item.path}:{item.line}" for item in declarations}))


def _count_files(root: Path, config: Config) -> int:
    sources = len(iter_files(root, config, suffixes=SOURCE_SUFFIXES))
    envs = len(iter_files(root, config, predicate=is_env_file))
    manifests = len(
        [
            path
            for path in iter_files(root, config, suffixes=frozenset({".yml", ".yaml"}))
            if path.name.lower() in MANIFEST_NAMES or ".github" in path.relative_to(root).parts
        ]
    )
    dockerfiles = len(iter_files(root, config, names=frozenset({"dockerfile", "containerfile"})))
    return sources + envs + manifests + dockerfiles


def analyze(root: Path, config: Config | None = None) -> Report:
    """Scan ``root`` and return a sorted, deduplicated report."""
    settings = config or Config.load(root)
    references = scan_sources(root, settings) + scan_workflow_references(root, settings)
    env_paths = iter_files(root, settings, predicate=is_env_file)
    declarations: list[Declaration] = []
    for path in env_paths:
        declarations.extend(parse_dotenv(path))
    declarations.extend(scan_manifests(root, settings))

    ignored = settings.ignore
    references = [ref for ref in references if ref.name not in ignored]
    declarations = [item for item in declarations if item.name not in ignored]

    examples = [item for item in declarations if item.is_example]
    runtime = [item for item in declarations if not item.is_example]

    refs_by_name: dict[str, list[Reference]] = defaultdict(list)
    for ref in references:
        refs_by_name[ref.name].append(ref)
    runtime_by_name: dict[str, list[Declaration]] = defaultdict(list)
    for item in runtime:
        runtime_by_name[item.name].append(item)

    example_names = {item.name for item in examples}
    declared_names = set(runtime_by_name)
    used_names = set(refs_by_name)
    findings: list[Finding] = []

    for name in sorted(used_names - declared_names - example_names):
        findings.append(
            Finding(
                kind=Kind.MISSING,
                severity=Severity.CRITICAL,
                name=name,
                message="read by code but never declared in an env file or manifest",
                locations=_locations(refs_by_name[name]),
            )
        )

    if examples:
        for name in sorted((used_names & (declared_names | example_names)) - example_names):
            findings.append(
                Finding(
                    kind=Kind.UNDECLARED,
                    severity=Severity.HIGH,
                    name=name,
                    message="used at runtime but absent from the env template",
                    locations=_locations(refs_by_name[name])
                    + _declaration_locations(runtime_by_name[name]),
                )
            )

    for name in sorted(example_names - used_names):
        findings.append(
            Finding(
                kind=Kind.STALE,
                severity=Severity.LOW,
                name=name,
                message="documented in a template but never read by the scanned code",
                locations=_declaration_locations([item for item in examples if item.name == name]),
            )
        )

    seen_leaks: set[tuple[str, str, str]] = set()
    for item in sorted(runtime, key=lambda decl: (decl.name, decl.path, decl.line)):
        key = (item.name, item.path, item.value)
        if key in seen_leaks or not looks_like_secret(item.name, item.value):
            continue
        seen_leaks.add(key)
        findings.append(
            Finding(
                kind=Kind.LEAK,
                severity=Severity.CRITICAL,
                name=item.name,
                message="credential-like value committed outside a template - rotate it",
                locations=(f"{item.path}:{item.line}",),
            )
        )

    values_by_name: dict[str, set[str]] = defaultdict(set)
    for item in runtime:
        if not is_placeholder(item.value):
            values_by_name[item.name].add(item.value)
    for name in sorted(name for name, values in values_by_name.items() if len(values) > 1):
        files = sorted({f"{item.path}:{item.line}" for item in runtime_by_name[name]})
        findings.append(
            Finding(
                kind=Kind.DRIFT,
                severity=Severity.MEDIUM,
                name=name,
                message=(
                    f"has {len(values_by_name[name])} different values across environments "
                    "- verify intentional"
                ),
                locations=tuple(files),
            )
        )

    findings.sort(key=lambda finding: (-finding.severity.rank, finding.kind.value, finding.name))
    return Report(
        root=settings.root.as_posix(),
        findings=tuple(findings),
        reference_count=len(references),
        declaration_count=len(declarations),
        files_scanned=_count_files(settings.root, settings),
    )
