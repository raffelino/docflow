#!/usr/bin/env bash
# DocFlow bootstrap: copy to /tmp/docflow, install deps, run tests, push to GitHub
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="/tmp/docflow"

echo "=== DocFlow Bootstrap ==="
echo ""

# ── 1. Copy files ─────────────────────────────────────────────────────────────
echo "1. Copying project to $TARGET..."
rm -rf "$TARGET"
cp -r "$SCRIPT_DIR" "$TARGET"
cd "$TARGET"

# ── 2. Check tools ────────────────────────────────────────────────────────────
echo ""
echo "2. Checking tools..."

if ! command -v uv &>/dev/null; then
    echo "ERROR: uv not found. Install with: brew install uv"
    exit 1
fi
echo "   uv: $(uv --version)"
echo "   python: $(uv python find 3.11 2>/dev/null || echo 'will be installed')"

# ── 3. Install deps ───────────────────────────────────────────────────────────
echo ""
echo "3. Installing dependencies..."
uv sync --dev

# ── 4. Unit tests ─────────────────────────────────────────────────────────────
echo ""
echo "4. Running unit tests..."
if ! uv run pytest -m unit -v --tb=short; then
    echo ""
    echo "ERROR: Unit tests failed. Fix failures before continuing."
    exit 1
fi
echo "   ✅ Unit tests passed"

# ── 5. E2E tests ──────────────────────────────────────────────────────────────
echo ""
echo "5. Running E2E tests..."
if ! uv run pytest -m e2e -v --tb=short; then
    echo ""
    echo "ERROR: E2E tests failed. Fix failures before continuing."
    exit 1
fi
echo "   ✅ E2E tests passed"

# ── 6. Git init ───────────────────────────────────────────────────────────────
echo ""
echo "6. Initializing git repository..."
git init -b main
git add -A
git commit -m "feat: initial release of DocFlow v0.1.0"
echo "   ✅ Git commit done"

# ── 7. GitHub repo ────────────────────────────────────────────────────────────
echo ""
echo "7. Creating GitHub repository..."

if ! command -v gh &>/dev/null; then
    echo "   WARNING: gh CLI not found. Install with: brew install gh"
    echo "   To push manually:"
    echo "     cd $TARGET"
    echo "     gh repo create docflow --public --description 'Automated document scanning, tagging and archiving for macOS' --source=. --remote=origin --push"
    exit 0
fi

if ! gh auth status &>/dev/null; then
    echo "   WARNING: gh CLI not authenticated. Run: gh auth login"
    echo "   Then run from $TARGET:"
    echo "     gh repo create docflow --public --description 'Automated document scanning, tagging and archiving for macOS' --source=. --remote=origin --push"
    exit 0
fi

gh repo create docflow \
    --public \
    --description "Automated document scanning, tagging and archiving for macOS" \
    --source=. \
    --remote=origin \
    --push

REPO_URL=$(gh repo view --json url -q .url)
echo ""
echo "=== ✅ All done ==="
echo ""
echo "   Repo: $REPO_URL"
echo "   Tests: all green"
echo "   Start server: cd $TARGET && uv run python -m docflow"
