#!/usr/bin/env bash
# validate-provenance.sh - Enforce raw -> knowledge -> insights provenance rules
# Usage: ./automation/scripts/validate-provenance.sh

set -eu
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo "$(dirname "$0")/../..")"

errors=0
checked=0

trim() {
    printf '%s' "$1" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

report_error() {
    local file="$1" message="$2"
    echo "ERROR [$file] $message"
    errors=$((errors + 1))
}

has_frontmatter() {
    awk '
        NR == 1 && /^---$/ { start = 1; next }
        start && /^---$/ { end = 1; exit }
        END { exit !(start && end) }
    ' "$1"
}

fm_scalar() {
    local file="$1" field="$2" value
    value=$(
        sed -n '/^---$/,/^---$/p' "$file" \
            | grep -m1 "^${field}:" \
            | sed "s/^${field}:[[:space:]]*//" \
            || true
    )
    trim "$value"
}

fm_list_items() {
    local file="$1" field="$2" raw inner
    raw=$(fm_scalar "$file" "$field")
    raw=$(trim "$raw")

    if [ -z "$raw" ]; then
        return 0
    fi

    case "$raw" in
        \[*\])
            inner=$(printf '%s' "$raw" | sed 's/^\[//; s/\]$//')
            if [ -z "$(trim "$inner")" ]; then
                return 0
            fi
            printf '%s\n' "$inner" \
                | tr ',' '\n' \
                | sed "s/^[[:space:]]*//; s/[[:space:]]*$//; s/^'//; s/'$//; s/^\"//; s/\"$//"
            ;;
        *)
            printf '__INVALID_LIST__:%s\n' "$raw"
            ;;
    esac
}

is_allowed_status() {
    case "$1" in
        draft|hypothesis|active|superseded|archived) return 0 ;;
        *) return 1 ;;
    esac
}

validate_common_fields() {
    local file="$1" title created updated tags status tag_items

    title=$(fm_scalar "$file" "title")
    created=$(fm_scalar "$file" "created")
    updated=$(fm_scalar "$file" "updated")
    tags=$(fm_scalar "$file" "tags")
    status=$(fm_scalar "$file" "status")

    [ -n "$title" ] || report_error "$file" "missing frontmatter field: title"
    [ -n "$created" ] || report_error "$file" "missing frontmatter field: created"
    [ -n "$updated" ] || report_error "$file" "missing frontmatter field: updated"
    [ -n "$tags" ] || report_error "$file" "missing frontmatter field: tags"
    [ -n "$status" ] || report_error "$file" "missing frontmatter field: status"

    if [ -n "$created" ] && ! printf '%s\n' "$created" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
        report_error "$file" "created must use YYYY-MM-DD"
    fi

    if [ -n "$updated" ] && ! printf '%s\n' "$updated" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
        report_error "$file" "updated must use YYYY-MM-DD"
    fi

    if [ -n "$status" ] && ! is_allowed_status "$status"; then
        report_error "$file" "status must be one of: draft, hypothesis, active, superseded, archived"
    fi

    if [ -n "$tags" ]; then
        tag_items=$(fm_list_items "$file" "tags")
        if printf '%s\n' "$tag_items" | grep -q '^__INVALID_LIST__:'; then
            report_error "$file" "tags must use single-line YAML list syntax: [a, b]"
        fi
    fi
}

validate_raw_file() {
    local file="$1" status source

    status=$(fm_scalar "$file" "status")
    source=$(fm_scalar "$file" "source")

    if [ "$status" != "draft" ] && [ -z "$source" ]; then
        report_error "$file" "raw document with non-draft status must fill source"
    fi
}

validate_knowledge_file() {
    local file="$1" reuse_count derived_items count ref raw_source raw_status

    reuse_count=$(fm_scalar "$file" "reuse_count")
    if [ -z "$reuse_count" ]; then
        report_error "$file" "knowledge document must define reuse_count"
    elif ! printf '%s\n' "$reuse_count" | grep -Eq '^[0-9]+$'; then
        report_error "$file" "reuse_count must be a non-negative integer"
    fi

    derived_items=$(fm_list_items "$file" "derived_from")
    if [ -z "$derived_items" ]; then
        report_error "$file" "knowledge document must define derived_from with at least one raw source"
        return
    fi

    if printf '%s\n' "$derived_items" | grep -q '^__INVALID_LIST__:'; then
        report_error "$file" "derived_from must use single-line YAML list syntax: [raw/...md]"
        return
    fi

    count=0
    while IFS= read -r ref; do
        [ -n "$ref" ] || continue
        count=$((count + 1))

        if [[ "$ref" != raw/* ]]; then
            report_error "$file" "derived_from entry must point to raw/: $ref"
            continue
        fi

        if [ ! -f "$ref" ]; then
            report_error "$file" "derived_from target does not exist: $ref"
            continue
        fi

        raw_source=$(fm_scalar "$ref" "source")
        raw_status=$(fm_scalar "$ref" "status")

        if [ -z "$raw_source" ]; then
            report_error "$file" "derived raw document must fill source: $ref"
        fi

        if [ "$raw_status" = "draft" ]; then
            report_error "$file" "knowledge cannot derive from draft raw document: $ref"
        fi
    done <<EOF
$derived_items
EOF

    if [ "$count" -eq 0 ]; then
        report_error "$file" "knowledge document must define derived_from with at least one raw source"
    fi
}

validate_insight_file() {
    local file="$1" status impact evidence_items count ref knowledge_status

    status=$(fm_scalar "$file" "status")
    impact=$(fm_scalar "$file" "impact")
    evidence_items=$(fm_list_items "$file" "evidence")

    if [ -n "$evidence_items" ] && printf '%s\n' "$evidence_items" | grep -q '^__INVALID_LIST__:'; then
        report_error "$file" "evidence must use single-line YAML list syntax: [knowledge/...md]"
        return
    fi

    count=0
    while IFS= read -r ref; do
        [ -n "$ref" ] || continue
        count=$((count + 1))

        if [[ "$ref" != knowledge/* ]]; then
            report_error "$file" "evidence entry must point to knowledge/: $ref"
            continue
        fi

        if [ ! -f "$ref" ]; then
            report_error "$file" "evidence target does not exist: $ref"
            continue
        fi

        knowledge_status=$(fm_scalar "$ref" "status")
        if [ "$knowledge_status" = "draft" ]; then
            report_error "$file" "insight cannot cite draft knowledge document: $ref"
        fi
    done <<EOF
$evidence_items
EOF

    if [ "$status" != "draft" ]; then
        [ -n "$impact" ] || report_error "$file" "non-draft insight must fill impact"

        if [ "$count" -lt 2 ]; then
            report_error "$file" "non-draft insight must cite at least two knowledge documents in evidence"
        fi
    fi
}

validate_file() {
    local file="$1"

    checked=$((checked + 1))

    if ! has_frontmatter "$file"; then
        report_error "$file" "missing YAML frontmatter"
        return
    fi

    validate_common_fields "$file"

    case "$file" in
        raw/*) validate_raw_file "$file" ;;
        knowledge/*) validate_knowledge_file "$file" ;;
        insights/*) validate_insight_file "$file" ;;
        *) ;;
    esac
}

while IFS= read -r file; do
    [ -n "$file" ] || continue
    validate_file "$file"
done < <(find raw knowledge insights -name '*.md' -type f | sort)

if [ "$errors" -gt 0 ]; then
    echo "Provenance validation failed: $errors error(s) across $checked file(s)."
    exit 1
fi

echo "Provenance validation passed: $checked file(s) checked."
