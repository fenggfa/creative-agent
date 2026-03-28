"""素材收集智能体 - 从 LightRAG 知识图谱检索相关素材。

架构设计：
===========================================

第一层：固定流程（推荐）
  - fetch_materials_for_writing() - 直接调用，100%可靠

第二层：工具调用（可选）
  - research_with_tools() - LLM 选择工具，适合动态场景
"""

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.tools.graph_service import (
    GRAPH_TOOLS,
    fetch_materials_for_writing,
)

# ============================================================================
# 方案一：直接调用（固定流程，推荐）
# ============================================================================


async def research(task: str) -> str:
    """
    获取创作素材（固定流程）。

    直接调用服务层函数，不经过 LLM 选择，100%可靠。

    Args:
        task: 创作任务描述

    Returns:
        检索到的素材字符串
    """
    return await fetch_materials_for_writing(task)


# ============================================================================
# 方案二：工具调用（动态场景，可选）
# ============================================================================

RESEARCHER_PROMPT = """你是素材研究员。

工具说明：
- ask_knowledge_graph: 向知识图谱提问

使用场景：
- 用户问"图谱里有什么" → 调用 ask_knowledge_graph
- 用户问"查一下xxx" → 调用 ask_knowledge_graph

注意：如果是创作前的素材收集，不需要调用工具，直接返回结果即可。
"""


def create_researcher_agent() -> Any:
    """创建支持工具调用的研究智能体。"""
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.1,
    )

    agent = create_react_agent(
        llm,
        GRAPH_TOOLS,
        prompt=RESEARCHER_PROMPT,
    )

    return agent


async def research_with_tools(task: str) -> str:
    """
    使用工具调用进行研究（动态场景）。

    注意：对于固定流程（创作前获取素材），
    应该直接调用 research() 而不是这个函数。

    Args:
        task: 任务描述

    Returns:
        结果
    """
    agent = create_researcher_agent()

    try:
        result = await agent.ainvoke({
            "messages": [HumanMessage(content=task)]
        })

        messages = result.get("messages", [])
        if messages:
            return str(messages[-1].content)
        return ""

    except Exception:
        # 回退到直接调用
        return await research(task)


# ============================================================================
# LangGraph 节点
# ============================================================================


async def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    素材收集智能体的 LangGraph 节点。

    默认使用固定流程（100%可靠），
    可通过 use_tools=True 启用工具调用模式。
    """
    task = state.get("task", "")
    use_tools = state.get("use_tools", False)

    if use_tools:
        # 动态场景：让 LLM 选择工具
        materials = await research_with_tools(task)
    else:
        # 固定流程：直接调用（推荐）
        materials = await research(task)

    return {"materials": materials}
