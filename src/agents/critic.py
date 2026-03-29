"""批评审核师智能体 - 评估内容质量和一致性。

职责：
- 评估内容质量（五维评估）
- 检查约束违规
- 提出修改建议
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.feedback.evaluator import ContentEvaluator, EvaluationResult
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry

# 批评审核师系统提示词
CRITIC_SYSTEM_PROMPT = """你是专业的内容审核员，负责评估创作内容质量。

## 核心职责

1. **质量评估**：从多个维度评估内容质量
2. **一致性检查**：确保人物、设定、情节前后一致
3. **约束验证**：检查是否违反创作约束
4. **改进建议**：提供具体、可操作的修改建议

## 评估维度

1. **设定一致性**（20分）
   - 人物性格是否偏离设定
   - 世界观规则是否自洽
   - 能力体系是否一致

2. **情节合理性**（20分）
   - 逻辑是否通顺
   - 节奏是否恰当
   - 是否有明显漏洞

3. **文笔表现**（20分）
   - 语言是否流畅
   - 描写是否生动
   - 对话是否自然

4. **人物塑造**（20分）
   - 人物是否有个性
   - 行为动机是否合理
   - 成长弧线是否清晰

5. **阅读体验**（20分）
   - 是否吸引人
   - 情感是否共鸣
   - 是否有惊喜

## 输出格式

审核通过输出：通过

需要修改输出：
1. 问题列表
2. 具体改进建议
3. 修改优先级"""


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("critic")

    if constraint_injection:
        return f"{CRITIC_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return CRITIC_SYSTEM_PROMPT


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


@retry(config=LLM_RETRY)
async def review_chapter(
    chapter_num: int,
    chapter_outline: dict[str, Any],
    draft: str,
    character_states: dict[str, Any],
    violations: list[dict[str, Any]] | None = None,
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    审核章节内容（整书模式）。

    Args:
        chapter_num: 章节序号
        chapter_outline: 章节细纲
        draft: 章节内容
        character_states: 人物状态
        violations: 约束违规记录

    Returns:
        (是否通过, 反馈, 评估结果)
    """
    import json

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )

    system_prompt = _build_system_prompt()
    violation_context = _format_violations_for_context(violations or [])

    prompt = f"""请审核第 {chapter_num} 章内容。

## 章节细纲
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

## 人物当前状态
{json.dumps(character_states, ensure_ascii=False, indent=2)}

## 章节内容
{draft[:3000]}...

{violation_context}

请评估：
1. 内容是否符合章节细纲要求
2. 人物行为是否与状态一致
3. 是否有情节漏洞或逻辑问题
4. 文笔质量如何

输出格式：
- 通过：第一行只写"通过"
- 不通过：列出问题和改进建议"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    feedback = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 判断是否通过
    first_line = feedback.strip().split("\n")[0]
    is_approved = "通过" in first_line and "不通过" not in first_line

    # 简化的评估结果
    eval_result = {
        "chapter_num": chapter_num,
        "passed": is_approved,
        "feedback": feedback,
        "violations_count": len(violations) if violations else 0,
    }

    return is_approved, feedback, eval_result


async def review_single(
    task: str,
    materials: str,
    draft: str,
    violations: list[dict[str, Any]] | None = None,
    use_evaluator: bool = True,
) -> tuple[bool, str, EvaluationResult | None]:
    """
    单篇审核模式（兼容原有流程）。

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

        context: dict[str, Any] = {}
        if violations:
            context["violations"] = violations

        eval_result = await evaluator.evaluate(
            task=task,
            content=draft,
            materials=materials,
            context=context if context else None,
        )

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

    return await _review_with_llm(task, materials, draft, violations)


@retry(config=LLM_RETRY)
async def _review_with_llm(
    task: str,
    materials: str,
    draft: str,
    violations: list[dict[str, Any]] | None = None,
) -> tuple[bool, str, None]:
    """使用 LLM 进行简单审核。"""
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=60.0,
    )

    system_prompt = _build_system_prompt()
    violation_context = _format_violations_for_context(violations or [])

    prompt = f"""创作任务：{task}

参考素材：
{materials}

待审核内容：
{draft}
{violation_context}

请审核以上内容，判断是否符合要求。"""

    if not violation_context:
        prompt = prompt.replace("\n\n\n请审核", "\n\n请审核")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    feedback = raw_content if isinstance(raw_content, str) else str(raw_content)

    is_approved = "通过" in feedback and len(feedback.strip()) <= 10

    return is_approved, feedback, None


async def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    批评审核师的 LangGraph 节点。

    支持单篇模式和整书模式。
    集成学习闭环：审核失败时自动学习新规则。
    """
    book_mode = state.get("book_mode", False)

    if not book_mode:
        # 单篇模式
        task = state.get("task", "")
        materials = state.get("materials", "")
        draft = state.get("draft", "")
        violations = state.get("violations", [])

        is_approved, feedback, eval_result = await review_single(
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

        if eval_result:
            result["evaluation_result"] = _evaluation_result_to_dict(eval_result)

        # 学习闭环：失败时学习
        if not is_approved:
            await _learn_from_failure(
                agent_type="critic",
                violations=violations,
                evaluation_result=result.get("evaluation_result"),
                content=draft,
            )

        return result

    # 整书模式：审核章节
    current_chapter = state.get("current_chapter", 1)
    chapter_outline = state.get("_current_chapter_outline", {})
    draft = state.get("draft", "")
    character_states = state.get("character_states", {})
    violations = state.get("violations", [])

    is_approved, feedback, chapter_eval = await review_chapter(
        chapter_num=current_chapter,
        chapter_outline=chapter_outline,
        draft=draft,
        character_states=character_states,
        violations=violations,
    )

    result = {
        "approved": is_approved,
        "review_feedback": feedback,
    }

    if chapter_eval:
        # 添加到审核历史
        review_history = state.get("review_history", [])
        review_history.append(chapter_eval)
        result["review_history"] = review_history

    # 学习闭环：失败时学习
    if not is_approved:
        await _learn_from_failure(
            agent_type="critic",
            violations=violations,
            evaluation_result=chapter_eval,
            content=draft,
        )

    return result


async def _learn_from_failure(
    agent_type: str,
    violations: list[dict[str, Any]],
    evaluation_result: dict[str, Any] | None,
    content: str,
) -> None:
    """从失败中学习，提取新规则。"""
    try:
        from src.harness import learn_from_failure, process_feedback

        # 从违规中学习
        if violations:
            await learn_from_failure(violations, agent_type, {"content": content[:500]})

        # 从评估失败中学习
        if evaluation_result and not evaluation_result.get("passed", True):
            await process_feedback(agent_type, violations, evaluation_result)

    except Exception as e:
        # 学习失败不影响主流程，但记录日志
        import logging

        logging.warning(f"学习失败: {e}")
