"""Core data structures shared by the scanner, analyzer and renderers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """Ordered finding severity, from least to most urgent."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return SEVERITY_RANK[self]


SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
)
SEVERITY_RANK: dict[Severity, int] = {level: index for index, level in enumerate(SEVERITY_ORDER)}


class Kind(StrEnum):
    """Supported finding categories."""

    MISSING = "missing"
    UNDECLARED = "undeclared"
    STALE = "stale"
    LEAK = "leak"
    DRIFT = "drift"


@dataclass(frozen=True)
class Reference:
    """A variable read by application code or a workflow."""

    name: str
    path: str
    line: int
    context: str


@dataclass(frozen=True)
class Declaration:
    """A variable assigned a value in an env file or deployment manifest."""

    name: str
    path: str
    line: int
    value: str
    is_example: bool = False


@dataclass(frozen=True)
class Finding:
    """A single actionable issue produced by the analyzer."""

    kind: Kind
    severity: Severity
    name: str
    message: str
    locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Report:
    """Aggregated result of a scan."""

    root: str
    findings: tuple[Finding, ...]
    reference_count: int
    declaration_count: int
    files_scanned: int

    @property
    def counts(self) -> dict[str, int]:
        result = {severity.value: 0 for severity in SEVERITY_ORDER}
        for finding in self.findings:
            result[finding.severity.value] += 1
        return result

    @property
    def max_severity(self) -> Severity | None:
        if not self.findings:
            return None
        return max((finding.severity for finding in self.findings), key=lambda level: level.rank)
