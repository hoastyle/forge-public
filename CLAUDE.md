# CLAUDE.md

This file provides repository-local guidance to Claude Code when working in this repo.

## Repository Vision

**Experience** is a personal evolution engine, not just a knowledge base.

Core loop:

```
Collect → Distill → Discover Patterns → Generate Insights → Drive Action → Verify → Feedback
```

Each cycle makes both the system and the user stronger.

### Three Layers

1. **Collect** (`raw/`): Capture everything — solutions, experiments, ideas, failures, observations.
   Low barrier, high volume. Record first, organize later.
2. **Distill** (`knowledge/`): Refine raw input into reusable knowledge — best practices,
   lessons learned, architecture decisions, tool guides.
3. **Evolve** (`insights/`): Discover patterns across knowledge, generate new insights,
   drive innovation. This is where compound growth happens.

### Success Metrics

- **Reuse rate**: How often past knowledge prevents redundant work
- **Innovation output**: New ideas, methods, and tools generated
- **Personal growth**: Measurable capability improvement over time

### Scope

Start with **technology** (code, architecture, infrastructure, tools, AI workflows).
Expand to decision-making, life optimization, and full-spectrum personal growth.

## Working Rules

- Prefer `rg` / `rg --files` for search.
- Use `apply_patch` for manual file edits.
- Do not revert unrelated local changes.
- Do not commit secrets, `.env`, `.ori`, cache files, build outputs, or other local backup files
  unless the user explicitly asks for them.
- When changing repository guidance, keep `CLAUDE.md` and `CODEX.md` aligned.
- Treat `.agents/skills/using-forge/SKILL.md` as the repo-standard AI-facing operator contract for Forge.
- When CLI semantics, receipts, trigger rules, release workflow, or operator docs change, update
  `.agents/skills/using-forge/SKILL.md` in the same change set.

### Language & Communication

- **Interactive language**: Chinese (中文)
- **Documentation**: Chinese by default
- **Code**: English only (except proper nouns)
- **Git commits**: Prefer Chinese summaries in this repository

### Time Management

**Core principle**: Never manually input dates, always use commands.

```bash
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d\ %H:%M:%S)
TODAY_CN=$(date +%Y年%m月%d日)
```

- **Historical dates** (creation): set once, never modify
- **Maintenance dates** (last updated): auto-update on each edit
- ❌ **Forbidden**: Manually input any date
- ✅ **Required**: Use bash commands to get current time

## Directory Structure

```
Experience/
├── raw/                    # Layer 1: Quick capture (low barrier)
│   ├── captures/           #   Daily observations, quick notes
│   ├── experiments/        #   Trial results, PoC outcomes
│   └── references/         #   External resources, bookmarks
├── knowledge/              # Layer 2: Distilled knowledge (reusable)
│   ├── troubleshooting/    #   Problem diagnosis and fixes
│   ├── architecture/       #   Design decisions and patterns
│   ├── tools/              #   Tool usage and configuration
│   ├── workflow/           #   Processes and methodologies
│   └── best-practices/     #   Proven patterns and standards
├── insights/               # Layer 3: Patterns and innovation
│   ├── patterns/           #   Cross-cutting patterns discovered
│   ├── innovations/        #   New ideas and approaches
│   └── retrospectives/     #   Periodic reviews and reflections
├── automation/             # Evolution engine tooling
│   ├── scripts/            #   Index generation, tag extraction
│   ├── templates/          #   Document templates
│   └── hooks/              #   Git hooks, automation triggers
├── docs/                   # Project meta-documentation
│   └── management/         #   PLANNING.md, TASK.md, etc.
├── CLAUDE.md               # This file
└── CODEX.md -> CLAUDE.md   # Symlink
```

## Document Standards

### Frontmatter

All documents use YAML frontmatter (`---` delimiters). This is the single metadata format
for the entire repo — scripts, indexes, and AI tools all parse it.

**Required fields** (all documents):

```yaml
---
title: SSH密码认证问题诊断
created: 2026-03-17
updated: 2026-03-17
tags: [ssh, auth, docker, troubleshooting]
status: active   # draft | hypothesis | active | superseded | archived
---
```

**Layer-specific fields**:

| Field | Usage | Example |
|-------|-------|---------|
| `source` | Raw capture 的来源说明；从 `raw` 提升前必须填写 | `source: "同事反馈"` |
| `derived_from` | Knowledge 的上游 raw 文档列表 | `derived_from: [raw/captures/2026-04-02-ssh-note.md]` |
| `evidence` | Insight 的证据链 knowledge 列表 | `evidence: [knowledge/troubleshooting/a.md, knowledge/tools/b.md]` |
| `impact` | Significance level (insight layer) | `impact: high` |
| `reuse_count` | Times reused (knowledge layer) | `reuse_count: 3` |

**Design rules**:
- `category` is NOT a frontmatter field — inferred from directory path
  (`knowledge/troubleshooting/` → troubleshooting)
- `tags` `derived_from` `evidence` 都使用单行 YAML list，便于脚本解析
- `tags` 保持小写、短横线风格
- `created` is set once and never changed; `updated` changes on every edit
- Dates use `YYYY-MM-DD` format, obtained via `$(date +%Y-%m-%d)`
- `status` 推荐含义：
  - `draft`: 未完成，不允许向上层依赖
  - `hypothesis`: 已形成洞察假设，但仍需更多验证
  - `active`: 当前有效、可复用
  - `superseded`: 已被新文档替代
  - `archived`: 仅保留历史价值

