# Skill: security-audit

Run security checks on DocFlow: dependency vulnerabilities, static analysis, and secret scanning.

## Trigger

Run monthly (1st of each month) or before any public release.

## Steps

### 1. Install audit tools

```bash
uv add --dev pip-audit bandit
```

### 2. Dependency vulnerability scan (pip-audit)

```bash
uv run pip-audit 2>&1 | tee /tmp/docflow_pip_audit.txt
```

Look for:
- `Found X known vulnerabilities`
- CVE numbers and severity
- Affected packages

### 3. Static security analysis (bandit)

```bash
uv run bandit -r src/ -f json -o /tmp/docflow_bandit.json 2>&1
uv run bandit -r src/ --severity-level medium 2>&1 | tee /tmp/docflow_bandit.txt
```

Look for:
- HIGH severity issues
- MEDIUM severity issues (especially in email/IMAP handling, subprocess usage)
- Issues in `email_source.py`, `ocr.py`, `storage/generic_cloud.py`

### 4. Hardcoded secrets check

Search for patterns that should never be committed:

```bash
grep -rn "api_key\s*=\s*['\"][a-zA-Z0-9]" src/ tests/
grep -rn "password\s*=\s*['\"][^{]" src/ tests/
grep -rn "sk-[a-zA-Z0-9]" src/ tests/
grep -rn "AKIA[A-Z0-9]" src/ tests/  # AWS key pattern
```

Also check `.env` is in `.gitignore`:
```bash
grep "^\.env$" .gitignore || echo "WARNING: .env not in .gitignore!"
```

### 5. Produce structured report

```
# DocFlow Security Audit — YYYY-MM-DD

## Dependency Vulnerabilities (pip-audit)
[PASS / X vulnerabilities found]
- CVE-XXXX-XXXX in package==version: description

## Static Analysis (bandit)
[PASS / X issues found]
HIGH:
- src/docflow/email_source.py:45: B601 - shell injection risk

MEDIUM:
- (none)

## Hardcoded Secrets
[PASS / FAIL]

## Recommendations
1. Upgrade <package> to <version> to fix CVE-XXXX
2. ...

## Status: ✅ CLEAN / ⚠️ ACTION REQUIRED
```

### 6. On critical findings

- CRITICAL/HIGH CVE: open GitHub issue immediately, consider yanking release
- Hardcoded secret: rotate immediately, rewrite git history if pushed
- HIGH bandit: file issue, fix before next release

## Notes

- False positives in bandit are common for IMAP/SSL code — review in context
- `src/docflow/storage/generic_cloud.py` uses boto3 — check for IAM issues
- Reference: `CLAUDE.md` → "Known Limitations"
- CI also runs security checks: see `.github/workflows/security.yml`
