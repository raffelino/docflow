# Skill: release

Full release process for DocFlow: test → version bump → CHANGELOG → git commit → tag → push → GitHub Release.

## Prerequisites

- `gh` CLI installed and authenticated: `gh auth status`
- Clean working tree on `main` branch
- All tests passing

## Steps

### 1. Verify clean state

```bash
git status
git branch --show-current  # must be: main
git pull origin main
```

Abort if working tree is dirty or not on main.

### 2. Run full test suite

```bash
uv run pytest -v
```

All tests must pass. If any fail, stop and fix before releasing.

### 3. Determine new version

Read current version from `pyproject.toml`:
```bash
grep '^version = ' pyproject.toml
```

Choose new version following semver:
- **patch** (0.1.0 → 0.1.1): bug fixes only
- **minor** (0.1.0 → 0.2.0): new features, backward compatible
- **major** (0.1.0 → 1.0.0): breaking changes

### 4. Update version in pyproject.toml

Edit `pyproject.toml`:
```toml
version = "X.Y.Z"
```

Also update `src/docflow/__init__.py`:
```python
__version__ = "X.Y.Z"
```

### 5. Update CHANGELOG.md

Move content from `## [Unreleased]` to a new `## [X.Y.Z] — YYYY-MM-DD` section.
Add a fresh empty `## [Unreleased]` section at the top.

Format:
```markdown
## [Unreleased]

## [X.Y.Z] — YYYY-MM-DD

### Added
- Feature descriptions

### Fixed
- Bug fix descriptions

### Changed
- Breaking or notable changes
```

Use `git log --oneline vPREV..HEAD` to enumerate commits for the entry.

### 6. Commit and tag

```bash
git add pyproject.toml src/docflow/__init__.py CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
```

### 7. Push

```bash
git push origin main
git push origin vX.Y.Z
```

### 8. Create GitHub Release

```bash
gh release create vX.Y.Z \
  --title "DocFlow vX.Y.Z" \
  --notes-file <(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md | head -n -1)
```

Or extract release notes automatically:
```bash
VERSION="X.Y.Z"
NOTES=$(awk "/## \[$VERSION\]/,/## \[/" CHANGELOG.md | grep -v "## \[" | head -n -1)
gh release create "v$VERSION" --title "DocFlow v$VERSION" --notes "$NOTES"
```

### 9. Verify

```bash
gh release view vX.Y.Z
```

Confirm:
- Release exists on GitHub
- CI passes on the tag (check `gh run list`)

## Rollback

If something goes wrong after push:
```bash
git tag -d vX.Y.Z              # delete local tag
git push origin :refs/tags/vX.Y.Z  # delete remote tag
gh release delete vX.Y.Z --yes    # delete GitHub release
```

Then fix and re-release.

## Notes

- GitHub Actions (`.github/workflows/release.yml`) also creates a release on tag push — the `gh` step above is manual / backup
- Never release from a dirty working tree
- Always run tests first — no exceptions
- Reference: `AGENTS.md` → "Release Process"
