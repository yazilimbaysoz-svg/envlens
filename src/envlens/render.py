"""Human, JSON and Markdown renderers for envlens reports."""

from __future__ import annotations

import re

from envlens.models import Report

_COLORS: dict[str, str] = {
    "critical": "\033[91m",
    "high": "\033[93m",
    "medium": "\033[96m",
    "low": "\033[94m",
    "info": "\033[90m",
}
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _paint(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{_RESET}" if enabled else text


def _summary(report: Report) -> str:
    counts = report.counts
    parts = [f"{count} {level}" for level, count in counts.items() if count]
    breakdown = ", ".join(parts) if parts else "none"
    return (
        f"Scanned {report.files_scanned} files | {report.reference_count} references | "
        f"{report.declaration_count} declarations | findings: {breakdown}"
    )


def render_table(report: Report, *, color: bool = False) -> str:
    """Render a compact terminal table with an ANSI-colored severity column."""
    lines: list[str] = []
    if not report.findings:
        lines.append(
            _paint("PASS", _COLORS["low"], color) + "  No environment configuration issues found."
        )
    else:
        lines.append(_paint(f"{'SEVERITY':<9} {'KIND':<12} {'VARIABLE':<26} DETAILS", _BOLD, color))
        lines.append("-" * 110)
        for finding in report.findings:
            severity = finding.severity.value
            label = _paint(f"{severity:<9}", _COLORS.get(severity, ""), color)
            detail = finding.message
            if finding.locations:
                shown = ", ".join(finding.locations[:3])
                suffix = " (+more)" if len(finding.locations) > 3 else ""
                detail = f"{detail} [{shown}{suffix}]"
            detail = detail.replace("\n", " ")
            lines.append(f"{label} {finding.kind.value:<12} {finding.name:<26} {detail}")
    lines.append(_DIM + _summary(report) + _RESET if color else _summary(report))
    return "\n".join(lines)


def render_json(report: Report) -> str:
    """Render a machine-readable report for CI pipelines."""
    import json

    payload = {
        "root": report.root,
        "summary": {
            "files_scanned": report.files_scanned,
            "references": report.reference_count,
            "declarations": report.declaration_count,
            "total_findings": len(report.findings),
            "counts": report.counts,
        },
        "findings": [
            {
                "kind": finding.kind.value,
                "severity": finding.severity.value,
                "name": finding.name,
                "message": finding.message,
                "locations": list(finding.locations),
            }
            for finding in report.findings
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _escape(text: str) -> str:
    return re.sub(r"\|", "\\|", text)


def render_markdown(report: Report) -> str:
    """Render a GitHub job-summary friendly Markdown table."""
    lines = [
        "## envlens report",
        "",
        _summary(report).replace("|", "\\|"),
        "",
    ]
    if report.findings:
        lines.extend(
            [
                "| Severity | Kind | Variable | Details |",
                "| --- | --- | --- | --- |",
            ]
        )
        for finding in report.findings:
            locations = ", ".join(finding.locations)
            detail = f"{finding.message} ({_escape(locations)})" if locations else finding.message
            lines.append(
                f"| {finding.severity.value} | {finding.kind.value} | "
                f"`{_escape(finding.name)}` | {_escape(detail)} |"
            )
    else:
        lines.append("No environment configuration issues found.")
    return "\n".join(lines)
