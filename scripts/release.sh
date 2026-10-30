#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

VERSION="${1:-}"
echo "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$' || { echo "usage: scripts/release.sh X.Y.Z"; exit 1; }
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "release from main only"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "working tree not clean"; exit 1; }
git fetch -q --tags
if git rev-parse -q --verify "refs/tags/v$VERSION" >/dev/null; then echo "tag v$VERSION exists"; exit 1; fi
NOTES="$(awk '/^## \[Unreleased\]/{found=1; next} /^## \[/{found=0} found' CHANGELOG.md | sed '/^[[:space:]]*$/d')"
[ -n "$NOTES" ] || { echo "add notes under ## [Unreleased] in CHANGELOG.md first"; exit 1; }

uv version --no-sync "$VERSION" >/dev/null
python3 -I - "$VERSION" "$(date -u +%Y-%m-%d)" <<'PY'
import pathlib
import sys

version, today = sys.argv[1], sys.argv[2]
changelog = pathlib.Path("CHANGELOG.md")
changelog.write_text(changelog.read_text().replace("## [Unreleased]\n", f"## [Unreleased]\n\n## [{version}] - {today}\n", 1))
PY

git add pyproject.toml uv.lock CHANGELOG.md
git commit -q -m "chore(release): v$VERSION"
git tag -a "v$VERSION" -m "v$VERSION"
git push -q origin main "v$VERSION"
echo "pushed v$VERSION: the Release workflow publishes it to PyPI and GitHub"
