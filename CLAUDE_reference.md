# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is an optimized closed-loop workflow command system for Claude Code that integrates project planning, task management, and development workflows.

**🚀 Quick Start**: New users can be productive with just 4 Essential Commands (80% of use cases)
**🔄 Context Continuity**: Uses PLANNING.md, TASK.md, and CONTEXT.md to maintain context across `/clear` boundaries
**⚡ Streamlined**: 13 commands organized by development lifecycle stages
**🛡️ Quality Gates**: Built-in formatting, testing, and validation

1. 语言
    * 交互沟通使用中文
    * 默认文档使用中文
    * 代码中全部使用英文(除非专有名词类)
    * 代码提交参考历史提交，如果历史提交大部分为中文，则使用中文。否则使用英文。
2. 项目管理类文档在docs/management目录下构建和管理，管理类文件包括:
    * PRD.md
    * PLANNING.md
    * TASK.md
    * CONTEXT.md
    * KNOWLEDGE.md

## Command Overview

All commands follow the `wf_<number>_<name>.md <ARGUMENTS>` format where:
- **Numbered prefixes** indicate typical usage order in workflows
- **Arguments** specify the target scope (feature, component, error, etc.)
- **Multi-agent coordination** used for complex tasks with specialized roles
- **Progressive development** with validation at each step

### Core Philosophy

The workflow system is designed to:
1. **Maintain Context** - Use PLANNING.md, TASK.md, and CONTEXT.md as persistent context stores
2. **Enable Continuity** - Allow work to continue across `/clear` boundaries via `wf_03_prime.md`
3. **Track Progress** - Automatically update task status throughout development
4. **Enforce Standards** - Apply consistent patterns and quality gates
5. **Close the Loop** - Each command integrates with others for complete workflows
6. **Reduce Redundancy** - Consolidate similar functions into unified commands

### Foundation Commands (1-3) - Project Infrastructure
- `wf_01_planning.md` - Create/update project planning documentation (aligned with PRD.md)
- `wf_02_task.md` - Manage task tracking and progress (mapped to PRD requirements)
- `wf_03_prime.md` - Load project context from PRD.md, PLANNING.md, TASK.md, and CONTEXT.md

### Development Commands (4-6) - Implementation Phase
- `wf_04_ask.md` - Architecture consultation within PRD and project context (includes comprehensive codebase review capabilities)
- `wf_05_code.md` - Implement features aligned with PRD requirements (auto-formatting integrated)
- `wf_06_debug.md` - Enhanced systematic debugging and fixing (integrated with advanced error analysis protocol)

### Quality Assurance Commands (7-10) - Quality & Optimization Phase
- `wf_07_test.md` - Test development and execution (coverage analysis integrated, PRD criteria validation)
- `wf_08_review.md` - Code review against standards and PRD compliance
- `wf_09_refactor.md` - Code improvement maintaining PRD compliance
- `wf_10_optimize.md` - Performance optimization (meeting PRD performance requirements)

### Operations Commands (11-12) - Deployment & Maintenance Phase
- `wf_11_commit.md` - Git commits with formatting and context updates (auto-formatting integrated)
- `wf_12_deploy_check.md` - Deployment readiness validation (PRD criteria verification)

### Support Commands (99) - Always Available
- `wf_99_help.md` - Complete help system (integrates guide, quick reference, and command help)

## Quick Start Guide

### 🚀 New to cc_commands? Start Here!

#### Essential Commands (80% of workflows)
These 4 commands handle most development scenarios:

**1. 📋 Project Setup** - `wf_01_planning.md "<project_description>"`
- Creates PLANNING.md with architecture, tech stack, standards
- Establishes PRD alignment and development guidelines
- **When to use**: Starting new projects or major feature planning
- **Example**: `wf_01_planning.md "E-commerce API with user authentication"`

**2. 🔄 Context Loading** - `wf_03_prime.md`
- Loads all project context (PRD.md, PLANNING.md, TASK.md, CONTEXT.md)
- **CRITICAL**: Always run after `/clear` or session restart
- **When to use**: Session start, after context loss, resuming work
- **Example**: Simply run `wf_03_prime.md` (no arguments needed)

**3. 💻 Feature Implementation** - `wf_05_code.md "<feature_description>"`
- Multi-agent development with auto-formatting
- Follows project standards and PRD requirements
- **When to use**: Implementing new features or major functionality
- **Example**: `wf_05_code.md "User login with JWT token validation"`

**4. 💾 Save Progress** - `wf_11_commit.md "<commit_message>"`
- Quality gates, auto-formatting, context updates
- Updates TASK.md and CONTEXT.md automatically
- **When to use**: After completing work, before `/clear`
- **Example**: `wf_11_commit.md "Add user authentication system"`

