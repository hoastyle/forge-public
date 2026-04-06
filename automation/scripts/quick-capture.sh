#!/usr/bin/env bash
# quick-capture.sh - Fast knowledge capture with YAML frontmatter
# Usage: ./automation/scripts/quick-capture.sh "title" [tags]
#
# Examples:
#   ./automation/scripts/quick-capture.sh "docker network gotcha"
#   ./automation/scripts/quick-capture.sh "nginx proxy timeout" "nginx,proxy,timeout"

set -eu
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/../..")"

TITLE="${1:?Usage: quick-capture.sh \"title\" [tags]}"
RAW_TAGS="${2:-}"
TODAY=$(date +%Y-%m-%d)
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')
FILENAME="raw/captures/${TODAY}-${SLUG}.md"

if [ -f "$FILENAME" ]; then
    echo "File already exists: $FILENAME"
    ${EDITOR:-vim} "$FILENAME"
    exit 0
fi

# Format tags as YAML list
if [ -n "$RAW_TAGS" ]; then
    TAGS="[$(echo "$RAW_TAGS" | sed 's/,/, /g')]"
else
    TAGS="[]"
fi

cat > "$FILENAME" << EOF
---
title: ${TITLE}
created: ${TODAY}
updated: ${TODAY}
tags: ${TAGS}
status: draft
source:
---

# ${TITLE}

EOF

echo "Created: $FILENAME"

if [ -n "${EDITOR:-}" ]; then
    "$EDITOR" "$FILENAME"
else
    echo "Edit with: vim $FILENAME"
fi
