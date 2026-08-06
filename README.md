# TestForge

AI-powered pytest unit test generation with Docker sandboxing and
deterministic coverage-mutation feedback.

## What TestForge Does

Given a Python target module, TestForge:
1. Establishes pytest, branch coverage, and mutation testing baselines
2. Generates candidate unit tests via LLM
3. Evaluates quality through a deterministic gate (test count,
   metric regression, mutation kills, coverage delta)
4. Provides structured feedback for the next generation attempt
5. Pauses for human approval before applying patches to real repos

## Install from PyPI

```bash
pip install testforge-harness
```

## Initialize a Trusted Project

```bash
testforge init /path/to/project
```

You will be prompted to confirm trust — the build may download
dependencies and execute the project's build backend.

## Configure Credentials Safely

Credentials are stored in your OS keyring:

```bash
testforge credentials set openai
testforge credentials status openai
testforge credentials clear openai
```

Environment variable fallback requires explicit opt-in
(`OPENAI_API_KEY` is NOT automatically read).

## Run the CLI

```bash
testforge run src/your_module.py
testforge status <task-id>
testforge approve <approval-id>
testforge history <task-id>
```

## Run the Local WebUI

```bash
testforge serve
# Open http://localhost:8000
```

The WebUI shows task timelines, metrics, pending approvals, and
credential status — operating only on trusted local repositories.

## Public Mock Demo

A read-only demo mode shows the core feedback loop without
executing code or requiring credentials:

```bash
# Start in demo mode:
uvicorn testforge.web.app:create_app --factory --host 0.0.0.0 --port 8000

# POST to /demo/tasks with {"scenario": "weak-then-strong"}
# The demo accepts only pre-defined scenario names — no URLs, no keys.
```

## Docker Distribution

```bash
docker build -t testforge:local .
docker run -p 8000:8000 testforge:local
```

## Testing and Mechanism Demo

```bash
# One-command test suite:
python -m pytest tests/unit tests/integration/test_mock_loop.py tests/e2e -m "not docker"

# Deterministic mechanism demonstration:
python scripts/mechanism_demo.py
```

## Security Boundaries

- **Docker isolation**: generated tests run as non-root (65532:65532),
  network-disabled, read-only filesystem, all capabilities dropped
- **Credential storage**: OS keyring first, dotenv opt-in only;
  secrets never appear in logs, status output, or Git
- **Human approval**: all repository mutations require UUID-validated
  approval before application
- **Demo mode**: no external code, no repository URLs, no credentials,
  no network access

## Directory Structure

```
src/testforge/         # Application source
  domain/              # Domain models and state machine
  feedback/            # Quality gate and feedback engine
  governance/          # Policy enforcement and approvals
  llm/                 # LLM protocol and OpenAI adapter
  memory/              # Structured project memory
  persistence/         # SQLite repository
  sandbox/             # Docker image building and execution
  tools/               # Parsers, results, and tool dispatcher
  web/                 # FastAPI WebUI
  credentials.py       # Credential store
  engine.py            # Agent engine
  context.py           # LLM context builder
  application.py       # Composition root
  cli.py               # Typer CLI
  demo.py              # Public demo mode
docs/                  # Design documents
scripts/               # Mechanism demo
docker/                # Dockerfile template
```

## Supported Platforms and Prerequisites

- Python 3.11+
- Docker (for sandbox execution)
- OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- pip, pytest, coverage, mutmut

## Known Limitations

- Mutation testing requires a Unix-like environment (Linux/macOS/WSL2)
- Docker-dependent tests are skipped when the daemon is unavailable
- SECRET_PATTERN currently matches `sk-*` format only; expandable

## Third-Party Licenses

See [LICENSES.md](LICENSES.md).
