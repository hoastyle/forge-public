#!/usr/bin/env bash
# generate-index.sh - Auto-generate knowledge base index from YAML frontmatter
# Usage: ./automation/scripts/generate-index.sh

set -eu
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/../..")"

INDEX_FILE="INDEX.md"
TODAY=$(date +%Y-%m-%d)

# Extract a frontmatter field value from a file
fm_field() {
    local file="$1" field="$2"
    sed -n '/^---$/,/^---$/p' "$file" 2>/dev/null \
        | grep -m1 "^${field}:" \
        | sed "s/^${field}:[[:space:]]*//" \
        | sed 's/^"\(.*\)"$/\1/'
}

cat > "$INDEX_FILE" << 'HEADER'
# Experience Index

> Auto-generated. Do not edit manually.
> Run `./automation/scripts/generate-index.sh` to refresh.

HEADER

echo "**Last Updated**: $TODAY" >> "$INDEX_FILE"
echo "" >> "$INDEX_FILE"

# --- Knowledge ---
echo "## Knowledge" >> "$INDEX_FILE"
echo "" >> "$INDEX_FILE"

for category in knowledge/*/; do
    cat_name=$(basename "$category")
    files=$(find "$category" -name '*.md' -type f 2>/dev/null | sort)
    if [ -z "$files" ]; then continue; fi

    echo "### ${cat_name}" >> "$INDEX_FILE"
    echo "" >> "$INDEX_FILE"
    echo "| Document | Tags | Status | Updated |" >> "$INDEX_FILE"
    echo "|----------|------|--------|---------|" >> "$INDEX_FILE"

    while IFS= read -r f; do
        title=$(fm_field "$f" "title")
        tags=$(fm_field "$f" "tags")
        status=$(fm_field "$f" "status")
        updated=$(fm_field "$f" "updated")
        [ -z "$title" ] && title=$(basename "$f" .md)
        [ -z "$tags" ] && tags="-"
        [ -z "$status" ] && status="-"
        [ -z "$updated" ] && updated="-"
        echo "| [${title}](${f}) | ${tags} | ${status} | ${updated} |" >> "$INDEX_FILE"
    done <<< "$files"
    echo "" >> "$INDEX_FILE"
done

# --- Raw Captures ---
raw_files=$(find raw/ -name '*.md' -type f 2>/dev/null | sort)
if [ -n "$raw_files" ]; then
    echo "## Raw Captures" >> "$INDEX_FILE"
    echo "" >> "$INDEX_FILE"
    echo "| Document | Tags | Source | Created |" >> "$INDEX_FILE"
    echo "|----------|------|--------|---------|" >> "$INDEX_FILE"
    while IFS= read -r f; do
        title=$(fm_field "$f" "title")
        tags=$(fm_field "$f" "tags")
        source=$(fm_field "$f" "source")
        created=$(fm_field "$f" "created")
        [ -z "$title" ] && title=$(basename "$f" .md)
        [ -z "$tags" ] && tags="-"
        [ -z "$source" ] && source="-"
        [ -z "$created" ] && created="-"
        echo "| [${title}](${f}) | ${tags} | ${source} | ${created} |" >> "$INDEX_FILE"
    done <<< "$raw_files"
    echo "" >> "$INDEX_FILE"
fi

# --- Insights ---
insight_files=$(find insights/ -name '*.md' -type f 2>/dev/null | sort)
if [ -n "$insight_files" ]; then
    echo "## Insights" >> "$INDEX_FILE"
    echo "" >> "$INDEX_FILE"
    echo "| Insight | Tags | Impact | Status |" >> "$INDEX_FILE"
    echo "|---------|------|--------|--------|" >> "$INDEX_FILE"
    while IFS= read -r f; do
        title=$(fm_field "$f" "title")
        tags=$(fm_field "$f" "tags")
        impact=$(fm_field "$f" "impact")
        status=$(fm_field "$f" "status")
        [ -z "$title" ] && title=$(basename "$f" .md)
        [ -z "$tags" ] && tags="-"
        [ -z "$impact" ] && impact="-"
        [ -z "$status" ] && status="-"
        echo "| [${title}](${f}) | ${tags} | ${impact} | ${status} |" >> "$INDEX_FILE"
    done <<< "$insight_files"
    echo "" >> "$INDEX_FILE"
fi

# --- Stats ---
total_knowledge=$(find knowledge/ -name '*.md' -type f 2>/dev/null | wc -l)
total_raw=$(find raw/ -name '*.md' -type f 2>/dev/null | wc -l)
total_insights=$(find insights/ -name '*.md' -type f 2>/dev/null | wc -l)

echo "## Stats" >> "$INDEX_FILE"
echo "" >> "$INDEX_FILE"
echo "| Layer | Count |" >> "$INDEX_FILE"
echo "|-------|-------|" >> "$INDEX_FILE"
echo "| Knowledge | ${total_knowledge} |" >> "$INDEX_FILE"
echo "| Raw Captures | ${total_raw} |" >> "$INDEX_FILE"
echo "| Insights | ${total_insights} |" >> "$INDEX_FILE"
echo "| **Total** | **$((total_knowledge + total_raw + total_insights))** |" >> "$INDEX_FILE"

echo "Index generated: ${INDEX_FILE} (${total_knowledge} knowledge, ${total_raw} raw, ${total_insights} insights)"
