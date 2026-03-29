"""风格写稿师智能体 - 根据大纲和设定撰写正文。

职责：
- 根据大纲和设定撰写正文
- 保持指定文风（如轻松搞笑、严肃史诗）
- 实现场景描写、对话、心理活动
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry

# 风格写稿师系统提示词
PROSE_WRITER_SYSTEM_PROMPT = """你是专业的创意写作者，负责根据大纲和设定撰写正文。

## 核心职责

1. **场景描写**：生动的环境、动作、对话
2. **人物刻画**：通过言行展现性格
3. **情节推进**：紧凑有力，避免拖沓
4. **文风保持**：始终如一的语言风格

## 写作原则

### 描写技巧
- 环境描写要简洁有画面感
- 对话要符合人物性格
- 心理活动要自然不突兀
- 动作描写要流畅有节奏

### 节奏把控
- 重要场景放慢节奏，详写
- 过渡场景加快节奏，略写
- 留悬念要适度，不故弄玄虚

### 禁忌
- 不要让人物OOC（偏离设定）
- 不要突然改变文风
- 不要忘记前文伏笔
- 不要让情节前后矛盾"""


def _build_system_prompt(style: str = "") -> str:
    """构建带有约束注入的系统提示词。"""
    base_prompt = PROSE_WRITER_SYSTEM_PROMPT

    if style:
        style_addition = f"\n\n## 当前文风要求\n{style}"
        base_prompt += style_addition

    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("prose_writer")

    if constraint_injection:
        return f"{base_prompt}\n\n{constraint_injection}"
    return base_prompt


def _check_constraints(content: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """检查内容是否符合约束规则。"""
    provider = get_constraint_provider()
    checker = provider.create_checker()

    violations = checker.run_all_checks(content, context)

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


@retry(config=LLM_RETRY)
async def write_chapter(
    chapter_outline: dict[str, Any],
    world_setting: dict[str, Any],
    character_profiles: dict[str, Any],
    character_states: dict[str, Any],
    previous_context: str,
    style: str = "",
    previous_draft: str = "",
    feedback: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """
    根据章节细纲撰写正文。

    Args:
        chapter_outline: 章节细纲
        world_setting: 世界观设定
        character_profiles: 人物档案
        character_states: 当前人物状态
        previous_context: 前文上下文（摘要）
        style: 文风要求
        previous_draft: 上一版草稿（修改时使用）
        feedback: 审核反馈（修改时使用）

    Returns:
        元组 (章节内容, 违规记录列表)
    """
    import json

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.8,  # 创作任务需要较高温度
        timeout=180.0,
    )

    system_prompt = _build_system_prompt(style)

    # 构建上下文
    context_parts = []

    # 章节细纲
    outline_json = json.dumps(chapter_outline, ensure_ascii=False, indent=2)
    context_parts.append(f"## 章节细纲\n{outline_json}")

    # 世界观（精简）
    if world_setting:
        world_summary = dict(list(world_setting.items())[:5])
        world_json = json.dumps(world_summary, ensure_ascii=False, indent=2)
        context_parts.append(f"\n## 世界观要点\n{world_json}")

    # 相关人物
    chapter_chars = chapter_outline.get("scenes", [])
    char_names = set()
    for scene in chapter_chars:
        char_names.update(scene.get("characters", []))

    relevant_profiles = {
        k: v for k, v in character_profiles.items() if k in char_names
    }
    if relevant_profiles:
        profiles_json = json.dumps(relevant_profiles, ensure_ascii=False, indent=2)
        context_parts.append(f"\n## 本章出场人物\n{profiles_json}")

    # 人物当前状态
    relevant_states = {
        k: v for k, v in character_states.items() if k in char_names
    }
    if relevant_states:
        states_json = json.dumps(relevant_states, ensure_ascii=False, indent=2)
        context_parts.append(f"\n## 人物当前状态\n{states_json}")

    # 前文上下文
    if previous_context:
        context_parts.append(f"\n## 前文回顾\n{previous_context}")

    context = "\n".join(context_parts)

    # 构建提示词
    if previous_draft and feedback:
        prompt = f"""{context}

## 上一版草稿
{previous_draft[:2000]}...

## 修改要求
{feedback}

请根据章节细纲和修改要求，修改上一版草稿。保持原有优点的同时改进不足之处。"""
    else:
        prompt = f"""{context}

请根据以上章节细纲和设定，撰写第 {chapter_outline.get('chapter_num', 1)} 章正文。

