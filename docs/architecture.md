# 系统架构

> 严格约束依赖方向、代码分层与模块边界。

## 分层架构

```
┌─────────────────────────────────────────────────────┐
│               CLI (main.py)                         │
├─────────────────────────────────────────────────────┤
│            Workflow (orchestrator)                  │
├──────────┬──────────┬───────────────┬──────────────┤
│Researcher│  Writer  │   Reviewer    │              │
│          │    ↓     │      ↓        │              │
│          │Constraint│  ContentEval  │              │
│          │ Checker  │    uator      │              │
├──────────┴──────────┴───────────────┴──────────────┤
│              Tools (lightrag, file_ops)             │
├─────────────────────────────────────────────────────┤
│    Constraints │ Feedback │ Harness (Provider/Upd)  │
└─────────────────────────────────────────────────────┘
                           ↑
                      AGENTS.md
                     (约束源)
```

## 约束注入管道

```
AGENTS.md (约束源)
      │
      ▼ ConstraintProvider.parse_md_rules()
      │
ParsedRules
├── core_principles: list[str]
├── forbidden_patterns: list[str]
├── constraints_boundary: dict
└── passing_criteria: dict
      │
      ▼ get_system_prompt_injection(agent_type)
      │
系统提示词注入 ──→ Writer / Reviewer
      │
      ▼ ConstraintChecker.run_all_checks()
      │
violations[] ──→ ConstraintUpdateEngine
                      │
                      ▼ 安全更新机制
```

## 依赖方向

```
CLI → Workflow → Agents → Tools
                  ↓
           Constraints / Feedback / Harness
                  ↓
                AGENTS.md
```

**红线**: 下层不得依赖上层，Tools 不得依赖 Agents。

## 模块边界

| 模块 | 职责 | 依赖 |
|------|------|------|
| agents | 智能体逻辑 | tools, config, harness |
| tools | 外部服务集成 | config |
| workflow | 状态编排 | agents |
| constraints | 规则检查 | 无外部依赖 |
| feedback | 内容评估 | config |
| harness | 约束注入、验证 | constraints, feedback |

## 状态定义

```python
class AgentState(TypedDict, total=False):
    # 创作流程
    task: str
    materials: str
    draft: str
    review_feedback: str
    approved: bool
    revision_count: int
    final_output: str

    # 约束注入 (2026-03-28 新增)
    constraints_injected: bool
    constraint_rules: dict[str, Any]
    violations: list[dict[str, Any]]
    evaluation_result: dict[str, Any] | None
```

## 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| MAX_REVISIONS | 2 | 最大修改次数 |
| LLM_TIMEOUT | 120s | LLM 超时 |
| MIN_LENGTH | 100 | 最小内容长度 |

## Harness 组件

| 组件 | 文件 | 职责 |
|------|------|------|
| ConstraintProvider | harness/provider.py | 解析 AGENTS.md，注入系统提示词 |
| ConstraintUpdateEngine | harness/updater.py | 安全更新约束规则 |
| HarnessVerifier | harness/verifier.py | 自动化验证检查 |