### Document Body

After frontmatter, document structure varies by layer:

**raw/** — Minimal. Speed over polish.

```markdown
---
title: Docker bridge 网络隔离问题
created: 2026-04-02
updated: 2026-04-02
tags: [docker, network]
status: draft
source: ""
---

# Docker bridge 网络隔离问题

[Content — as brief or detailed as needed]
```

**knowledge/** — Structured and reusable.

```markdown
---
title: SSH密码认证问题诊断
created: 2026-03-17
updated: 2026-04-02
tags: [ssh, password-auth, docker, pam]
status: active
reuse_count: 0
derived_from: [raw/captures/2026-04-02-ssh-password-auth-incident.md]
---

# SSH密码认证问题诊断

## Context
## Content
## Key Takeaways
## Related
```

**insights/** — Pattern discovery and innovation.

```markdown
---
title: 容器网络故障共性模式
created: 2026-04-02
updated: 2026-04-02
tags: [docker, network, pattern]
status: hypothesis
impact: high
evidence: [knowledge/troubleshooting/a.md, knowledge/troubleshooting/b.md]
---

# 容器网络故障共性模式

## Observation
## Analysis
## Application
## Evidence
```

### Promotion Contract

`raw -> knowledge`

- 新事件、新观察、新实验默认先进入 `raw/`
- `raw` 在提升前必须补全 `source`
- `knowledge` 必须声明 `derived_from`，且所有路径都必须指向存在的 `raw/*.md`

`knowledge -> insights`

- `insights` 只记录跨文档模式，不复述单一案例
- `insights` 必须声明 `evidence`
- 非 `draft` 的 insight 至少要有 2 个 `knowledge/*.md` 证据来源
- 非 `draft` 的 insight 必须填写 `impact`

### Validation Workflow

在提交前运行：

```bash
./automation/scripts/validate-provenance.sh
./automation/scripts/generate-index.sh
```

### Naming Convention

- `raw/`: Date prefix: `2026-04-02-quick-note.md`
- `knowledge/`: Descriptive: `ssh-password-auth-diagnosis.md`
- `insights/`: Pattern-focused: `pattern-container-network-failures.md`

## Commit Rules

### Canonical Format

- Subject: `type(scope): summary`
- `type`: `docs` `feat` `fix` `refactor` `chore` `revert`
- `scope`: `raw` `knowledge` `insight` `automation` `config`

### When Body Is Mandatory

A body is required when the change:
- Crosses multiple documents or directories
- Changes structure, conventions, or standards
- Includes significant technical content
- Affects knowledge organization

### Body Structure

```text
type(scope): 简要说明

一句话概述本次提交。

背景：
- ...

本次改动：
- ...

## AI-Facing Contract

- Project-local skill lives at `.agents/skills/using-forge/`.
- This skill is part of the repository standard, not optional local documentation.
- If a release, version bump, CLI change, receipt change, or operator-flow change alters how Forge should be used,
  the same change set must update:
  - `.agents/skills/using-forge/SKILL.md`
  - `docs/management/repository-conventions.md`
  - relevant operator docs and README when applicable

收益：
- ...

结果：
- ...
```

### Line Width And Wording

- Every commit-message line must be at most 100 characters.
- Reflow prose instead of leaving overlong lines.
- Do not mechanically split identifiers, commands, URLs or paths.
- When the message is long, prefer composing in a temp file: `git commit -F`.

### Pre-commit Checks

```bash
./automation/scripts/validate-provenance.sh
git diff --cached --check
git log -1 --pretty=%B | awk 'length($0) > 100 { print NR ":" length($0) ":" $0 }'
grep -rn " $" *.md && echo "❌ Found trailing whitespace" || echo "✅ Clean"
```

## Automation Roadmap

### Phase 0: Foundation (Current)

- [x] CLAUDE.md + CODEX.md
- [x] Directory structure
- [x] Document templates
- [x] Index generation script
- [x] Quick capture script
- [x] Tag extraction tool
- [x] Provenance validation script

### Phase 1: Systematic Collection (Month 1)

- [x] Migrate existing docs to knowledge/
- [x] Backfill raw provenance for existing knowledge docs
- [ ] Build 30+ knowledge articles
- [ ] Auto-index with tags and categories
- [ ] Cross-reference detection
- [ ] Weekly review trigger

### Phase 2: Intelligent Processing (Month 2-3)

- [ ] AI-assisted classification
- [ ] Pattern discovery across articles
- [ ] Knowledge gap analysis
- [ ] Auto-generated insights
- [ ] Reuse tracking

### Phase 3: Autonomous Flow (Month 4-6)

- [ ] Multi-source auto-collection
- [ ] Real-time processing pipeline
- [ ] Recommendation engine
- [ ] Self-improving system

## Best Practices

1. **Capture immediately**: 新内容先写进 `raw/`，不要直接跳到 `knowledge/`。
2. **Promote with provenance**: `knowledge` 必须写 `derived_from`，`insights` 必须写 `evidence`。
3. **Tag consistently**: Tags enable cross-cutting pattern discovery.
4. **Link aggressively**: Every article should reference related knowledge.
5. **Track reuse**: Increment reuse count when knowledge prevents redundant work.
6. **Review monthly**: Generate insights from accumulated knowledge.
7. **Automate friction**: If you do it twice, script it.
