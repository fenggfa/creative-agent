"""创作智能体 - 基于收集的素材创作内容。"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings

# 创作智能体系统提示词
WRITER_SYSTEM_PROMPT = """你是一个专业的创意写作者。你的任务是根据提供的素材创作精彩的内容。

你的职责：
1. 深入理解素材中的人物设定、背景故事、世界观
2. 创作符合设定、逻辑自洽的内容
3. 注重细节描写、人物性格塑造和情节张力

创作原则：
- 忠实于原作设定，不随意改变人物性格和能力
- 情节合理，符合逻辑
- 语言生动，富有感染力
- 适当创新，但保持原作风格"""


async def write(task: str, materials: str, previous_draft: str = "", feedback: str = "") -> str:
    """
    根据任务和素材创作内容。

    Args:
        task: 创作任务描述
        materials: 收集的参考素材
        previous_draft: 上一版草稿（修改时使用）
        feedback: 审核反馈（修改时使用）

    Returns:
        创作的内容字符串
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=120.0,  # 创作任务需要较长超时
    )

    if previous_draft and feedback:
        # 修改模式
        prompt = f"""创作任务：{task}

参考素材：
{materials}

上一版草稿：
{previous_draft}

审核反馈：
{feedback}

请根据审核反馈修改上一版草稿，保持原有优点的同时改进不足之处。"""
    else:
        # 初次创作模式
        prompt = f"""创作任务：{task}

参考素材：
{materials}

请根据以上素材，完成创作任务。"""

    messages = [
        SystemMessage(content=WRITER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    return response.content


# LangGraph 节点函数
async def writer_node(state: dict) -> dict:
    """创作智能体的 LangGraph 节点。"""
    task = state.get("task", "")
    materials = state.get("materials", "")
    previous_draft = state.get("draft", "")
    feedback = state.get("review_feedback", "")

    draft = await write(task, materials, previous_draft, feedback)

    result = {"draft": draft}
    if state.get("revision_count"):
        result["revision_count"] = state["revision_count"] + 1
    else:
        result["revision_count"] = 1

    return result
