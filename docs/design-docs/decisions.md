# 设计决策

> 存储系统的核心信念与架构选型，提供高维度背景上下文。

## ADR-001: 选择 LangGraph 作为工作流编排

**状态**: 已采纳

**背景**: 需要一个支持状态管理和条件分支的工作流引擎。

**决策**: 选择 LangGraph 而非 LangChain Chain。

**理由**:
- 原生支持状态持久化
- 支持循环和条件边
- 与 LangChain 生态兼容

**后果**:
- 需要学习 LangGraph 特有 API
- 状态定义需要严格类型化

---

## ADR-002: GAN 风格的生成-评估反馈

**状态**: 已采纳

**背景**: 需要自动评估生成内容的质量。

**决策**: 采用 GAN 的判别器思想设计评估器。

**理由**:
- 评估器保持"挑剔"态度
- 自动生成改进建议
- 支持迭代优化

**后果**:
- 评估器需要独立 LLM 调用
- 增加延迟但提高质量

---

## ADR-003: 异步优先架构

**状态**: 已采纳

**背景**: I/O 密集型应用，需要高并发。

**决策**: 所有 I/O 操作使用 async/await。

**理由**:
- Python 原生协程支持
- 与 LangChain 异步 API 兼容
- 便于后续扩展

**后果**:
- 代码风格统一
- 测试需要 pytest-asyncio

---

## ADR-004: pydantic-settings 配置管理

**状态**: 已采纳

**背景**: 需要类型安全的配置管理。

**决策**: 使用 pydantic-settings 加载环境变量。

**理由**:
- 类型验证
- 环境变量自动加载
- 支持默认值

**后果**:
- 配置集中管理
- 单例模式访问

---

## ADR-005: 约束注入管道架构

**状态**: 已采纳 (2026-03-28)

**背景**: AGENTS.md 定义了约束规则，但智能体代码没有读取和应用这些规则，存在架构断裂。

**决策**: 建立 ConstraintProvider → ConstraintChecker → ConstraintUpdateEngine 的约束注入管道。

**架构**:
```
AGENTS.md (约束源)
      │
      ▼
ConstraintProvider
      ├── parse_md_rules() - 解析 MD 提取规则
      ├── get_system_prompt_injection() - 生成提示词注入
      └── create_checker() - 创建检查器
      │
      ▼
Writer/Reviewer 智能体
      │
      ▼
ConstraintChecker
      │
      ▼
violations[]
      │
      ▼
ConstraintUpdateEngine (安全更新)
```

**理由**:
- 约束规则集中管理在 AGENTS.md
- 智能体动态获取约束注入
- 支持安全的约束规则更新
- 闭环反馈：检测违规 → 分析模式 → 提出更新

**后果**:
- 新增 harness/provider.py 和 harness/updater.py
- AgentState 扩展约束相关字段
- Writer/Reviewer 智能体需要集成约束检查

**安全机制**:

| 更新类型 | 风险 | 自动批准 |
|----------|------|----------|
| 添加禁止模式 | 低 | ✅ |
| 移除禁止模式 | 中 | ❌ |
| 修改质量阈值 | 高 | ❌ |
| 添加核心原则 | 高 | ❌ |
