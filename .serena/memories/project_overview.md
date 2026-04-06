# Forge - Personal Evolution Engine

## Project Vision
Forge is a personal evolution engine that follows the cycle:
`Collect → Distill → Discover Patterns → Generate Insights → Drive Action → Verify → Feedback`

## Three-Layer Knowledge Structure

### Layer 1: Raw (`raw/`)
- Purpose: Quick capture with low barrier
- Subdirectories: `captures/`, `experiments/`, `references/`
- Naming: Date prefix `2026-04-02-*.md`
- Required frontmatter: `source` must be filled before promotion

### Layer 2: Knowledge (`knowledge/`)
- Purpose: Distilled, reusable knowledge
- Categories: `troubleshooting/`, `architecture/`, `tools/`, `workflow/`, `best-practices/`
- Naming: Descriptive, e.g., `ssh-password-auth-diagnosis.md`
- Required frontmatter: `derived_from` pointing to raw sources

### Layer 3: Insights (`insights/`)
- Purpose: Pattern discovery and innovation
- Categories: `patterns/`, `innovations/`, `retrospectives/`
- Required frontmatter: `evidence` (min 2 knowledge articles for non-draft), `impact`

## Frontmatter Standards
All documents use YAML frontmatter with:
- `title`: Document title
- `created`: Creation date (set once, never modify)
- `updated`: Last update date (auto-update on edits)
- `tags`: Single-line YAML list, lowercase, kebab-case
- `status`: `draft` | `hypothesis` | `active` | `superseded` | `archived`
- Layer-specific: `source` (raw), `derived_from` (knowledge), `evidence` + `impact` (insights)

## Key Commands
- `./automation/scripts/validate-provenance.sh` - Validate provenance chains
- `./automation/scripts/generate-index.sh` - Regenerate INDEX.md
- `./automation/scripts/quick-capture.sh` - Quick capture template
- `./automation/scripts/extract-tags.sh` - Tag extraction

## Project Context
- **Path**: /home/hao/Workspace/Forge
- **Language**: Chinese interaction, English code
- **Branch**: master
- **Date Format**: Always use `$(date +%Y-%m-%d)` - never manual dates

## Current Status
- Phase 0: Foundation (complete)
- Moving to Phase 1: Systematic Collection
- Knowledge: 5 articles
- Raw Captures: 6 articles
- Insights: 0 articles
