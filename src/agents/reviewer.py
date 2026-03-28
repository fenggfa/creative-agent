"""审核智能体 - 审核内容质量和一致性。"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings

# 审核智能体系统提示词
REVIEWER_SYSTEM_PROMPT = """你是一个专业的内容审核员。你的任务是审核创作内容是否符合要求。

审核标准：
1. 设定一致性：人物性格、能力是否与原作设定一致
2. 逻辑合理性：情节发展是否合理，是否存在明显漏洞
3. 内容质量：文笔是否流畅，描写是否生动
4. 任务完成度：是否完成了指定的创作任务

输出格式：
- 如果通过审核，输出：通过
- 如果需要修改，输出具体的问题和改进建议


请注意：你的输出必须严格遵循上述格式。如果审核通过，只输出"通过"二字；如果需要修改，请详细说明问题。"""


async def review(task: str, materials: str, draft: str) -> tuple[bool, str]:
    """
    审核创作内容。

    Args:
        task: 创作任务描述
        materials: 参考素材
        draft: 待审核的创作内容

    Returns:
        元组 (是否通过, 反馈内容)
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=60.0,
    )

    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""创作任务：{task}

参考素材：
{materials}

待审核内容：
{draft}

请审核以上内容，判断是否符合要求。"""
        ),
    ]

    response = await llm.ainvoke(messages)
    feedback = response.content

    # 检查是否通过
    is_approved = "通过" in feedback and len(feedback.strip()) <= 10

    return is_approved, feedback


# LangGraph 节点函数
async def reviewer_node(state: dict) -> dict:
    """审核智能体的 LangGraph 节点。"""
    task = state.get("task", "")
    materials = state.get("materials", "")
    draft = state.get("draft", "")

    is_approved, feedback = await review(task, materials, draft)

    return {
        "approved": is_approved,
        "review_feedback": feedback,
        "final_output": draft if is_approved else "",
    }
