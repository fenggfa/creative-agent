"""故事架构师智能体 - 设计整书大纲和章节结构。

职责：
- 设计整书大纲和章节结构
- 规划情节线索和伏笔
- 设计情感曲线和节奏

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

PLOT_ARCHITECT_SYSTEM_PROMPT = """你是专业的故事架构师，负责设计整书大纲和情节结构。

## 核心职责

1. **结构设计**：设计整书的章节结构和节奏
2. **情节规划**：规划主情节和支线的交织
3. **伏笔布局**：巧妙埋设伏笔，控制揭晓节奏
4. **情感曲线**：设计情感起伏，确保张弛有度

## 大纲设计原则

### 开篇（前10%）
- 快速建立世界观
- 引入主角和核心冲突
- 制造悬念吸引读者

### 发展（10%-50%）
- 主线推进 + 支线交织
- 人物成长弧线
- 阶段性小高潮

### 高潮（50%-90%）
- 矛盾激化
- 关键抉择
- 情感爆发

### 结局（最后10%）
- 主线收束
- 伏笔揭晓
- 余韵悠长

## 输出格式

整书大纲采用 JSON 格式，包含：
- title: 书名
- theme: 主题
- total_chapters: 总章节数
- chapters: 各章概要
- plot_threads: 情节线索
- main_characters: 主要人物"""


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("plot_architect")

    if constraint_injection:
        return f"{PLOT_ARCHITECT_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return PLOT_ARCHITECT_SYSTEM_PROMPT


def _get_lessons_for_architect() -> list[str]:
    """获取故事架构师的历史教训。"""
    try:
        memory = get_agent_memory()
        return memory.get_lessons_learned("plot_architect", OutcomeType.FAILURE)
    except Exception:
        return []


async def _record_architect_outcome(
    task: str,
    success: bool,
    outline: dict[str, Any] | None = None,
    error: str = "",
) -> None:
    """记录架构师结果，用于学习闭环。"""
    import logging

    try:
        memory = get_agent_memory()
        if success and outline:
            memory.record_experience(
                agent_type="plot_architect",
                task_category=TaskCategory.PLANNING,
                task_description=task,
                outcome=OutcomeType.SUCCESS,
                result_summary=f"生成大纲: {outline.get('title', '')}",
                score=1.0,
                reusable_patterns=[f"成功设计: {outline.get('title', '')}"],
            )
        else:
            await learn_from_failure(
                [{"error": error, "task": task}],
                "plot_architect",
                {"outline": outline},
            )
    except Exception as e:
        logging.debug(f"记录架构师结果失败: {e}")


@retry(config=LLM_RETRY)
async def generate_book_outline(
    task: str,
    plan: dict[str, Any],
    world_setting: dict[str, Any] | None = None,
    character_profiles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    生成整书大纲。

    Args:
        task: 创作任务
        plan: 创作计划（来自 Director）
        world_setting: 世界观设定（可选）
        character_profiles: 人物档案（可选）

    Returns:
        整书大纲字典
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.7,
    )

    import json

    # 构建上下文
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    context_parts = [f"创作任务：{task}", "", f"创作计划：{plan_json}"]

    if world_setting:
        world_json = json.dumps(world_setting, ensure_ascii=False, indent=2)
        context_parts.append(f"\n世界观设定：\n{world_json}")

    if character_profiles:
        char_names = list(character_profiles.keys())
        context_parts.append(f"\n主要人物：\n{json.dumps(char_names, ensure_ascii=False)}")

    context = "\n".join(context_parts)

    prompt = f"""{context}

请设计整书大纲。

要求：
1. 总章节数：{plan.get('estimated_chapters', 10)} 章左右
2. 风格：{plan.get('style', '通用')}
3. 题材：{plan.get('genre', '未知')}

