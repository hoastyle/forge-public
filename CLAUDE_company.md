# AI 工具知识库 - Claude Code 入口

**版本**: v2.1 (Claude Code 优先)
**最后更新**: 2025-12-29
**定位**: 本知识库为 Claude Code 优化，提供设计哲学、最佳实践和工具指南

> 🎯 **快速开始**: Claude Code 首次访问时，阅读本文件的"📍 知识库导航"部分即可

---

## 📍 知识库导航 (For Claude Code)

### 我要做什么？ → 找对应的文档

| 场景 | 首选文档 | 优先级 |
|------|---------|--------|
| 🔧 **实现功能** | [best-practices/ai-collaboration.md](best-practices/ai-collaboration.md) | ⭐⭐⭐ |
| 📝 **生成文档** | [best-practices/document-architecture.md](best-practices/document-architecture.md) | ⭐⭐⭐ |
| 🎨 **设计架构** | [PHILOSOPHY.md](PHILOSOPHY.md) | ⭐⭐⭐ |
| 🔌 **使用 MCP** | [mcp-integration/README.md](mcp-integration/README.md) | ⭐⭐ |
| 🛠️ **使用工具** | [KNOWLEDGE.md#工具库](KNOWGE.md) | ⭐⭐ |
| ❓ **查决策理由** | [docs/adr/](docs/adr/) | ⭐ |

### 按角色查找

**作为 AI 助手**:
1. 先读 [PHILOSOPHY.md](PHILOSOPHY.md) - 理解设计思维
2. 再读 [best-practices/ai-collaboration.md](best-practices/ai-collaboration.md) - 学习协作模式

**作为开发者**:
1. 先读 [best-practices/document-architecture.md](best-practices/document-architecture.md) - 理解文档规范
2. 再读 [mcp-integration/quick-start.md](mcp-integration/quick-start.md) - 学习 MCP 集成

**作为架构师**:
1. 先读 [PHILOSOPHY.md](PHILOSOPHY.md) - 理解设计哲学
2. 再读 [docs/adr/](docs/adr/) - 查看历史决策

---

## 🎯 核心设计原则 (Ultrathink)

### 6 个核心原则

1. **Think Different** - 质疑假设，追求最优
   - 第一个能工作的方案往往不是最优的
   - 应用: 架构设计、技术选型、系统边界划分

2. **Balance Trade-offs** - 明确权衡，记录决策
   - 每个决策都涉及取舍
   - 应用: 使用 ADR 记录"为什么"

3. **Iterate to Excellence** - 持续打磨
   - 不懈地打磨细节
   - 应用: 代码重构、文档优化

4. **Context Aware** - 理解环境
   - 技术选型必须考虑实际需求
   - 应用: 框架选择、工具评估

5. **Document Decisions** - 沉淀学习
   - 记录决策的"为什么"
   - 应用: 创建 ADR

6. **Test Assumptions** - 验证假设
   - 通过 PoC 验证方案
   - 应用: 技术验证

**详细说明**: [best-practices/philosophy.md](best-practices/philosophy.md)

---

## 📚 快速参考卡片

### 卡片 1: AI 协作模式

**何时使用**: 当 Claude Code 需要与开发者协作时

**核心实践**:
- ✅ 明确的上下文加载（每次会话开始）
- ✅ 约束驱动交互（在 CLAUDE.md 中定义规则）
- ✅ 渐进式自动化（从简单到复杂）
- ✅ 质量门控（pre-commit, 测试覆盖）

**快速链接**:
- [完整指南](best-practices/ai-collaboration.md)
- [文档架构](best-practices/document-architecture.md)
- [上下文管理](best-practices/ai-collaboration.md#会话生命周期)

### 卡片 2: 文档生成约束

**何时使用**: 当需要生成或更新文档时

**三阶段门控**:
1. **Phase 1**: 文档决策树（确定类型和位置）
2. **Phase 2**: 成本估计和门控（<500行，<30%增长率）
3. **Phase 3**: 架构合规性检查（Frontmatter 完整性）

**快速链接**:
- [完整指南](best-practices/document-architecture.md)
- [决策树](best-practices/document-architecture.md#文档分类决策树)
- [Frontmatter 规范](docs/reference/FRONTMATTER.md)

### 卡片 3: MCP 集成

**何时使用**: 当需要使用 MCP 服务器时

**两种集成方式**:

1. **AIRIS MCP Gateway** (推荐) - 统一接口访问 13 个 MCP 服务器
   - 三步工作流: airis-find → airis-schema → airis-exec
   - 112 个工具，HOT/COLD 模式优化
   - 文档: [docs/airis-mcp-gateway/README.md](docs/airis-mcp-gateway/README.md)

2. **传统 MCP** - 直接集成单个服务器
   - Gateway 模式: `get_mcp_gateway()`
   - 文档: [mcp-integration/](mcp-integration/)

**可用 MCP 服务器** (通过 Gateway):
- **HOT 模式** (4): airis-agent, memory, gateway-control, airis-commands
- **COLD 模式** (9): serena, playwright, tavily, context7, morphllm, magic, chrome-devtools, fetch, sequential-thinking

**快速参考**:
- [快速参考卡片](docs/airis-mcp-gateway/QUICK_REFERENCE.md)
- [工具索引](docs/airis-mcp-gateway/TOOL_INDEX.md)
- [服务器文档](docs/airis-mcp-gateway/servers/)

### 卡片 4: 技术选型

**何时使用**: 当需要选择技术方案时

**核心原则**:
1. 优先开源（除非有特殊理由）
2. 成熟优先（有社区、有文档）
3. 标准优先（业界标准方案）
4. 记录决策（创建 ADR）

**决策流程**:
```
需求明确 → 列举 3+ 方案 → 分析优缺点 → 记录 ADR → PoC 验证
```

**快速链接**:
- [完整原则](docs/adr/2025-11-13-prioritize-opensource-in-architecture.md)
- [ADR 模板](docs/adr/TEMPLATE.md)
- [决策示例](docs/adr/)

---

## 📂 知识库结构

```
ai_workflow/
├── CLAUDE.md (本文件) - 🎯 知识库主入口
├── KNOWLEDGE.md - 📚 完整索引
├── PHILOSOPHY.md - 🎨 设计哲学
│
├── best-practices/      - 💡 最佳实践集合
│   ├── philosophy.md       - Ultrathink 设计思维
│   ├── document-architecture.md  - 文档架构
│   └── ai-collaboration.md  - AI 协作模式
│
├── mcp-integration/     - 🔌 MCP 集成专题
│   ├── README.md            - Serena 使用指南
│   ├── quick-start.md       - 快速开始
│   └── troubleshooting.md   - 故障排查
│
├── docs/
│   ├── adr/                 - 🗂️ 17 个架构决策记录
│   ├── reference/           - 📖 参考文档（Frontmatter, Markdown）
│   └── examples/            - 💼 使用示例
│
├── commands/lib/        - 🛠️ 工具库（DocLoader, AgentCoordinator）
├── scripts/             - 📜 实用脚本（doc_guard, frontmatter_utils）
└── archive/             - 📦 归档内容（workflow 历史文档）
```

---

## 🔍 按需加载指南

### 文档大小策略

| 文档大小 | 加载方式 | 示例 |
|---------|---------|------|
| < 100 行 | 直接读取 | CLAUDE.md (本文件) |
| 100-300 行 | 摘要模式 | [mcp-integration/README.md](mcp-integration/README.md) |
| 300-800 行 | 章节模式 | [best-practices/document-architecture.md](best-practices/document-architecture.md) |
| > 800 行 | 禁止完整读取 | [docs/adr/2025-11-21-mcp-integration-strategy.md](docs/adr/2025-11-21-mcp-integration-strategy.md) |

### DocLoader 工具

**推荐使用** `scripts/doc_guard.py` 加载大文档:

```bash
# 章节模式
python scripts/doc_guard.py \
  --docs "best-practices/document-architecture.md" \
  --sections '{"best-practices/document-architecture.md": ["三阶段门控", "成本约束"]}'

# 摘要模式
python scripts/doc_guard.py \
  --docs "mcp-integration/README.md" \
  --max-lines 50
```

---

## 🎓 学习路径

### 路径 1: 快速上手 (30 分钟)

1. 阅读 [PHILOSOPHY.md](PHILOSOPHY.md) 的"6 个核心原则" (10 分钟)
2. 阅读 [best-practices/ai-collaboration.md](best-practices/ai-collaboration.md) (10 分钟)
3. 浏览 [KNOWLEDGE.md](KNOWLEDGE.md) 的快速导航 (10 分钟)

### 路径 2: 深入理解 (2 小时)

1. 完成"快速上手"路径
2. 阅读 [best-practices/document-architecture.md](best-practices/document-architecture.md) (30 分钟)
3. 阅读 [mcp-integration/quick-start.md](mcp-integration/quick-start.md) (30 分钟)
4. 浏览 [docs/adr/](docs/adr/) 中的核心决策 (30 分钟)

### 路径 3: 专家级别 (持续学习)

1. 完成前两个路径
2. 实践中应用 Ultrathink 原则
3. 为新决策创建 ADR
4. 贡献新的最佳实践

---

## 🛠️ 常用工具

### 工具快速索引

| 工具 | 功能 | 文档 |
|------|------|------|
| **DocLoader** | 智能文档加载 | [commands/lib/doc_loader.py](commands/lib/doc_loader.py) |
| **DocGuard** | 文档读取保护 | [scripts/doc_guard.py](scripts/doc_guard.py) |
| **AgentCoordinator** | 多 Agent 协调 | [commands/lib/agent_coordinator.py](commands/lib/agent_coordinator.py) |
| **FrontmatterUtils** | Frontmatter 验证 | [scripts/frontmatter_utils.py](scripts/frontmatter_utils.py) |

### 使用示例

**DocLoader**:
```python
from commands.lib.doc_loader import DocLoader
loader = DocLoader()
# 摘要模式
summary = loader.load_summary(doc_path, max_lines=50)
# 章节模式
content = loader.load_sections(doc_path, sections=["Step 3", "MCP Integration"])
```

**DocGuard**:
```bash
# 基础用法
python scripts/doc_guard.py --docs "KNOWLEDGE.md"
# 章节模式
python scripts/doc_guard.py --docs "large_doc.md" --sections '{"large_doc.md": ["Chapter 1"]}'
```

---

## 📊 知识库统计

| 类型 | 数量 |
|------|------|
| 最佳实践文档 | 4 |
| MCP 集成文档 | 4+ |
| 架构决策记录 | 17 |
| 参考文档 | 3 |
| 工具库 | 5+ |
| **总计** | **133 个活跃文档** |

---

## 🤝 贡献指南

本知识库欢迎贡献：

1. **新的 ADR**: 遵循 [docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md)
2. **最佳实践**: 基于实践经验，提交 PR
3. **工具改进**: 保持测试覆盖 > 80%
4. **文档完善**: 遵循 [docs/reference/MARKDOWN_STYLE.md](docs/reference/MARKDOWN_STYLE.md)

**贡献流程**:
1. Fork 项目
2. 创建分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m '[feat] Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📞 获取帮助

| 问题类型 | 查找位置 |
|---------|---------|
| 如何使用知识库 | 本文件的"📍 知识库导航" |
| 设计哲学问题 | [PHILOSOPHY.md](PHILOSOPHY.md) |
| 文档生成问题 | [best-practices/document-architecture.md](best-practices/document-architecture.md) |
| MCP 集成问题 | [mcp-integration/troubleshooting.md](mcp-integration/troubleshooting.md) |
| 工具使用问题 | [KNOWLEDGE.md#工具库](KNOWLEDGE.md) |
| 历史决策理由 | [docs/adr/](docs/adr/) |

---

**最后更新**: 2025-12-29
**版本**: v2.1 (Claude Code 优先)
**维护状态**: 持续更新中
