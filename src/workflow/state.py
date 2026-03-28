"""多智能体工作流状态定义。"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """智能体之间传递的工作流状态。"""

    # 创作任务
    task: str
    # 收集的素材
    materials: str
    # 创作内容
    draft: str
    # 审核反馈
    review_feedback: str
    # 审核是否通过
    approved: bool
    # 修改次数
    revision_count: int
    # 最终输出
    final_output: str

    # === 约束注入相关字段 ===
    # 约束是否已注入
    constraints_injected: bool
    # 当前生效的约束规则
    constraint_rules: dict[str, Any]
    # 约束违规记录
    violations: list[dict[str, Any]]
    # 评估结果
    evaluation_result: dict[str, Any] | None

    # === 输出相关字段 (2026-03-28 新增) ===
    # 原作名称（如"西游记"）
    source_work: str
    # Obsidian 保存路径
    obsidian_path: str
    # LightRAG 保存状态
    lightrag_saved: bool
    # 输出结果汇总
    output_result: dict[str, Any]
