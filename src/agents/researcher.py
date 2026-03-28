"""素材收集智能体 - 从 LightRAG 知识图谱检索相关素材。"""

from src.tools.lightrag import lightrag_client


async def research(task: str) -> str:
    """
    从知识图谱查询相关素材。

    LightRAG 已返回 LLM 生成的答案，无需额外处理。

    Args:
        task: 创作任务描述

    Returns:
        检索到的素材字符串
    """
    return await lightrag_client.query(
        query=task,
        mode="mix",
    )


# LangGraph 节点函数
async def researcher_node(state: dict) -> dict:
    """素材收集智能体的 LangGraph 节点。"""
    task = state.get("task", "")
    materials = await research(task)
    return {"materials": materials}
