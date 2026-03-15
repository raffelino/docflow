# Skill: e2e-health

Run the DocFlow E2E test suite, report pass/fail status, and extract actionable error summaries.

## Trigger

Run weekly (Monday 09:00 local time) or on demand when tests are suspected broken.

## Steps

### 1. Navigate to project root

```bash
cd /path/to/docflow
```

### 2. Ensure dependencies are installed

```bash
uv sync --dev
```

### 3. Run E2E tests

```bash
uv run pytest -m e2e -v --tb=short 2>&1 | tee /tmp/docflow_e2e_results.txt
```

### 4. Parse results

Extract:
- Total tests run
- Number passed / failed / errored / skipped
- For each failure: test name + short traceback
- Exit code (0 = all pass, non-zero = failures)

### 5. Report

**If all pass:**
```
✅ DocFlow E2E Health: All N tests passed.
```

**If failures exist:**
```
❌ DocFlow E2E Health: X/N tests failed.

Failed tests:
- test_e2e_photos.py::TestE2EPhotoPipeline::test_full_photo_pipeline
  AssertionError: Expected PDF at /tmp/.../2026/03/... (file not found)

- test_e2e_storage.py::TestE2ES3Storage::test_save_to_s3_moto
  ImportError: moto not installed

Action needed: review failures above and open GitHub issues if not transient.
```

### 6. On failures — escalate

If any test fails:
1. Check if it's a dependency issue (missing `moto`, `pdfplumber`, etc.) — suggest `uv add <pkg>`
2. Check if it's a code regression — open a GitHub issue with the failure log
3. If on macOS and Vision-related: expected on CI, skip unless running locally

## Notes

- E2E tests use real SQLite + real file I/O. Only external APIs are mocked.
- S3 tests require `moto` (`uv add moto`).
- Run `uv run pytest -m unit -v` first if E2E setup seems broken.
- Reference: `CLAUDE.md` → "Testing Strategy"
