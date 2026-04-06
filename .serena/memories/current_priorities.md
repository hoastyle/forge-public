# Forge Current Priorities & TODOs

## Priority 1: LLM Automation Pipeline
**Status**: in-progress
**Goal**: Build `raw → knowledge → insights` LLM-powered automation pipeline

### Design Principles (from `forge-llm-pipeline-v1.md`)
- Control plane / Runtime plane separation
- LLM outputs structured JSON, not direct Markdown
- Multi-layer quality gates (schema + validators + critic + judge)
- Conservative release strategy (draft → hypothesis → active)

### Recent Milestones
- ✅ Architecture design documented
- ✅ Provenance validation system established
- ⏳ Build `automation/pipeline/` skeleton
- ⏳ Implement `llm_client.py` with LiteLLM SDK
- ⏳ Implement writer/critic/judge for `raw → knowledge`

### Key Design Decisions
| Decision | Date | Rationale |
|----------|------|-----------|
| Control/Runtime separation | 2026-04-03 | Separate flexibility from determinism |
| Structured JSON output | 2026-04-03 | Enable validation, critic review, template changes |
| Conservative release | 2026-04-03 | Minimize errors in official docs |

## Priority 2: Code Map (Company & Personal)
**Status**: todo
**Goal**: Build comprehensive code repository maps linking services, dependencies, owners, docs

### Expected Outputs
- Code repository inventory and classification
- Service/module dependency graphs
- Ownership and responsibility mapping
- Critical path and high-risk module annotations
- Reverse links to Forge knowledge base

### Recent Milestones
- ⏳ Define object model: repo/service/module/owner/dependency/doc/incident
- ⏳ Identify collection sources: git, package managers, CI, docs, manual
- ⏳ Design minimal storage and visualization
- ⏳ Pilot on a real codebase

## Priority 3: Autoresearch Self-Iteration
**Status**: todo
**Goal**: Introduce "generate → critique → improve" loop for continuous system evolution

### Core Concepts
- Auto-critique and rewrite after generation
- Failure case pattern attribution
- Prompt/policy improvement suggestions from historical outputs
- "Generate → Evaluate → Adjust → Replay → Lock" loop

### Recent Milestones
- ⏳ Abstract writer/critic/judge interfaces
- ⏳ Build failure case archive and replay mechanism
- ⏳ Design prompt/policy patch suggestion format
- ⏳ Map frequent failures to actionable tuning
- ⏳ Design minimal auto-review/auto-retune flow

## Unified Strategy
- **Pipeline**: Execution framework
- **Code Map**: Context foundation
- **Autoresearch**: Self-evolution capability

## Technical Debt
- [ ] raw/ directory structure needs automation script assistance
- [ ] INDEX.md could add insights layer index
- [ ] quick-capture.sh needs real-world testing
- [ ] LLM automation pipeline skeleton not yet implemented
- [ ] Code map object model and storage undetermined
- [ ] Autoresearch self-iteration not yet institutionalized