请输出 JSON 格式的大纲：
{{
    "title": "书名",
    "theme": "核心主题",
    "total_chapters": 章节数,
    "chapters": [
        {{
            "chapter_num": 1,
            "title": "章节标题",
            "summary": "章节概要（50-100字）",
            "key_events": ["关键事件1", "关键事件2"],
            "pov_character": "视角人物",
            "emotional_tone": "情感基调"
        }}
    ],
    "plot_threads": [
        {{
            "thread_id": "thread_1",
            "description": "情节线索描述",
            "start_chapter": 起始章节,
            "end_chapter": 结束章节,
            "importance": "main/sub"
        }}
    ],
    "main_characters": ["主角", "配角1", "配角2"],
    "foreshadowing_plan": [
        {{
            "content": "伏笔内容",
            "plant_chapter": 埋设章节,
            "reveal_chapter": 揭晓章节
        }}
    ],
    "emotional_curve": [
        {{"chapter": 1, "intensity": 5, "emotion": "好奇"}},
        {{"chapter": 5, "intensity": 8, "emotion": "紧张"}}
    ]
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

        outline: dict[str, Any] = json.loads(json_str)
        return outline
    except (json.JSONDecodeError, IndexError, KeyError):
        import json

        # 返回默认大纲
        return {
            "title": plan.get("intent", "未命名作品")[:20],
            "theme": plan.get("core_appeal", ""),
            "total_chapters": plan.get("estimated_chapters", 10),
            "chapters": [
                {
                    "chapter_num": i,
                    "title": f"第{i}章",
                    "summary": "",
                    "key_events": [],
                    "pov_character": "",
                    "emotional_tone": "中性",
                }
                for i in range(1, plan.get("estimated_chapters", 10) + 1)
            ],
            "plot_threads": [],
            "main_characters": list(character_profiles.keys()) if character_profiles else [],
            "foreshadowing_plan": [],
            "emotional_curve": [],
        }


@retry(config=LLM_RETRY)
async def refine_chapter_outline(
    chapter_num: int,
    book_outline: dict[str, Any],
    previous_chapters: list[dict[str, Any]],
    feedback: str = "",
) -> dict[str, Any]:
    """
    优化单个章节的细纲。

    Args:
        chapter_num: 章节序号
        book_outline: 整书大纲
        previous_chapters: 前文章节摘要
        feedback: 反馈意见（修改时使用）

    Returns:
        优化后的章节细纲
    """
    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.6,
    )

    import json

    # 获取当前章节的基本信息
    chapters = book_outline.get("chapters", [])
    current_chapter: dict[str, Any] = next(
        (c for c in chapters if c.get("chapter_num") == chapter_num), {}
    )

    prompt = f"""请优化第 {chapter_num} 章的细纲。

整书大纲概要：
- 书名：{book_outline.get('title', '')}
- 主题：{book_outline.get('theme', '')}
- 总章节：{book_outline.get('total_chapters', 10)}

当前章节基本信息：
{json.dumps(current_chapter, ensure_ascii=False, indent=2)}

前文章节概要：
{json.dumps(previous_chapters[-3:] if len(previous_chapters) > 3 else previous_chapters)}

{"反馈意见：" + feedback if feedback else ""}

请输出 JSON 格式的章节细纲：
{{
    "chapter_num": {chapter_num},
    "title": "章节标题",
    "summary": "章节概要",
    "scenes": [
        {{
            "scene_num": 1,
            "location": "场景地点",
            "characters": ["出场人物"],
            "action": "场景内容描述",
            "dialogue_focus": ["关键对话主题"],
            "outcome": "场景结果"
        }}
    ],
    "key_events": ["关键事件"],
    "character_developments": {{"人物": "发展变化"}},
    "foreshadowing_to_plant": ["要埋的伏笔"],
    "foreshadowing_to_reveal": ["要揭的伏笔"],
    "cliffhanger": "结尾悬念",
    "word_count_estimate": 预估字数
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

        result: dict[str, Any] = json.loads(json_str)
        return result
    except (json.JSONDecodeError, IndexError):
        # 返回基本细纲
        return {
            "chapter_num": chapter_num,
            "title": current_chapter.get("title", f"第{chapter_num}章"),
            "summary": current_chapter.get("summary", ""),
            "scenes": [],
            "key_events": current_chapter.get("key_events", []),
            "character_developments": {},
            "foreshadowing_to_plant": [],
            "foreshadowing_to_reveal": [],
            "cliffhanger": "",
            "word_count_estimate": 3000,
        }


async def plot_architect_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    故事架构师的 LangGraph 节点。

    根据当前阶段生成或优化大纲。

    Harness 集成：
    - 重试机制：@retry 装饰器
    - 学习闭环：记录成功/失败经验
    - 历史教训：获取并应用历史经验
    """
    task = state.get("task", "")
    book_mode = state.get("book_mode", False)
    current_chapter = state.get("current_chapter", 0)

    # 获取历史教训
    lessons = _get_lessons_for_architect()

    if not book_mode:
        return {}

    # 获取创作计划
    plan = state.get("_creation_plan", {})

    try:
        # 如果没有大纲，生成整书大纲
        if not state.get("book_outline"):
            outline = await generate_book_outline(
                task=task,
                plan=plan,
                world_setting=state.get("world_setting"),
                character_profiles=state.get("character_profiles"),
            )

            # 记录成功
            await _record_architect_outcome(task, success=True, outline=outline)

            return {"book_outline": outline}

        # 如果有当前章节，生成章节细纲
        if current_chapter > 0:
            book_outline = state.get("book_outline", {})
            chapter_summaries = state.get("chapter_summaries", {})
            previous_chapters = [
                s for s in chapter_summaries.values()
                if s.get("chapter_num", 0) < current_chapter
            ]

            chapter_outline = await refine_chapter_outline(
                chapter_num=current_chapter,
                book_outline=book_outline,
                previous_chapters=previous_chapters,
            )

            # 记录成功
            await _record_architect_outcome(
                f"{task} - 章节{current_chapter}",
                success=True,
                outline=chapter_outline,
            )

            return {"_current_chapter_outline": chapter_outline}

        return {}

    except Exception as e:
        # 记录失败
        await _record_architect_outcome(task, success=False, error=str(e))

        # 如果有历史教训，提供提示
        if lessons:
            return {
                "error": str(e),
                "lessons": lessons[:3],
            }
        raise
