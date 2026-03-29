"""总监制智能体 - 统筹全书创作流程。

职责：
- 解析用户创作意图，制定创作计划
- 协调各专业智能体的工作流程
- 把控全书进度和整体品质
- 决定何时进入下一章节、何时需要重写
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry

DIRECTOR_SYSTEM_PROMPT = """你是创意写作团队的总监制，负责统筹整书创作流程。

## 核心职责

1. **任务解析**：理解用户创作意图，明确创作目标
2. **流程协调**：决定何时调用各专业智能体
3. **质量把控**：判断内容是否达标，决定是否重写
4. **进度管理**：追踪章节进度，确保创作按计划推进

## 工作流程

### 策划阶段
1. 分析创作任务，确定风格、题材、篇幅
2. 指导故事架构师生成大纲
3. 确认世界观设定和人物档案

### 创作阶段
1. 为每个章节制定细纲
2. 监督写稿师完成章节撰写
3. 审核批评审核师的反馈，决定是否修改
4. 检查连贯性，确保跨章节一致

### 收尾阶段
1. 全书一致性检查
2. 生成目录、索引
3. 输出最终成果

## 决策原则

- **质量优先**：宁可重写，不留硬伤
- **一致性第一**：人物性格、设定不能前后矛盾
- **节奏把控**：注意情节张弛，避免流水账
- **读者视角**：始终考虑阅读体验"""


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("director")

    if constraint_injection:
        return f"{DIRECTOR_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return DIRECTOR_SYSTEM_PROMPT


@retry(config=LLM_RETRY)
async def analyze_task(task: str) -> dict[str, Any]:
    """
    分析创作任务，返回创作计划。

    Args:
        task: 用户创作任务描述

    Returns:
        创作计划字典，包含：
        - intent: 创作意图
        - genre: 题材类型
        - style: 文风
        - estimated_chapters: 预估章节数
        - key_elements: 关键元素
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )

    prompt = f"""分析以下创作任务，制定创作计划。

创作任务：
{task}

请输出 JSON 格式的创作计划：
{{
    "intent": "创作意图（一句话概括）",
    "genre": "题材类型（如：玄幻、都市、历史）",
    "style": "文风（如：轻松搞笑、严肃史诗、热血爽文）",
    "estimated_chapters": 预估章节数（整数），
    "key_elements": ["关键元素1", "关键元素2", ...],
    "target_audience": "目标读者",
    "core_appeal": "核心卖点"
}}"""

    messages = [
        SystemMessage(content=_build_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 解析 JSON
    import json

    try:
        # 尝试提取 JSON 块
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        plan: dict[str, Any] = json.loads(json_str)
        return plan
    except (json.JSONDecodeError, IndexError):
        # 返回默认计划
        return {
            "intent": task[:50] + "..." if len(task) > 50 else task,
            "genre": "未知",
            "style": "通用",
            "estimated_chapters": 10,
            "key_elements": [],
            "target_audience": "一般读者",
            "core_appeal": "精彩故事",
        }


@retry(config=LLM_RETRY)
async def approve_outline(outline: dict[str, Any], plan: dict[str, Any]) -> tuple[bool, str]:
    """
    审核大纲，决定是否通过。

    Args:
        outline: 大纲内容
        plan: 创作计划

    Returns:
        (是否通过, 反馈意见)
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )

    import json

    prompt = f"""请审核以下创作大纲，判断是否合格。

创作计划：
{json.dumps(plan, ensure_ascii=False, indent=2)}

大纲内容：
{json.dumps(outline, ensure_ascii=False, indent=2)}

审核标准：
1. 章节结构是否完整
2. 情节推进是否合理
3. 是否有明确的伏笔和线索
4. 是否符合创作计划的风格和目标

请输出：
- 第一行：通过 / 不通过
- 后续：具体反馈意见"""

    messages = [
        SystemMessage(content=_build_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    first_line = content.strip().split("\n")[0]
    approved = "通过" in first_line and "不通过" not in first_line

    return approved, content


@retry(config=LLM_RETRY)
async def approve_chapter(
    chapter_num: int,
    chapter_content: str,
    chapter_summary: dict[str, Any],
    context: dict[str, Any],
) -> tuple[bool, str]:
    """
    审核章节，决定是否通过或需要修改。

    Args:
        chapter_num: 章节序号
        chapter_content: 章节内容
        chapter_summary: 章节摘要
        context: 上下文（前文摘要、人物状态等）

    Returns:
        (是否通过, 反馈意见)
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )

    import json

    context_str = json.dumps(context, ensure_ascii=False, indent=2)

    prompt = f"""请审核第 {chapter_num} 章内容。

章节摘要：
{json.dumps(chapter_summary, ensure_ascii=False, indent=2)}

上下文信息：
{context_str}

章节内容（前500字）：
{chapter_content[:500]}...

审核标准：
1. 内容是否符合章节大纲
2. 人物行为是否一致
3. 是否有明显的情节漏洞
4. 文风是否符合预期

请输出：
- 第一行：通过 / 不通过
- 后续：具体反馈意见"""

    messages = [
        SystemMessage(content=_build_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    first_line = content.strip().split("\n")[0]
    approved = "通过" in first_line and "不通过" not in first_line

    return approved, content


@retry(config=LLM_RETRY)
async def generate_chapter_outline(
    chapter_num: int,
    book_outline: dict[str, Any],
    character_states: dict[str, Any],
    previous_events: list[str],
) -> dict[str, Any]:
    """
    为指定章节生成细纲。

    Args:
        chapter_num: 章节序号
        book_outline: 整书大纲
        character_states: 当前人物状态
        previous_events: 前文关键事件

    Returns:
        章节细纲
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.7,
    )

    import json

    prompt = f"""请为第 {chapter_num} 章生成详细大纲。

整书大纲：
{json.dumps(book_outline, ensure_ascii=False, indent=2)}

当前人物状态：
{json.dumps(character_states, ensure_ascii=False, indent=2)}

前文关键事件：
{json.dumps(previous_events, ensure_ascii=False, indent=2)}

请输出 JSON 格式的章节细纲：
{{
    "chapter_num": {chapter_num},
    "title": "章节标题",
    "summary": "本章摘要（一句话）",
    "scenes": [
        {{
            "location": "场景地点",
            "characters": ["出场人物"],
            "action": "场景动作",
            "outcome": "场景结果"
        }}
    ],
    "key_events": ["关键事件1", "关键事件2"],
    "character_developments": {{"人物名": "发展变化"}},
    "foreshadowing": ["伏笔（如果有）"],
    "cliffhanger": "章节悬念（可选）"
}}"""

    messages = [
        SystemMessage(content=_build_system_prompt()),
        HumanMessage(content=prompt),
    ]

    response = await llm.ainvoke(messages)
    raw_content = response.content
    content = raw_content if isinstance(raw_content, str) else str(raw_content)

    # 解析 JSON
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        chapter_outline: dict[str, Any] = json.loads(json_str)
        return chapter_outline
    except (json.JSONDecodeError, IndexError):
        # 返回基本大纲
        chapters = book_outline.get("chapters", [])
        chapter_info = next(
            (c for c in chapters if c.get("chapter_num") == chapter_num),
            {"title": f"第{chapter_num}章", "summary": ""},
        )
        return {
            "chapter_num": chapter_num,
            "title": chapter_info.get("title", f"第{chapter_num}章"),
            "summary": chapter_info.get("summary", ""),
            "scenes": [],
            "key_events": [],
            "character_developments": {},
            "foreshadowing": [],
            "cliffhanger": "",
        }


async def director_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    总监制智能体的 LangGraph 节点。

    根据当前状态决定下一步操作。
    """
    task = state.get("task", "")
    book_mode = state.get("book_mode", False)

    if not book_mode:
        # 单篇模式，直接返回（由原有流程处理）
        return {"materials": state.get("materials", "")}

    # 整书模式：分析任务
    plan = await analyze_task(task)

    return {
        "book_mode": True,
        "task": task,
        "current_chapter": 0,
        "chapter_contents": {},
        "chapter_summaries": {},
        "character_states": {},
        "plot_threads": {},
        "foreshadowing": [],
        "review_history": [],
        # 存储创作计划供后续使用
        "_creation_plan": plan,
    }
