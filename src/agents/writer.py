"""创作智能体 - 基于收集的素材创作内容。

Harness 集成：
- 约束注入：通过 get_constraint_provider()
- 重试机制：@retry 装饰器
- 学习闭环：从失败中学习，获取历史教训
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.harness import OutcomeType, TaskCategory, get_agent_memory, learn_from_failure
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry

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


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("writer")

    if constraint_injection:
        return f"{WRITER_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return WRITER_SYSTEM_PROMPT


def _check_constraints(content: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """检查内容是否符合约束规则。

    Args:
        content: 待检查的内容
        context: 检查上下文

    Returns:
        违规记录列表
    """
    provider = get_constraint_provider()
    checker = provider.create_checker()

    violations = checker.run_all_checks(content, context)

    # 转换为可序列化的字典格式
    return [
        {
            "rule_name": v.rule_name,
            "severity": v.severity.value,
            "message": v.message,
            "position": v.position,
            "suggestion": v.suggestion,
        }
        for v in violations
    ]


def _get_lessons_for_writer() -> list[str]:
    """获取创作智能体的历史教训。"""
    try:
        memory = get_agent_memory()
        return memory.get_lessons_learned("writer", OutcomeType.FAILURE)
    except Exception:
        return []


async def _record_writer_outcome(
    task: str,
    content: str,
    violations: list[dict[str, Any]],
    success: bool,
) -> None:
    """记录创作结果，用于学习闭环。"""
    import logging

    try:
        memory = get_agent_memory()
        if success:
            memory.record_experience(
                agent_type="writer",
                task_category=TaskCategory.CREATION,
                task_description=task,
                outcome=OutcomeType.SUCCESS,
                result_summary=f"创作内容 {len(content)} 字符",
                score=1.0 if not violations else 0.7,
                reusable_patterns=[f"成功完成任务: {task[:50]}"],
            )
        else:
            await learn_from_failure(
                violations,
                "writer",
                {"task": task, "content_length": len(content)},
            )
    except Exception as e:
        logging.debug(f"记录创作结果失败: {e}")


@retry(config=LLM_RETRY)
async def write(
    task: str,
    materials: str,
    previous_draft: str = "",
    feedback: str = "",
    check_constraints: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """
    根据任务和素材创作内容。

    Args:
        task: 创作任务描述
        materials: 收集的参考素材
        previous_draft: 上一版草稿（修改时使用）
        feedback: 审核反馈（修改时使用）
        check_constraints: 是否检查约束

    Returns:
        元组 (创作的内容, 违规记录列表)
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=120.0,  # 创作任务需要较长超时
    )

    # 构建带有约束注入的系统提示词
    system_prompt = _build_system_prompt()

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
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    # 处理响应内容类型
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 检查约束
    violations: list[dict[str, Any]] = []
    if check_constraints:
        violations = _check_constraints(content)

    return content, violations


# LangGraph 节点函数
async def writer_node(state: dict[str, Any]) -> dict[str, Any]:
    """创作智能体的 LangGraph 节点。

    Harness 集成：
    - 重试机制：@retry 装饰器
    - 学习闭环：记录成功/失败经验
    - 历史教训：获取并应用历史经验
    """
    task = state.get("task", "")
    materials = state.get("materials", "")
    previous_draft = state.get("draft", "")
    feedback = state.get("review_feedback", "")

    # 获取历史教训
    lessons = _get_lessons_for_writer()

    # 在反馈中加入历史教训
    enhanced_feedback = feedback
    if lessons and previous_draft:  # 修改时提醒
        enhanced_feedback = f"{feedback}\n\n历史经验提醒：\n" + "\n".join(
            f"- {lesson}" for lesson in lessons[:3]
        )

    draft, violations = await write(task, materials, previous_draft, enhanced_feedback)

    result: dict[str, Any] = {
        "draft": draft,
        "violations": violations,
    }

    if state.get("revision_count"):
        result["revision_count"] = state["revision_count"] + 1
    else:
        result["revision_count"] = 1

    # 记录结果用于学习
    success = len(violations) == 0
    await _record_writer_outcome(task, draft, violations, success)

    return result