#### Intermediate Commands (Cover remaining 15%)
Ready to expand? Add these workflow enhancers:

**5. 🤔 Decision Support** - `wf_04_ask.md "<technical_question>"`
- Architecture consultation with optional codebase review
- **Flag**: Use `--review-codebase` for comprehensive analysis
- **Example**: `wf_04_ask.md "Should I use Redis or database caching?"`

**6. 🧪 Testing** - `wf_07_test.md "<component_to_test>"`
- Test development with coverage analysis
- **Flag**: Use `--coverage` for detailed coverage reports
- **Example**: `wf_07_test.md "UserService authentication methods"`

**7. 🔍 Quality Review** - `wf_08_review.md`
- Code review against standards and PRD compliance
- **Example**: `wf_08_review.md` (reviews current codebase)

**8. 📝 Task Management** - `wf_02_task.md update "<task_description>"`
- Dynamic task tracking with PRD traceability
- **Example**: `wf_02_task.md update "Complete user registration API"`

### 🎯 Advanced Users: Full Workflow Commands

Once comfortable with the basics, explore:
- `wf_06_debug.md` - Systematic error resolution
- `wf_09_refactor.md` - Code structure improvements
- `wf_10_optimize.md` - Performance tuning
- `wf_12_deploy_check.md` - Deployment validation

## Command Decision Tree

### 🤔 Which Command Should I Use?

**Start here** → What do you want to do?

```
🆕 Starting fresh?
├── 📋 New project → wf_01_planning.md "project description"
└── 🔄 Resume work → wf_03_prime.md

💻 Building features?
├── 🤔 Need guidance → wf_04_ask.md "technical question"
├── 💻 Write code → wf_05_code.md "feature description"
├── 🐛 Fix bugs → wf_06_debug.md "error description"
└── 🧪 Add tests → wf_07_test.md "component name"

🔍 Improving quality?
├── 👀 Review code → wf_08_review.md
├── 🔧 Refactor → wf_09_refactor.md "component to improve"
└── ⚡ Optimize → wf_10_optimize.md "performance target"

💾 Finishing work?
├── 📝 Update tasks → wf_02_task.md update "task description"
├── 💾 Commit changes → wf_11_commit.md "commit message"
└── 🚀 Check deployment → wf_12_deploy_check.md

❓ Need help → wf_99_help.md
```

### 🎯 Common Scenarios

**"I'm new and don't know where to start"**
→ `wf_01_planning.md` → `wf_03_prime.md` → `wf_05_code.md` → `wf_11_commit.md`

**"I just opened Claude Code"**
→ `wf_03_prime.md` (loads all context)

**"I want to implement a feature"**
→ `wf_04_ask.md` (get guidance) → `wf_05_code.md` → `wf_07_test.md` → `wf_11_commit.md`

**"Something is broken"**
→ `wf_06_debug.md` → `wf_07_test.md` → `wf_11_commit.md`

**"Code quality needs improvement"**
→ `wf_08_review.md` → `wf_09_refactor.md` → `wf_07_test.md` → `wf_11_commit.md`

**💡 Pro Tip**: Each command follows the pattern `wf_XX_name.md "<description>"` and integrates automatically with your project files (PLANNING.md, TASK.md, CONTEXT.md).

## Complete Workflow Patterns

### 🔄 Session Management
**Essential for context continuity:**
```
📱 Session Start   → wf_03_prime.md (load all context)
⚡  Active Work     → wf_05_code.md, wf_07_test.md, etc.
💾 Save Progress   → wf_11_commit.md (auto-updates CONTEXT.md)
🔄 Memory Reset    → /clear (when context gets large)
🚀 Resume Work     → wf_03_prime.md (reload and continue)
```

### 🏗️ Feature Development (Complete)
**Full development lifecycle:**
```
🤔 Plan           → wf_04_ask.md "architecture guidance"
💻 Implement      → wf_05_code.md "feature description"
🧪 Test           → wf_07_test.md "component name"
👀 Review         → wf_08_review.md
💾 Commit         → wf_11_commit.md "feature completed"
📝 Track          → wf_02_task.md update "task status"
```

### 🐛 Bug Fixing (Streamlined)
**Efficient problem resolution:**
```
🔍 Debug          → wf_06_debug.md "error description"
✅ Verify Fix     → wf_07_test.md "affected component"
💾 Commit         → wf_11_commit.md "fix applied"
```

### 🔧 Quality Improvement (Advanced)
**Code quality enhancement:**
```
📊 Analyze        → wf_08_review.md
🔧 Refactor       → wf_09_refactor.md "component to improve"
⚡  Optimize       → wf_10_optimize.md "performance target"
🧪 Test           → wf_07_test.md --coverage "ensure no regression"
💾 Commit         → wf_11_commit.md "quality improvements"
```

## Key Files (Closed Loop)