要求：
1. 字数：约 {chapter_outline.get('word_count_estimate', 3000)} 字
2. 按照细纲中的场景顺序写作
3. 注意人物行为符合设定和当前状态
4. 结尾留下：{chapter_outline.get('cliffhanger', '自然过渡到下一章')}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 检查约束
    violations = _check_constraints(content)

    return content, violations


@retry(config=LLM_RETRY)
async def write_single(
    task: str,
    materials: str,
    previous_draft: str = "",
    feedback: str = "",
    check_constraints: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """
    单篇创作模式（兼容原有流程）。

    Args:
        task: 创作任务描述
        materials: 收集的参考素材
        previous_draft: 上一版草稿
        feedback: 审核反馈
        check_constraints: 是否检查约束

    Returns:
        元组 (创作的内容, 违规记录列表)
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=120.0,
    )

    system_prompt = _build_system_prompt()

    if previous_draft and feedback:
        prompt = f"""创作任务：{task}

参考素材：
{materials}

上一版草稿：
{previous_draft}

审核反馈：
{feedback}

请根据审核反馈修改上一版草稿，保持原有优点的同时改进不足之处。"""
    else:
        prompt = f"""创作任务：{task}

参考素材：
{materials}

请根据以上素材，完成创作任务。"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    violations: list[dict[str, Any]] = []
    if check_constraints:
        violations = _check_constraints(content)

    return content, violations


async def prose_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    风格写稿师的 LangGraph 节点。

    支持单篇模式和整书模式。
    集成记忆系统：参考历史经验，记录写作经验。
    """
    book_mode = state.get("book_mode", False)

    # 获取历史教训（帮助避免重复错误）
    lessons = _get_lessons_for_writer()

    if not book_mode:
        # 单篇模式：使用原有逻辑
        task = state.get("task", "")
        materials = state.get("materials", "")
        previous_draft = state.get("draft", "")
        feedback = state.get("review_feedback", "")

        # 在反馈中加入历史教训
        enhanced_feedback = feedback
        if lessons and not previous_draft:  # 首次写作时提醒
            enhanced_feedback = f"{feedback}\n\n历史经验提醒：\n" + "\n".join(
                f"- {lesson}" for lesson in lessons[:3]
            )

        draft, violations = await write_single(task, materials, previous_draft, enhanced_feedback)

        result: dict[str, Any] = {
            "draft": draft,
            "violations": violations,
        }

        if state.get("revision_count"):
            result["revision_count"] = state["revision_count"] + 1
        else:
            result["revision_count"] = 1

        return result

    # 整书模式：撰写章节
    chapter_outline = state.get("_current_chapter_outline", {})
    if not chapter_outline:
        return {"draft": ""}

    world_setting = state.get("world_setting", {})
    character_profiles = state.get("character_profiles", {})
    character_states = state.get("character_states", {})
    book_outline = state.get("book_outline", {})
    style = book_outline.get("style", "")

    # 构建前文上下文
    chapter_summaries = state.get("chapter_summaries", {})
    current_chapter = state.get("current_chapter", 1)
    previous_summaries = [
        chapter_summaries[i].get("summary", "")
        for i in sorted(chapter_summaries.keys())
        if i < current_chapter
    ]
    previous_context = "\n".join(previous_summaries[-3:])  # 最近3章摘要

    # 获取修改信息
    previous_draft = state.get("draft", "")
    feedback = state.get("review_feedback", "")

    # 在反馈中加入历史教训
    enhanced_feedback = feedback
    if lessons and previous_draft:  # 修改时提醒
        enhanced_feedback = f"{feedback}\n\n历史经验提醒：\n" + "\n".join(
            f"- {lesson}" for lesson in lessons[:3]
        )

    draft, violations = await write_chapter(
        chapter_outline=chapter_outline,
        world_setting=world_setting,
        character_profiles=character_profiles,
        character_states=character_states,
        previous_context=previous_context,
        style=style,
        previous_draft=previous_draft,
        feedback=enhanced_feedback,
    )

    result = {
        "draft": draft,
        "violations": violations,
    }

    if state.get("revision_count"):
        result["revision_count"] = state["revision_count"] + 1
    else:
        result["revision_count"] = 1

    return result


def _get_lessons_for_writer() -> list[str]:
    """获取写稿师的历史教训。"""
    try:
        from src.harness import OutcomeType, get_agent_memory

        memory = get_agent_memory()
        return memory.get_lessons_learned("prose_writer", OutcomeType.FAILURE)
    except Exception:
        return []
