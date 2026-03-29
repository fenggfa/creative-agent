"""Harness 工具模块 - Harness Engineering 核心实现。

三大支柱：
1. 上下文工程 (Context Engineering) - AGENTS.md
2. 约束工程 (Constraint Engineering) - provider.py + rules.py
3. 反馈工程 (Feedback Engineering) - evaluator.py + e2e.py

高级要素：
- 持久化状态 (persistence) - 解决换班失忆
- E2E 验证 (e2e) - 打破纸面胜利
- 熵管理 (entropy) - AI 垃圾回收
- 文档治理 (docs) - 活着的文档
- 重试机制 (retry) - 反馈回路增强
- 学习模块 (learning) - 从失败中学习
- 反馈闭环 (feedback_loop) - 自动更新规则
- 智能体记忆 (agent_memory) - 经验持久化
"""

from src.harness.agent_memory import (
    AgentExperience,
    AgentMemory,
    MemoryEnhancedAgent,
    OutcomeType,
    PatternMatch,
    TaskCategory,
    get_agent_memory,
)
from src.harness.docs import (
    DocGardener,
    DocHealthReport,
    DocIssue,
    DocIssueType,
    DocLinter,
    run_doc_lint,
)
from src.harness.e2e import (
    E2ETestResult,
    E2EValidator,
    TestStatus,
    run_e2e_validation,
)
from src.harness.entropy import (
    EntropyCleaner,
    EntropyIssue,
    EntropyReport,
    EntropyScanner,
    IssueSeverity,
    run_entropy_check,
)
from src.harness.feedback_loop import (
    FeedbackCoordinator,
    FeedbackLoop,
    RuleUpdate,
    get_feedback_coordinator,
    process_feedback,
)
from src.harness.learning import (
    FailureAnalyzer,
    LearningEngine,
    LearningPattern,
    LearningSource,
    RuleProposer,
    RuleType,
    get_learning_engine,
    learn_from_failure,
)
from src.harness.provider import (
    ConstraintProvider,
    ParsedRules,
    get_constraint_provider,
    inject_constraints_to_state,
)
from src.harness.retry import (
    API_RETRY,
    LLM_RETRY,
    RetryConfig,
    retry,
)
from src.harness.verifier import (
    run_all_checks,
    verify_constraints,
    verify_tests,
    verify_types,
)

__all__ = [
    # Retry - 重试机制
    "retry",
    "RetryConfig",
    "LLM_RETRY",
    "API_RETRY",
    # Provider - 约束提供者
    "ConstraintProvider",
    "ParsedRules",
    "get_constraint_provider",
    "inject_constraints_to_state",
    # Verifier - 自动化验证
    "run_all_checks",
    "verify_constraints",
    "verify_tests",
    "verify_types",
    # E2E - 端到端验证
    "E2EValidator",
    "E2ETestResult",
    "TestStatus",
    "run_e2e_validation",
    # Entropy - 熵管理
    "EntropyScanner",
    "EntropyCleaner",
    "EntropyIssue",
    "EntropyReport",
    "IssueSeverity",
    "run_entropy_check",
    # Docs - 文档治理
    "DocLinter",
    "DocGardener",
    "DocIssue",
    "DocIssueType",
    "DocHealthReport",
    "run_doc_lint",
    # Learning - 学习模块
    "LearningEngine",
    "LearningPattern",
    "LearningSource",
    "RuleType",
    "FailureAnalyzer",
    "RuleProposer",
    "get_learning_engine",
    "learn_from_failure",
    # FeedbackLoop - 反馈闭环
    "FeedbackLoop",
    "FeedbackCoordinator",
    "RuleUpdate",
    "get_feedback_coordinator",
    "process_feedback",
    # AgentMemory - 智能体记忆
    "AgentMemory",
    "AgentExperience",
    "MemoryEnhancedAgent",
    "OutcomeType",
    "TaskCategory",
    "PatternMatch",
    "get_agent_memory",
]
