# Creative Agent 项目指南

> **Harness 入口** - 定义全局地图与核心行为原则。

## 项目定位

多智能体创意写作系统，LangGraph 编排 + LightRAG 知识库。

## 架构地图

```
src/
├── agents/      # 智能体：researcher → writer → reviewer
├── tools/       # 工具：lightrag 客户端
├── workflow/    # 编排：LangGraph 状态机
├── constraints/ # 约束：内容规则检查
├── feedback/    # 反馈：GAN 风格评估器
├── harness/     # 验证：自动化检查
└── output/      # 输出：保存到 Obsidian + LightRAG
```

## 核心原则

1. **异步优先**：所有 I/O 使用 async/await
2. **类型完整**：函数必须有类型注解
3. **配置单例**：通过 `settings` 访问配置

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
