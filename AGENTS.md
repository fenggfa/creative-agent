# Creative Agent 项目指南

> **Harness 入口** - 定义全局地图与核心行为原则。

## 项目定位

多智能体创意写作系统，LangGraph 编排 + LightRAG 知识库。

## 架构地图

```
src/
├── agents/       # 智能体（见下方详细定义）
├── tools/        # 工具：lightrag 客户端 + 图谱服务 + 连贯性追踪
├── workflow/     # 编排：LangGraph 状态机（单篇/整书双模式）
├── constraints/  # 约束：内容规则检查
├── feedback/     # 反馈：五维评估器
├── harness/      # Harness 核心：验证、E2E、熵管理、文档治理
├── persistence/  # 持久化：解决换班失忆
└── output/       # 输出：保存到 Obsidian + LightRAG
```

## 智能体定义

### 单篇模式（原有）

```
START → researcher → writer → reviewer → output → END
```

| 智能体 | 文件 | 职责 |
|--------|------|------|
| researcher | `agents/researcher.py` | 从知识图谱检索素材 |
| writer | `agents/writer.py` | 根据素材创作内容 |
| reviewer | `agents/reviewer.py` | 审核内容质量 |

### 整书模式（新增）

```
START → director → plot_architect → [章节循环] → output → END
                                      ↓
                     ┌────────────────────────────────┐
                     │ plot_architect (细纲)          │
                     │ → prose_writer (撰写)          │
                     │ → critic (审核)                │
                     │ → save_chapter (保存+状态更新)  │
                     └────────────────────────────────┘
```

| 智能体 | 文件 | 职责 | 约束注入键 |
|--------|------|------|------------|
| director | `agents/director.py` | 统筹全书创作流程 | `director` |
| plot_architect | `agents/plot_architect.py` | 生成整书大纲和章节细纲 | `plot_architect` |
| prose_writer | `agents/prose_writer.py` | 根据大纲撰写正文 | `prose_writer` |
| critic | `agents/critic.py` | 评估内容质量、一致性 | `critic` |

### 连贯性工具模块

| 工具类 | 文件 | 职责 |
|--------|------|------|
| CharacterStateTracker | `tools/continuity.py` | 追踪人物状态变化 |
| PlotThreadTracker | `tools/continuity.py` | 追踪情节线索 |
| ConflictDetector | `tools/continuity.py` | 检测设定冲突 |
| ChapterSummarizer | `tools/continuity.py` | 生成章节摘要 |
| ForeshadowingTracker | `tools/continuity.py` | 追踪伏笔埋设与揭晓 |

## 核心原则

1. **异步优先**：所有 I/O 使用 async/await
2. **类型完整**：函数必须有类型注解
3. **配置单例**：通过 `settings` 访问配置

## Harness Engineering 三大支柱

| 支柱 | 模块 | 说明 |
|------|------|------|
| 上下文工程 | `AGENTS.md` | 渐进式披露，按需加载知识树 |
| 约束工程 | `constraints/`, `harness/provider.py` | 解析 MD 文件并注入约束规则 |
| 反馈工程 | `feedback/evaluator.py`, `harness/e2e.py` | 五维评估 + E2E 验证 |

## Harness 高级要素

| 要素 | 模块 | 用途 |
|------|------|------|
| 持久化状态 | `persistence/` | 解决长任务"换班失忆" |
| E2E 验证 | `harness/e2e.py` | 打破 Agent "纸面胜利" |
| 熵管理 | `harness/entropy.py` | AI 垃圾回收（GC） |
| 文档治理 | `harness/docs.py` | 文档 Linter + 新鲜度监控 |
| 重试机制 | `harness/retry.py` | 反馈回路增强 |
| CI/CD | `.github/workflows/ci.yml` | 自动化验证传感器 |
| 执行器脚本 | `scripts/` | 回滚、环境检查、验证 |

## 知识树

| 路径 | 用途 | 按需加载 |
|------|------|----------|
| `docs/architecture.md` | 系统架构 | 理解整体设计 |
| `docs/design-docs/` | 设计决策 | 需要背景上下文 |
| `docs/exec-plans/` | 执行日志 | Agent 短期记忆 |
| `docs/references/` | 参考资料 | 调用外部 API |

## 知识图谱架构

**双图谱分离设计**：

| 图谱 | 端口 | 内容 | 用途 |
|------|------|------|------|
| 素材图谱 | 9621 | 原作设定、人物、世界观 | 智能体检索素材 |
| 二创图谱 | 9622 | 创作的作品、角色演绎 | 积累创作资产 |

## 输出流程

```
创作完成 → 保存到 Obsidian (人工阅读)
         → 写入二创图谱 (知识积累)
```

**Obsidian 目录结构**：
```
30_二创作品/
└── 西游记/
    ├── 人物设定/
    └── 章节/
```

## 约束边界

| 禁止 | 原因 |
|------|------|
| 硬编码 API Key | 安全 |
| 同步 I/O | 架构 |
| AI 典型表达 | 质量 |

详见 `src/constraints/rules.py`

## 反馈机制

五维评估：一致性(25%) + 创意性(20%) + 质量(20%) + 完成度(20%) + 逻辑(15%)

通过标准：总分 ≥ 0.70，一致性 & 完成度 ≥ 0.60

详见 `src/feedback/evaluator.py`

## 验证命令

```bash
uv run ruff check src/ && uv run mypy src/ && uv run pytest tests/ -v
```

## Agent 边界

- **允许**：修改 src/, tests/
- **确认**：修改 pyproject.toml, .env
- **禁止**：删除 .venv/, 修改 .git/
