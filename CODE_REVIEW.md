# CODE REVIEW

## Code style conventions

- Language & runtime: Python 3.11
- Format & lint (configured in `pyproject.toml`):
  - Black: line-length = 100, target-version = py311
  - Ruff: enable rule groups E/W (PEP8), F (Pyflakes), I (isort), B (bugbear), UP (pyupgrade)
  - isort: profile = black, line_length = 100
  - mypy: `ignore_missing_imports = true`, `python_version = "3.11"`
- Running style checks (Windows PowerShell):
  - Install dev tools (once):
    ```bash
    pip install -e '.\[dev]'
    ```
  - Auto-fix & check:
    ```bash
    ruff check . --fix
    black .
    isort .
    mypy services
    ```
- Additional guidelines:
  - File/folder names: snake_case; class names: PascalCase; variable/function names: snake_case.
  - Keep endpoints small; place core logic in `logic/`, schemas in `schemas/`, routers in `routers/`.
  - Short docstrings focusing on inputs/outputs and key side effects.
  - Do not commit secrets (.env is ignored). Use `config.py` or environment variables.

## Testing & CI

- Unit tests (pytest):
  - Tests run offline without servers: LLM layer stubs/patches LangChain; Gateway mocks `httpx.AsyncClient`.
  - Run all:
    ```bash
    pytest -q
    ```
  - Run a single file/test:
    ```bash
    pytest tests/test_llm_service.py -q
    pytest -q -k "change_time_full_exec"
    ```
- Optional coverage:
  - Add `coverage` and run:
    ```bash
    pip install coverage
    coverage run -m pytest -q; coverage html
    ```
- CI (GitHub Actions suggestion):
  - Create `.github/workflows/ci.yml` like:
    ```yaml
    name: CI
    on: [push, pull_request]
    jobs:
      build:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: '3.11'
          - name: Install
            run: |
              python -m pip install -U pip
              pip install -e '.[dev]'
          - name: Lint
            run: |
              ruff check .
              black --check .
              isort --check-only .
          - name: Type check (mypy)
            run: mypy services
          - name: Tests
            run: pytest -q
    ```

## Pre-merge review checklist

- [ ] Style checks pass: `ruff check .` and `black --check .` / `isort --check-only .`.
- [ ] No unused imports; no mixed tabs/spaces; line length ≤ 100.
- [ ] Endpoints in `routers/`, schemas in `schemas/`, logic in `logic/`.
- [ ] No real network calls in unit tests (must mock).
- [ ] No secrets committed; config via `config.py`/env; README updated for public behavior changes.
- [ ] New tests cover happy path and 1–2 edge cases.

## Current limitations

- Data Service is in-memory (no persistence); `/orders/query_time` is missing (tool `query_ticket_time` would 404 if called live). However, this is mocking layer, in production this layer should be functional from the beginning.
- No auth/rate limiting; Gateway has basic timeout handling but no retry/circuit breaker.
- No load balancing.
- Planner prompt is long and brittle; JSON parsing from LLM needs better guards/tests.
- RAG FAQ loads embeddings/FAISS at startup; no caching/resource coordination.
- No tests yet for FAQ streaming and cross-service e2e flows.
- Ruff deprecation warning: move `per-file-ignores` to `tool.ruff.lint.per-file-ignores` (to be migrated).

## Future work

- Security & observability: API key/JWT in Gateway & LLM; structured logging; metrics (Prometheus) and tracing (OTel).
- Resilience: retries with backoff for internal HTTP; circuit breaker; per-endpoint timeouts.
- Performance: caching (Redis) for RAG/LLM results; embeddings warmup; Docker + Compose.
- Quality: increase test coverage; add contract tests between services; test streaming; add CI as suggested.
- LLM manipulation ability: Langgraph should be consider for better flow conditioning, instead of if-else.
- Architecture: 12-factor ENV config; standardize response schemas; API versioning; modularize tool-calling.

