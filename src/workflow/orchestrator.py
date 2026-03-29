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

import os
import re
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.writer import writer_node
from src.config import settings
from src.output import clean_final_output, save_creative_output
from src.workflow.state import AgentState


def _clean_console_output(content: str) -> str:
    """清理控制台输出内容。"""
    if not content:
        return content

    # 移除 <...> 标签
    cleaned = re.sub(r"<>", "", content)
    cleaned = re.sub(r"</>", "", cleaned)

    # 移除 References 部分
    cleaned = re.sub(
        r"\n---\s*\n###?\s*References?\s*\n.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 移除写作说明部分
    cleaned = re.sub(
        r"\n---\s*\n\*\*写作说明\*\*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # 移除连续空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


async def output_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    输出节点：保存创作内容到 Obsidian 和 LightRAG。

    使用服务层直接调用，不依赖工具选择，100%可靠。
    """
    task = state.get("task", "")
    draft = state.get("draft", "")
    source_work = state.get("source_work", "西游记")

    # 清理内容，只保留正文
    cleaned_draft = clean_final_output(draft)

    # 保存内容
    result = await save_creative_output(
        content=cleaned_draft,
        task=task,
        source_work=source_work,
        evaluation=state.get("evaluation_result"),
    )

    # 更新状态
    final_output = cleaned_draft
    if result.get("success"):
        final_output = f"{cleaned_draft}\n\n---\n\n✅ 已保存到图谱和 Obsidian"

    output_state: dict[str, Any] = {
        "final_output": final_output,
        "output_result": result,
        "lightrag_saved": result.get("lightrag", {}).get("success", False),
    }

    # 可选：E2E 验证（通过环境变量控制）
    if os.environ.get("HARNESS_E2E"):
        e2e_results = await _run_e2e_validation()
        if e2e_results:
            output_state["e2e_results"] = e2e_results

    return output_state


async def _run_e2e_validation() -> list[str] | None:
    """运行 E2E 验证（可选）。"""
    try:
        from src.harness import E2EValidator

        validator = E2EValidator()
        results = await validator.run_all_tests()

        # 返回通过的功能 ID
        passed_features = [
            r.feature_id for r in results
            if r.status.value == "passed"
        ]

        if passed_features:
            print(f"\n✅ E2E 验证通过: {passed_features}")

        return passed_features

    except Exception as e:
        print(f"\n⚠️ E2E 验证失败: {e}")
        return None


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


def create_workflow() -> StateGraph[AgentState]:
    """
    创建多智能体工作流图。

    流程:
        START → researcher → writer → reviewer → output → END
                                  ↑          │
                                  └──────────┘ (审核不通过时修改)
    """
    # 创建工作流图
    workflow: StateGraph[AgentState] = StateGraph(AgentState)

    # 添加节点（type: ignore 因为 LangGraph 的类型系统与我们的节点函数签名不完全匹配）
    workflow.add_node("researcher", researcher_node)  # type: ignore[type-var]
    workflow.add_node("writer", writer_node)  # type: ignore[type-var]
    workflow.add_node("reviewer", reviewer_node)  # type: ignore[type-var]
    workflow.add_node("output", output_node)  # type: ignore[type-var]

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


def compile_workflow() -> Any:
    """编译并返回工作流应用。"""
    workflow = create_workflow()
    return workflow.compile()


# 预编译的工作流实例
app: Any = compile_workflow()
