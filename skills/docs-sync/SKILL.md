# Skill: docs-sync

Verify that DocFlow's documentation stays in sync with its actual code structure.

## Trigger

Run weekly, or after any PR that adds/removes modules, config options, or public APIs.

## Steps

### 1. Check CLAUDE.md module table matches actual modules

List actual modules:
```bash
find src/docflow -name "*.py" | sort
```

Compare against the module table in `CLAUDE.md`. Flag any module present in code but missing from docs, or documented but deleted.

**Expected modules (as of v0.1.0):**
- `config.py`, `db.py`, `ocr.py`, `photos.py`, `email_source.py`, `pipeline.py`, `scheduler.py`
- `llm/__init__.py`, `llm/base.py`, `llm/anthropic.py`, `llm/ollama.py`, `llm/openrouter.py`
- `storage/__init__.py`, `storage/base.py`, `storage/local.py`, `storage/icloud.py`, `storage/generic_cloud.py`
- `web/__init__.py`, `web/app.py`, `web/routes.py`
- `web/templates/base.html`, `web/templates/index.html`, `web/templates/documents.html`, `web/templates/run_detail.html`

### 2. Check README covers all .env.example options

```bash
grep "^[A-Z_]*=" .env.example | cut -d= -f1
```

For each variable, verify it appears in `README.md` (in the configuration table). Flag any missing.

### 3. Check .env.example is complete

```bash
grep "^[A-Z_]*=" .env.example | cut -d= -f1 | sort
```

Compare against `config.py` fields. Fields in Settings but not in `.env.example` should be added.

### 4. Check CHANGELOG.md is up to date

- `## [Unreleased]` section should exist
- Latest tagged version should have an entry
- Check `git log --oneline v0.1.0..HEAD` for commits not yet documented

### 5. Check docstrings on public classes/functions

```bash
uv run python -c "
import ast, sys
from pathlib import Path
issues = []
for p in Path('src/docflow').rglob('*.py'):
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not (ast.get_docstring(node)) and not node.name.startswith('_'):
                issues.append(f'{p}:{node.lineno} {node.name}')
for i in issues[:20]:
    print(i)
"
```

Flag public functions/classes without docstrings.

### 6. Report

```
# DocFlow Docs Sync Report — YYYY-MM-DD

## Module Coverage
✅ All modules documented in CLAUDE.md  /  ❌ Missing: [list]

## README Config Coverage
✅ All .env variables documented  /  ❌ Missing: [list]

## .env.example Completeness
✅ All config fields present  /  ❌ Missing: [list]

## CHANGELOG Status
✅ Up to date  /  ⚠️ X commits since last entry

## Docstring Coverage
✅ All public APIs documented  /  ⚠️ X missing docstrings

## Actions needed:
1. ...
```

## Notes

- CLAUDE.md is the authoritative architecture reference — keep it current
- `.env.example` must always have a line for every `Settings` field with a non-secret default
- Never document internal `_private` functions
