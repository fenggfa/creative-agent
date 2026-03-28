"""使用 LangGraph 编排工作流。"""

from langgraph.graph import END, StateGraph

from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.writer import writer_node
from src.config import settings
from src.workflow.state import AgentState


def should_continue(state: AgentState) -> str:
    """
    判断是否继续修改或结束工作流。

    Returns:
        需要修改返回 "writer"，通过或达到最大修改次数返回 "end"
    """
    if state.get("approved", False):
        return "end"

    revision_count = state.get("revision_count", 0)
    if revision_count >= settings.MAX_REVISIONS:
        # 达到最大修改次数，接受当前草稿
        return "end"

    return "writer"


def create_workflow() -> StateGraph:
    """
    创建多智能体工作流图。

    流程:
        START → researcher → writer → reviewer → END
                              ↑          │
                              └──────────┘ (审核不通过时修改)
    """
    # 创建工作流图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)

    # 添加边
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", "reviewer")

    # 从 reviewer 添加条件边
    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {
            "writer": "writer",
            "end": END,
        },
    )

    return workflow


def compile_workflow():
    """编译并返回工作流应用。"""
    workflow = create_workflow()
    return workflow.compile()


# 预编译的工作流实例
app = compile_workflow()
