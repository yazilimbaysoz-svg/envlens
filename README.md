# envlens

[![CI](https://github.com/yazilimbaysoz-svg/envlens/actions/workflows/ci.yml/badge.svg)](https://github.com/yazilimbaysoz-svg/envlens/actions/workflows/ci.yml)
[![Stars](https://img.shields.io/github/stars/yazilimbaysoz-svg/envlens?style=flat-square)](https://github.com/yazilimbaysoz-svg/envlens/stargazers)
[![Release](https://img.shields.io/github/v/release/yazilimbaysoz-svg/envlens?style=flat-square)](https://github.com/yazilimbaysoz-svg/envlens/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)](https://www.python.org/downloads/)
[![Runtime deps](https://img.shields.io/badge/runtime_dependencies-ZERO-brightgreen?style=flat-square)](pyproject.toml)
[![License: MIT](https://img.shields.io/github/license/yazilimbaysoz-svg/envlens?style=flat-square)](LICENSE)

> **X-ray vision for environment variables.** `envlens` finds missing config, undocumented variables, stale templates, committed secrets and cross-environment drift — before they become 3 a.m. incidents.

`envlens` is a **single-binary-feel, zero-runtime-dependency** CLI built with the Python standard library. It reads your source code, `.env` family files, Docker Compose manifests, Dockerfiles and GitHub Actions workflows, then cross-checks them in milliseconds. It runs anywhere Python 3.11+ runs, needs no network access, and never uploads your configuration.

---

## Why envlens?

Environment variables are the most common source of "works on my machine", failed deploys and leaked credentials:

| Pain | What happens without envlens | What envlens does |
| --- | --- | --- |
| Code reads `STRIPE_KEY`, nobody declared it | `None` at runtime, crash in production | **`MISSING`** (critical) with exact file:line |
| `.env.local` has a key, `.env.example` does not | New teammate / CI cannot start the app | **`UNDECLARED`** (high) |
| Template documents a key nobody uses anymore | Config rot, misleading onboarding | **`STALE`** (low) |
| `AWS_SECRET_ACCESS_KEY=hunter2real...` committed | Credential leak, incident response | **`LEAK`** (critical) |
| Same key has different values across files | Silent config drift between staging/prod | **`DRIFT`** (medium) |

Unlike secret scanners, `envlens` looks at the **relationship** between code, templates and deployment manifests. Unlike config linters, it understands 10+ languages and produces CI-friendly JSON/Markdown.

---

## Quick start

```bash
# Install from source (no runtime dependencies)
git clone https://github.com/yazilimbaysoz-svg/envlens.git
cd envlens
uv tool install .

# Scan the current project
envlens scan .

# Machine-readable output for pipelines
envlens scan . --format json

# Only fail the build on critical findings
envlens scan . --fail-on critical

# Safely add missing keys to .env.example (empty values only)
envlens sync-example .
```

No `uv`? `pip install .` works too. No install? `python -m envlens` from a checkout with `src` on the path.

---

## Example output

```text
SEVERITY  KIND         VARIABLE                   DETAILS
critical  missing      STRIPE_KEY                 read by code but never declared in an env file or manifest [app.py:42]
critical  leak         AWS_SECRET_ACCESS_KEY      credential-like value committed outside a template - rotate it [.env.local:7]
high      undeclared   DATABASE_URL               used at runtime but absent from the env template [app.py:12, docker-compose.yml:9]
low       stale        LEGACY_FEATURE_FLAG        documented in a template but never read by the scanned code [.env.example:14]
medium    drift        REDIS_URL                  has 2 different values across environments - verify intentional [.env:4, .env.prod:3]
Scanned 23 files | 37 references | 19 declarations | findings: 2 critical, 1 high, 1 medium, 1 low
```

Clean project:

```text
PASS  No environment configuration issues found.
Scanned 23 files | 37 references | 19 declarations | findings: none
```

---

## What it detects

### `MISSING` — critical
A variable read by code (or `${{ secrets.X }}` in a workflow) but not present in any `.env*` file, Compose manifest, Dockerfile or Actions `env:` block.

### `UNDECLARED` — high
A runtime variable that exists somewhere but is absent from `.env.example`, so new developers and CI cannot discover it.

### `STALE` — low
A key documented in the template that no scanned code reads anymore.

### `LEAK` — critical
A non-placeholder value assigned to a credential-shaped key (`PASSWORD`, `TOKEN`, `API_KEY`, `SECRET`, ...), a known token prefix (`sk-`, `ghp_`, `AKIA`, `xoxb-`, `eyJ...`) or a high-entropy blob (Shannon entropy ≥ 4.0, length ≥ 20). Template files are never flagged as leaks.

### `DRIFT` — medium
The same key holds different concrete values in more than one environment file — a prompt to verify intent, not a hard error.

---

## Supported sources

| Category | Examples |
| --- | --- |
| Python | `os.getenv("X")`, `os.environ["X"]`, `os.environ.get("X")`, `getenv("X")` |
| JavaScript / TypeScript | `process.env.X`, `process.env["X"]`, `Deno.env.get("X")`, `Bun.env.X` |
| Go | `os.Getenv("X")`, `os.LookupEnv("X")` |
| Rust | `env::var("X")`, `std::env::var_os("X")` |
| Ruby / PHP / Java / .NET | `ENV["X"]`, `$_ENV["X"]`, `System.getenv("X")`, `Environment.GetEnvironmentVariable("X")` |
| Shell / Docker | `${X}`, `${X:-default}`, Compose `environment:`, Dockerfile `ENV` |
| GitHub Actions | `env:` blocks and `${{ secrets.X }}`, `${{ env.X }}`, `${{ vars.X }}` |

Add `# envlens:ignore` (or `// envlens:ignore`) to a line to suppress a deliberate dynamic lookup.

---

## Architecture

```text
                        ┌──────────────────────┐
   source files ───────▶ │  scanner.py          │ ─┐
   workflows ──────────▶ │  workflow refs       │  │
                        └──────────────────────┘  │   ┌──────────────────┐   ┌──────────────┐
                                                  ├─▶ │  analysis.py     │ ─▶ │  render.py   │
   .env files ─────────▶ ┌──────────────────────┐  │   │  5 finding rules│   │ table/json   │
   compose/Dockerfile ─▶ │ envfiles.py /        │ ─┘   └──────────────────┘   │ markdown     │
                        │ manifests.py         │            │                └──────────────┘
                        └──────────────────────┘            ▼
                                                   ┌──────────────────┐
                                                   │ cli.py exit code │
                                                   │ 0 clean / 1 issue│
                                                   └──────────────────┘
```

Design rules:

- **Standard library only at runtime** — `tomllib`, `re`, `pathlib`, `argparse`, `json`.
- **No network, no telemetry, no subprocesses** — safe to run on air-gapped CI and client infrastructure.
- **Streaming-friendly** — files are read line by line; memory stays flat even on large monorepos.
- **Deterministic** — findings sorted by severity → kind → name; identical input always yields identical output.
- **Fail-the-build policy** — `--fail-on {critical,high,medium,low,info,none}` (default `high`).

---

## Configuration

Optional `[tool.envlens]` section in `pyproject.toml`:

```toml
[tool.envlens]
exclude = ["fixtures", "generated"]   # extra directory names to skip
ignore = ["NODE_ENV", "PORT"]         # variables known to be intentionally dynamic
```

Default excludes include `.git`, `.venv`, `node_modules`, `__pycache__`, `dist`, `build` and more.

---

## Use in GitHub Actions

```yaml
name: config-check
on: [push, pull_request]
jobs:
  envlens:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv tool install envlens
      - run: envlens scan . --format markdown >> "$GITHUB_STEP_SUMMARY"
      - run: envlens scan . --fail-on high
```

The first scan writes a Markdown report to the job summary; the second enforces the policy.

---

## Development

```bash
uv venv --python 3.12
uv sync
.venv/bin/python -m pytest
uvx ruff check src tests
uvx ruff format --check src tests
uvx semgrep scan --config p/python --config p/secrets --metrics off --error src
```

---

## Roadmap

- [x] 10+ language pattern support
- [x] Compose / Dockerfile / Actions parsers
- [x] Secret entropy heuristics
- [x] Safe `.env.example` sync
- [x] JSON + Markdown reporters
- [ ] Terraform / Helm value parsers
- [ ] `.gitignore` cross-check (is every real env file ignored?)
- [ ] Pre-commit hook distribution

---

## Security & privacy

`envlens` never prints real secret values — only variable names, locations and a generic explanation. It reads local files only, performs no DNS/HTTP calls, and is safe for regulated environments (KVKK/GDPR friendly). Report security issues privately via GitHub Security Advisories.

---

## License

MIT © [Baysoz Yazilim](https://github.com/yazilimbaysoz-svg)

<p align="center">Built with <span style="color:#4ade80">zero runtime dependencies</span> for developers who hate 3 a.m. config incidents.</p>
