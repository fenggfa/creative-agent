"""素材收集智能体 - 从知识图谱检索相关素材。

架构设计：
===========================================

第一层：固定流程（推荐）
  - fetch_materials_for_writing() - 直接调用，100%可靠

第二层：工具调用（可选）
  - research_with_tools() - LLM 选择工具，适合动态场景

Harness 集成：
- 约束注入：通过 get_constraint_provider()
- 重试机制：@retry 装饰器
- 学习闭环：从失败中学习，获取历史教训
"""

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.config import settings
from src.harness import OutcomeType, TaskCategory, get_agent_memory, learn_from_failure
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry
from src.tools.graph_service import (
    GRAPH_TOOLS,
    fetch_materials_for_writing,
)

# ============================================================================
# 方案一：直接调用（固定流程，推荐）
# ============================================================================


@retry(config=LLM_RETRY)
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


def _build_researcher_prompt() -> str:
    """构建带有约束注入的研究员提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("researcher")

    if constraint_injection:
        return f"{RESEARCHER_PROMPT}\n\n{constraint_injection}"
    return RESEARCHER_PROMPT


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
        prompt=_build_researcher_prompt(),
    )

    return agent


@retry(config=LLM_RETRY)
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


def _get_lessons_for_researcher() -> list[str]:
    """获取研究员的历史教训。"""
    try:
        memory = get_agent_memory()
        return memory.get_lessons_learned("researcher", OutcomeType.FAILURE)
    except Exception:
        return []


async def _record_research_outcome(
    task: str,
    materials: str,
    success: bool,
    error: str = "",
) -> None:
    """记录研究结果，用于学习闭环。"""
    import logging

    try:
        memory = get_agent_memory()
        if success:
            memory.record_experience(
                agent_type="researcher",
                task_category=TaskCategory.ANALYSIS,
                task_description=task,
                outcome=OutcomeType.SUCCESS,
                result_summary=f"获取素材 {len(materials)} 字符",
                score=1.0 if len(materials) > 100 else 0.5,
            )
        else:
            await learn_from_failure(
                [{"error": error, "task": task}],
                "researcher",
                {"materials_length": len(materials)},
            )
    except Exception as e:
        logging.debug(f"记录研究结果失败: {e}")


async def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    素材收集智能体的 LangGraph 节点。

    默认使用固定流程（100%可靠），
    可通过 use_tools=True 启用工具调用模式。

    Harness 集成：
    - 重试机制：@retry 装饰器
    - 学习闭环：记录成功/失败经验
    - 历史教训：获取并应用历史经验
    """
    task = state.get("task", "")
    use_tools = state.get("use_tools", False)

    # 获取历史教训
    lessons = _get_lessons_for_researcher()

    try:
        if use_tools:
            # 动态场景：让 LLM 选择工具
            materials = await research_with_tools(task)
        else:
            # 固定流程：直接调用（推荐）
            materials = await research(task)

        # 记录成功
        await _record_research_outcome(task, materials, success=True)

        return {"materials": materials}

    except Exception as e:
        # 记录失败
        await _record_research_outcome(task, "", success=False, error=str(e))

        # 如果有历史教训，尝试返回提示
        if lessons:
            lesson_text = "\n".join(f"- {lesson}" for lesson in lessons[:3])
            return {
                "materials": f"素材获取失败。历史经验提示：\n{lesson_text}",
                "research_error": str(e),
            }
        raise
