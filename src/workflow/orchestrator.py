"""使用 LangGraph 编排工作流。

工作流架构：
===========================================

START → researcher → writer → reviewer → output → END
                            ↑          │
                            └──────────┘ (审核不通过时修改)

固定流程（直接调用，100%可靠）：
- researcher: fetch_materials_for_writing()
- output: save_creative_output()
"""

from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.writer import writer_node
from src.config import settings
from src.output import save_creative_output
from src.workflow.state import AgentState


async def output_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    输出节点：保存创作内容到 Obsidian 和 LightRAG。

    使用服务层直接调用，不依赖工具选择，100%可靠。
    """
    task = state.get("task", "")
    draft = state.get("draft", "")
    source_work = state.get("source_work", "西游记")

    # 保存内容
    result = await save_creative_output(
        content=draft,
        task=task,
        source_work=source_work,
        evaluation=state.get("evaluation_result"),
    )

    # 更新状态
    final_output = draft
    if result.get("success"):
        final_output = f"{draft}\n\n---\n\n✅ 已保存到图谱和 Obsidian"

    return {
        "final_output": final_output,
        "output_result": result,
        "lightrag_saved": result.get("lightrag", {}).get("success", False),
    }


def should_continue(state: AgentState) -> str:
    """
    判断是否继续修改或结束工作流。

    Returns:
        需要修改返回 "writer"，通过或达到最大修改次数返回 "output"
    """
    if state.get("approved", False):
        return "output"  # 审核通过，进入输出阶段

    revision_count = state.get("revision_count", 0)
    if revision_count >= settings.MAX_REVISIONS:
        # 达到最大修改次数，进入输出阶段
        return "output"

    return "writer"


def create_workflow() -> StateGraph:
    """
    创建多智能体工作流图。

    流程:
        START → researcher → writer → reviewer → output → END
                                  ↑          │
                                  └──────────┘ (审核不通过时修改)
    """
    # 创建工作流图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("output", output_node)

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
            "output": "output",
        },
    )

    # output 节点连接到 END
    workflow.add_edge("output", END)

    return workflow


def compile_workflow():
    """编译并返回工作流应用。"""
    workflow = create_workflow()
    return workflow.compile()


# 预编译的工作流实例
app = compile_workflow()
