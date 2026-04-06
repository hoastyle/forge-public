#!/usr/bin/env bash
# extract-tags.sh - Extract and list all tags from YAML frontmatter
# Usage: ./automation/scripts/extract-tags.sh

set -eu
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/../..")"

echo "=== Tag Frequency ==="
echo ""

# Extract tags from YAML frontmatter
find raw/ knowledge/ insights/ -name '*.md' -type f 2>/dev/null | while read -r f; do
    sed -n '/^---$/,/^---$/p' "$f" 2>/dev/null \
        | grep -m1 '^tags:' \
        | sed 's/^tags:[[:space:]]*//' \
        | tr -d '[]' \
        | tr ',' '\n' \
        | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
done | grep -v '^$' | sort | uniq -c | sort -rn

echo ""
echo "=== Documents Without Tags ==="
echo ""

find raw/ knowledge/ insights/ -name '*.md' -type f 2>/dev/null | while read -r f; do
    has_fm=$(sed -n '1{/^---$/p}' "$f" 2>/dev/null)
    if [ -z "$has_fm" ]; then
        echo "  [no frontmatter] $f"
    else
        tags=$(sed -n '/^---$/,/^---$/p' "$f" 2>/dev/null | grep -m1 '^tags:' | sed 's/^tags:[[:space:]]*//')
        if [ -z "$tags" ] || [ "$tags" = "[]" ]; then
            echo "  [empty tags]     $f"
        fi
    fi
done