### PRD.md (Requirements Source)
Project Requirements Document - read-only reference containing:
- Official project requirements and specifications
- Business objectives and success criteria
- Stakeholder requirements and constraints
- **CRITICAL**: Never automatically modified by commands
- **ROLE**: Source of truth for all project decisions

### PLANNING.md
Technical architecture document aligned with PRD.md containing:
- Project overview and goals (derived from PRD.md)
- System architecture and design (meeting PRD requirements)
- Technology stack and tools (supporting PRD objectives)
- Development standards and patterns
- Testing and deployment strategies
- PRD compliance checklist

### TASK.md
Dynamic task tracking document containing:
- Categorized task lists (mapped to PRD requirements)
- Task status and progress
- Dependencies and blockers
- Completion history
- PRD requirement traceability

### CONTEXT.md (New)
Session state and progress summary containing:
- Work completed in recent sessions
- Key decisions made (with PRD alignment notes)
- Current focus areas
- Next priority items
- Auto-updated by wf_11_commit.md for seamless session continuity

## Command Integration Rules

1. **PRD Compliance**: All commands must reference and align with PRD.md requirements (read-only, never modify)
2. **Context Loading**: Commands should read PRD.md for requirements, PLANNING.md for standards, TASK.md for status, and CONTEXT.md for session state
3. **Progress Updates**: Commands that complete work should update TASK.md with PRD requirement traceability
4. **Standard Enforcement**: All code generation follows PLANNING.md guidelines aligned with PRD requirements
5. **Documentation**: Significant decisions update PLANNING.md with PRD alignment justification
6. **Task Generation**: Issues and improvements create TASK.md entries mapped to PRD requirements
7. **Session Continuity**: wf_11_commit.md auto-updates CONTEXT.md for seamless wf_03_prime.md loading
8. **Integrated Operations**: Formatting, coverage analysis, and fixing are integrated into main commands

## Multi-Agent Coordination

The cc_commands workflow system uses a multi-agent approach with specialized roles:

- **Architect Agent** - High-level design and structure analysis
- **Implementation Engineer** - Core functionality development following standards
- **Integration Specialist** - System compatibility and dependency management
- **Code Reviewer** - Quality validation and standards compliance
- **Test Specialists** - Various testing strategies (unit, integration, coverage)
- **Structure Analyst** - Code architecture evaluation and improvement
- **Design Pattern Expert** - Pattern application for maintainability
- **Debug Coordinator** - Systematic error analysis and resolution
- **Performance Optimizer** - System performance analysis and tuning

Each command orchestrates relevant specialists to ensure comprehensive coverage of development tasks while maintaining consistency with project standards and PRD requirements.

## Development Standards

### Code Quality
- Follow patterns established in existing code
- Maintain test coverage requirements
- Auto-formatting applied by wf_11_commit.md (Python: black, JS/TS: prettier, C++: clang-format, Go: gofmt)
- **No trailing whitespace**: All files must be free of trailing spaces and tabs
- **Consistent line endings**: Use Unix-style line endings (LF)
- Document significant changes

### Pre-commit Quality Checks
**Automated through pre-commit framework**: The system now uses pre-commit hooks for automated quality validation.

**Manual Installation** (one-time setup):
```bash
# Install pre-commit framework
pip install pre-commit

# Install hooks in repository
pre-commit install
```

**Automated Checks** (run automatically on commit):
- Trailing whitespace detection (zero tolerance)
- File format validation
- Line ending validation (Unix LF only)
- Markdown link validation
- Command reference consistency

**Manual Verification** (if needed):
```bash
# Run checks on all files
pre-commit run --all-files

# Run checks on staged files only
pre-commit run

# Legacy manual checks (if pre-commit not available)
grep -n " $" *.md && echo "❌ Found trailing whitespace" || echo "✅ No trailing whitespace"
file *.md | grep -v "ASCII text" && echo "❌ Non-standard file format" || echo "✅ Clean file formats"
```

### Git Workflow
- Semantic commit messages ([feat], [fix], [docs], [refactor])
- Task references in commits
- **Mandatory quality checks**: Run pre-commit validation before every commit
- Auto-formatting integrated into wf_11_commit.md
- Auto-update TASK.md and CONTEXT.md after commits
- Consider splitting logically separate changes into different commits

### Quality Gate Enforcement
The `wf_11_commit.md` command MUST include these checks:
1. **Pre-commit hooks execution**: Run all configured quality gates
2. **Whitespace validation**: Reject commits with trailing whitespace (zero tolerance)
3. **File format validation**: Ensure consistent line endings and formats
4. **Auto-formatting**: Apply language-specific formatters
5. **Lint checks**: Run relevant linters before commit
6. **Link validation**: Verify all markdown links work correctly
7. **Reference consistency**: Ensure command references are consistent across documentation

