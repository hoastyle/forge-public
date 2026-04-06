# Forge Automation & Workflows

## Validation Scripts

### Provenance Validation
**Script**: `./automation/scripts/validate-provenance.sh`
**Purpose**: Ensures all knowledge/insights have valid source chains
**Checks**:
- Raw documents must have `source` field filled
- Knowledge documents must have `derived_from` pointing to existing raw files
- Insight documents must have `evidence` pointing to existing knowledge files
- Non-draft insights need ≥2 evidence sources

### Index Generation
**Script**: `./automation/scripts/generate-index.sh`
**Purpose**: Auto-generate INDEX.md from frontmatter
**Updates**: Last Updated timestamp, document listings with metadata

### Tag Extraction
**Script**: `./automation/scripts/extract-tags.sh`
**Purpose**: Extract and analyze tag usage patterns

### Quick Capture
**Script**: `./automation/scripts/quick-capture.sh`
**Purpose**: Create new raw capture with template

## Document Templates

Located in `automation/templates/`:
- `raw-capture.md` - Raw capture template
- `knowledge-article.md` - Knowledge article template  
- `insight.md` - Insight template

## Promotion Workflow

### Raw → Knowledge
1. Fill `source` field in raw document
2. Promote to `knowledge/` with descriptive name
3. Add `derived_from: [raw/path.md]` to frontmatter
4. Run `validate-provenance.sh`

### Knowledge → Insights
1. Identify cross-cutting patterns across ≥2 knowledge articles
2. Create insight in `insights/` with `evidence` list
3. Set `impact: high|medium|low`
4. Run `validate-provenance.sh`

## Quality Gates

### Before Commit
```bash
# Validate provenance
./automation/scripts/validate-provenance.sh

# Check trailing whitespace
git diff --cached --check

# Regenerate index
./automation/scripts/generate-index.sh
```

### Commit Message Format
- Format: `type(scope): summary`
- Types: `docs`, `feat`, `fix`, `refactor`, `chore`, `revert`
- Scopes: `raw`, `knowledge`, `insight`, `automation`, `config`
- Subject line: ≤100 characters
- Body: Required for multi-document or structural changes

## Time Management Rule
**CRITICAL**: Never manually input dates
```bash
TODAY=$(date +%Y-%m-%d)              # 2026-04-04
YESTERDAY=$(date -d 'yesterday' +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d\ %H:%M:%S)
TODAY_CN=$(date +%Y年%m月%d日)
```
- Historical dates (created): set once, never modify
- Maintenance dates (updated): auto-update on each edit
