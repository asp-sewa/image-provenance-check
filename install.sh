#!/usr/bin/env bash
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
for d in "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.gemini/skills"; do
  mkdir -p "$d"; rm -rf "$d/image-provenance-check"; cp -r "$SRC" "$d/image-provenance-check"; echo "installed -> $d/image-provenance-check"
done
python3 -c "import PIL" 2>/dev/null || echo "NOTE: pip install pillow"
