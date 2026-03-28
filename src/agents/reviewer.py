"""审核智能体 - 审核内容质量和一致性。"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.feedback.evaluator import ContentEvaluator, EvaluationResult
from src.harness.provider import get_constraint_provider

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


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("reviewer")

    if constraint_injection:
        return f"{REVIEWER_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return REVIEWER_SYSTEM_PROMPT


def _format_violations_for_context(violations: list[dict[str, Any]]) -> str:
    """格式化违规信息用于评估上下文。"""
    if not violations:
        return ""

    lines = ["## 约束检查发现的问题", ""]
    for v in violations:
        severity = v.get("severity", "unknown")
        message = v.get("message", "")
        suggestion = v.get("suggestion", "")
        lines.append(f"- [{severity.upper()}] {message}")
        if suggestion:
            lines.append(f"  建议: {suggestion}")

    return "\n".join(lines)


def _evaluation_result_to_dict(result: EvaluationResult) -> dict[str, Any]:
    """将评估结果转换为字典格式。"""
    return {
        "total_score": result.total_score,
        "passed": result.passed,
        "overall_feedback": result.overall_feedback,
        "improvement_suggestions": result.improvement_suggestions,
        "scores": [
            {
                "dimension": s.dimension.value,
                "score": s.score,
                "reasoning": s.reasoning,
                "issues": s.issues,
            }
            for s in result.scores
        ],
    }


async def review(
    task: str,
    materials: str,
    draft: str,
    violations: list[dict[str, Any]] | None = None,
    use_evaluator: bool = True,
) -> tuple[bool, str, EvaluationResult | None]:
    """
    审核创作内容。

    Args:
        task: 创作任务描述
        materials: 参考素材
        draft: 待审核的创作内容
        violations: 约束违规记录
        use_evaluator: 是否使用 ContentEvaluator

    Returns:
        元组 (是否通过, 反馈内容, 评估结果)
    """
    # 使用 ContentEvaluator 进行评估
    if use_evaluator:
        evaluator = ContentEvaluator()

        # 构建评估上下文
        context: dict[str, Any] = {}
        if violations:
            context["violations"] = violations

        # 执行评估
        eval_result = await evaluator.evaluate(
            task=task,
            content=draft,
            materials=materials,
            context=context if context else None,
        )

        # 构建反馈
        if eval_result.passed:
            feedback = "通过"
        else:
            feedback_parts = [eval_result.overall_feedback]
            if eval_result.improvement_suggestions:
                feedback_parts.append("\n改进建议：")
                for i, suggestion in enumerate(eval_result.improvement_suggestions, 1):
                    feedback_parts.append(f"{i}. {suggestion}")
            feedback = "\n".join(feedback_parts)

        return eval_result.passed, feedback, eval_result

    # 使用简单的 LLM 审核
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=60.0,
    )

    # 构建带有约束注入的系统提示词
    system_prompt = _build_system_prompt()

    # 添加违规信息到提示词
    violation_context = _format_violations_for_context(violations or [])

    prompt = f"""创作任务：{task}

参考素材：
{materials}

待审核内容：
{draft}
{violation_context}

请审核以上内容，判断是否符合要求。"""

    # 如果没有违规信息，移除空行
    if not violation_context:
        prompt = prompt.replace("\n\n\n请审核", "\n\n请审核")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    # 处理响应内容类型
    raw_content = response.content
    feedback = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 检查是否通过
    is_approved = "通过" in feedback and len(feedback.strip()) <= 10

    return is_approved, feedback, None


# LangGraph 节点函数
async def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
    """审核智能体的 LangGraph 节点。"""
    task = state.get("task", "")
    materials = state.get("materials", "")
    draft = state.get("draft", "")
    violations = state.get("violations", [])

    is_approved, feedback, eval_result = await review(
        task=task,
        materials=materials,
        draft=draft,
        violations=violations,
        use_evaluator=True,
    )

    result: dict[str, Any] = {
        "approved": is_approved,
        "review_feedback": feedback,
        "final_output": draft if is_approved else "",
    }

    # 保存评估结果
    if eval_result:
        result["evaluation_result"] = _evaluation_result_to_dict(eval_result)

    return result