### Testing
- Write tests for new features
- Maintain coverage targets using wf_07_test.md --coverage
- Test before deployment
- Document test strategy in PLANNING.md

### Error Debugging Process
Follow the systematic approach in `wf_06_debug.md`:
1. Analyze complete error output with detailed classification
2. Research using available tools (context7 MCP, brave-search MCP)
3. Implement targeted fixes addressing root causes
4. Verify fixes by re-running original commands
5. Iterate if new errors appear
6. Document solutions for future reference

## Best Practices

1. **Start Sessions with Prime**: Always run `wf_03_prime.md` after `/clear`
2. **Update Tasks Regularly**: Keep TASK.md current with progress
3. **Document Decisions**: Update PLANNING.md with architectural changes
4. **Test Continuously**: Run tests after significant changes
5. **Review Before Commit**: Use `wf_08_review.md` for quality checks
6. **Quality First**: Run pre-commit checks to catch whitespace, formatting issues
7. **Let Commit Handle Everything**: wf_11_commit.md includes quality gates, formatting, and validation

## Troubleshooting

### Lost Context
- Run `wf_03_prime.md` to reload from all core files
- Check CONTEXT.md for latest session state
- Review PLANNING.md for architecture
- Review TASK.md for current state

### Unclear Requirements
- Use `wf_04_ask.md` for consultation
- Update PLANNING.md with decisions
- Create tasks in TASK.md

### Quality Issues
- Run `wf_08_review.md` for assessment
- Apply `wf_09_refactor.md` for improvements
- Verify with `wf_07_test.md --coverage`

### Code Quality Problems
- **Trailing whitespace found**: Run `pre-commit run --all-files` to identify and fix automatically
- **Commit rejected by quality gates**: Run `pre-commit run` to see specific issues, fix, then retry
- **Mixed line endings**: Pre-commit hooks will detect and reject inconsistent line endings
- **Formatting inconsistent**: Let `wf_11_commit.md` handle auto-formatting and pre-commit validation
- **Pre-commit not installed**: Run `pip install pre-commit && pre-commit install` to set up quality gates
- **Hook failures**: Review pre-commit output for specific file and line numbers with issues

### 时间点管理规范

**核心原则**: 绝不手动输入日期，总是使用命令动态获取

#### 标准时间获取命令
```bash
# 基础日期格式
TODAY=$(date +%Y-%m-%d)              # 今天: 2025-08-21
YESTERDAY=$(date -d 'yesterday' +%Y-%m-%d)  # 昨天: 2025-08-20
TIMESTAMP=$(date +%Y-%m-%d\ %H:%M:%S)       # 完整时间戳

# 中文格式（用于文档）
TODAY_CN=$(date +%Y年%m月%d日)        # 2025年08月21日
WEEK_CN=$(date +%Y年第%U周)           # 2025年第34周
```

#### 日期类型与使用规则
1. **历史日期** (创建时间、发布日期)
   - 创建时使用: `$(date +%Y-%m-%d)`
   - 一旦确定，永不修改

2. **维护日期** (最后更新、修改时间)
   - 总是使用: `$(date +%Y-%m-%d)`
   - 每次修改时自动更新

3. **ADR决策日期** (架构决策记录)
   - 决策当天: `$(date +%Y-%m-%d)`
   - 体现决策制定的具体时间

#### 文档模板示例
```markdown
**创建日期**: $(date +%Y-%m-%d)      # 项目启动时固定
**最后更新**: $(date +%Y-%m-%d)      # 每次编辑自动更新
**版本发布**: $(date +%Y-%m-%d)      # 版本发布时固定
**决策日期**: $(date +%Y-%m-%d)      # ADR决策时固定
```

#### 预防时间错误的强制规则
- ❌ **禁止**: 手动输入任何形式的日期
- ✅ **必须**: 使用bash命令获取当前时间
- ✅ **必须**: 在wf_11_commit.md中验证日期正确性
- ✅ **必须**: 区分历史日期和维护日期的处理方式

## Version Information

**Current Version**: v2.3 (User Experience Optimization)
**Last Updated**: 2025-08-21

### Recent Improvements (v2.3)
- Enhanced Quick Start Guide with detailed Essential Commands
- Added Command Decision Tree for intuitive command selection
- Improved Workflow Patterns with visual clarity
- Comprehensive code quality rules and enforcement

For complete version history, optimization details, and development roadmap, see: **[CHANGELOG.md](./CHANGELOG.md)**

## Continuous Improvement

The workflow system evolves through:
- Regular PLANNING.md updates
- Task pattern analysis
- Command refinements
- Process optimization
- User feedback integration

This system ensures development continuity, quality maintenance, and efficient progress tracking across all project phases while maintaining simplicity and avoiding redundancy.
