# AGENTS.md — DocFlow Agent Guide

> For agentic systems (OpenClaw, Codex, Claude Code, etc.) maintaining this repo.

## Available Skills

| Skill | Directory | What it does | Schedule |
|---|---|---|---|
| **e2e-health** | `skills/e2e-health/` | Runs E2E test suite, reports pass/fail, extracts failing test errors | Weekly (Monday 09:00) |
| **security-audit** | `skills/security-audit/` | pip-audit + bandit scan, checks for hardcoded secrets | Monthly (1st of month) |
| **docs-sync** | `skills/docs-sync/` | Verifies CLAUDE.md matches module structure, README covers all .env options | On PR or weekly |
| **release** | `skills/release/` | Full release: tests → version bump → CHANGELOG → git tag → GitHub Release | On demand |

## Maintenance Schedule

```
Monday 09:00   →  e2e-health skill
1st of month   →  security-audit skill
Weekly         →  docs-sync skill (or after large PRs)
On demand      →  release skill (when shipping a version)
```

## Dev Commands (quick ref)

```bash
uv run pytest -m unit -v        # fast unit tests
uv run pytest -m e2e -v         # end-to-end tests (local only)
uv run pytest -v                # all tests
uv run python -m docflow        # start server + scheduler
uv run python scripts/run_once.py  # run pipeline once
uv run ruff check src/ tests/   # lint
uv run mypy src/docflow --ignore-missing-imports  # type check
```

## Key Files for Context

Always read before making changes:
- `CLAUDE.md` — full architecture + extension guide
- `src/docflow/config.py` — all settings
- `src/docflow/pipeline.py` — main orchestration
- `tests/conftest.py` — shared fixtures and mock helpers

## Adding Features

1. **New LLM**: see `CLAUDE.md` → "How to Add a New LLM Provider"
2. **New Storage**: see `CLAUDE.md` → "How to Add a New Storage Backend"
3. **Schema changes**: add migrations to `SCHEMA` in `db.py` + update `MIGRATIONS` list
4. **New config**: add field to `Settings` in `config.py`, document in `.env.example` and README

## Testing Rules

- All new code needs `@pytest.mark.unit` tests
- Pipeline/integration changes need `@pytest.mark.e2e` tests
- Never mock SQLite — use real DB in `tmp_dir`
- Always mock external APIs (Vision, LLM, IMAP, S3)
- See `tests/conftest.py` for shared fixtures

## Release Process

Use the `release` skill (see `skills/release/SKILL.md`) or:
1. `uv run pytest -v` — all green
2. Bump version in `pyproject.toml`
3. Add entry in `CHANGELOG.md` under `## [X.Y.Z]`
4. `git commit -m "chore: release vX.Y.Z"`
5. `git tag vX.Y.Z`
6. `git push origin main --tags`
7. GitHub Actions creates the release automatically
