"""知识图谱服务层 - 直接编程 + 可选工具调用。

设计理念：
===========================================

对于固定流程 → 直接编程（100%可靠）
对于动态决策 → 工具调用（LLM 选择）

为什么这样设计？
- 创作前查询图谱：固定流程，不需要 LLM 选择
- 创作后保存图谱：固定流程，不需要 LLM 选择
- 用户自由提问：动态决策，需要工具调用

优点：
1. 固定流程准确率：100%（代码控制，不依赖 LLM 选择）
2. 动态场景灵活性：LLM 可以自由探索图谱
3. 实现简单：核心流程不需要 Agent

"""

from __future__ import annotations

import asyncio
from datetime import datetime

from langchain_core.tools import tool

from src.tools.lightrag import creative_lightrag_client, lightrag_client

# ============================================================================
# 第一层：直接编程 API（固定流程，100%可靠）
# ============================================================================


async def fetch_materials_for_writing(task: str) -> str:
    """
    获取创作所需的素材（固定流程，不依赖 LLM 选择）。

    这是 Researcher 智能体应该直接调用的函数，
    不需要通过工具调用让 LLM "选择"。

    Args:
        task: 创作任务

    Returns:
        格式化的素材内容
    """
    if not task or len(task.strip()) < 2:
        return "任务描述太短"

    task = task.strip()

    # 固定流程：并发查询两个图谱
    material_task = lightrag_client.query(task)
    creative_task = creative_lightrag_client.query(task)

    material_result, creative_result = await asyncio.gather(
        material_task, creative_task, return_exceptions=True
    )

    # 格式化输出
    parts = []

    if not isinstance(material_result, Exception) and material_result:
        parts.append("=== 【素材图谱】原作设定 ===")
        parts.append(str(material_result))

    if not isinstance(creative_result, Exception) and creative_result:
        if parts:
            parts.append("")
        parts.append("=== 【二创图谱】创作演绎 ===")
        parts.append("")
        parts.append("⚠️ 如与原作冲突，以此为准。")
        parts.append(str(creative_result))

    if not parts:
        return f"未找到「{task}」相关设定，可自由创作。"

    return "\n".join(parts)


async def save_creative_content(
    content: str,
    title: str,
    metadata: dict | None = None,
) -> dict:
    """
    保存创作内容到二创图谱（固定流程，不依赖 LLM 选择）。

    这是 Output 模块应该直接调用的函数。

    Args:
        content: 创作内容
        title: 标题
        metadata: 可选元数据

    Returns:
        保存结果
    """
    if not content or len(content.strip()) < 20:
        return {"success": False, "error": "内容太短"}

    if not title or not title.strip():
        return {"success": False, "error": "标题不能为空"}

    # 固定流程：格式化 + 保存
    enriched = f"""【{title}】
创作时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{f'元数据: {metadata}' if metadata else ''}

{content.strip()}"""

    try:
        success = await creative_lightrag_client.insert(enriched)
        return {
            "success": success,
            "title": title,
            "message": "保存成功" if success else "保存失败",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# 第二层：工具定义（动态决策场景，LLM 选择）
# ============================================================================

# 只有在用户自由提问、需要动态决策时才需要工具调用
# 例如：用户问"图谱里有哪些角色？"、"帮我查一下孙悟空的朋友有哪些？"


@tool
async def ask_knowledge_graph(question: str) -> str:
    """
    向知识图谱提问（用于用户自由提问场景）。

    适用场景：
    - 用户问"图谱里有什么？"
    - 用户问"查一下孙悟空的关系网络"
    - 用户自由探索图谱

    不适用场景：
    - 创作前的素材收集 → 用 fetch_materials_for_writing
    - 创作后的内容保存 → 用 save_creative_content

    Args:
        question: 问题

    Returns:
        图谱回答
    """
    if not question or len(question.strip()) < 2:
        return "问题太短，请提供更具体的问题"

    # 自动决定查哪个图谱
    question = question.strip()

    # 如果问题涉及"创作"、"章节"、"之前"，优先查二创图谱
    creative_keywords = ["创作", "章节", "之前", "已经", "写过"]
    use_creative = any(kw in question for kw in creative_keywords)

    if use_creative:
        return await creative_lightrag_client.query(question)
    else:
        # 默认查双图谱
        return await fetch_materials_for_writing(question)


# ============================================================================
# 工具导出
# ============================================================================

# 固定流程用的函数（推荐直接调用）
__all__ = [
    "fetch_materials_for_writing",  # 创作前获取素材
    "save_creative_content",  # 创作后保存内容
    "ask_knowledge_graph",  # 用户自由提问（工具）
]

# 工具列表（仅在需要 LLM 选择时使用）
GRAPH_TOOLS = [ask_knowledge_graph]
