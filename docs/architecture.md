# 系统架构

> 严格约束依赖方向、代码分层与模块边界。

## 分层架构

```
┌─────────────────────────────────────┐
│         CLI (main.py)               │
├─────────────────────────────────────┤
│      Workflow (orchestrator)        │
├──────────┬──────────┬───────────────┤
│ Researcher│  Writer │   Reviewer    │
├──────────┴──────────┴───────────────┤
│        Tools (lightrag)             │
├─────────────────────────────────────┤
│   Constraints │ Feedback │ Harness  │
└─────────────────────────────────────┘
```

## 依赖方向

```
CLI → Workflow → Agents → Tools
                  ↓
           Constraints / Feedback / Harness
```

**红线**: 下层不得依赖上层，Tools 不得依赖 Agents。

## 模块边界

| 模块 | 职责 | 依赖 |
|------|------|------|
| agents | 智能体逻辑 | tools, config |
| tools | 外部服务集成 | config |
| workflow | 状态编排 | agents |
| constraints | 规则检查 | 无外部依赖 |
| feedback | 内容评估 | config |
| harness | 自动化验证 | constraints, feedback |

## 状态定义

```python
class WorkflowState(TypedDict):
    task: str
    materials: str
    draft: str
    review_feedback: str
    revision_count: int
    approved: bool
```

## 配置项

| 配置 | 默认值 | 说明 |
|------|--------|------|
| MAX_REVISIONS | 2 | 最大修改次数 |
| LLM_TIMEOUT | 120s | LLM 超时 |
| MIN_LENGTH | 100 | 最小内容长度 |
