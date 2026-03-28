"""多智能体工作流状态定义。"""

from typing import TypedDict


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
