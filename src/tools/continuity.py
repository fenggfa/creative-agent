"""连贯性守护工具模块。

提供人物状态追踪、情节线索追踪、设定冲突检测、章节摘要生成。
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.workflow.state import ChapterSummary, CharacterState, Foreshadowing, PlotThread


class CharacterStateTracker:
    """人物状态追踪器。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.3,
        )

    async def update_states(
        self,
        chapter_num: int,
        chapter_content: str,
        current_states: dict[str, CharacterState],
        character_profiles: dict[str, Any],
    ) -> dict[str, CharacterState]:
        """
        根据章节内容更新人物状态。

        Args:
            chapter_num: 章节序号
            chapter_content: 章节内容
            current_states: 当前人物状态
            character_profiles: 人物档案

        Returns:
            更新后的人物状态
        """
        # 获取本章涉及的人物
        involved_chars = []
        for name in character_profiles:
            if name in chapter_content:
                involved_chars.append(name)

        if not involved_chars:
            return current_states

        prompt = f"""分析以下章节内容，更新人物状态。

章节内容（前2000字）：
{chapter_content[:2000]}...

涉及人物：{involved_chars}

当前人物状态：
{json.dumps(current_states, ensure_ascii=False, indent=2)}

请输出 JSON 格式的人物状态更新：
{{
    "人物名": {{
        "name": "人物名",
        "location": "当前位置",
        "mood": "情绪状态",
        "relationships": {{"其他人物": "关系状态"}},
        "current_goal": "当前目标",
        "last_appearance": {chapter_num},
        "development_notes": ["发展变化记录"]
    }}
}}

只输出有变化的人物状态。"""

        messages = [
            SystemMessage(content="你是人物状态分析专家，负责追踪小说中人物的变化。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            content = raw_content if isinstance(raw_content, str) else str(raw_content)

            # 解析 JSON
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            updates = json.loads(json_str)

            # 合并更新
            new_states = dict(current_states)
            for name, state in updates.items():
                if name in new_states:
                    # 合并发展记录
                    existing_notes = new_states[name].get("development_notes", [])
                    new_notes = state.get("development_notes", [])
                    state["development_notes"] = existing_notes + new_notes
                new_states[name] = state

            return new_states

        except (json.JSONDecodeError, IndexError, KeyError):
            # 解析失败，返回原状态
            return current_states

    def get_state_summary(self, states: dict[str, CharacterState]) -> str:
        """获取人物状态摘要。"""
        if not states:
            return "暂无人物状态记录。"

        lines = ["## 人物状态摘要", ""]
        for name, state in states.items():
            lines.append(f"**{name}**")
            lines.append(f"- 位置: {state.get('location', '未知')}")
            lines.append(f"- 情绪: {state.get('mood', '未知')}")
            lines.append(f"- 目标: {state.get('current_goal', '无')}")
            lines.append("")

        return "\n".join(lines)


class PlotThreadTracker:
    """情节线索追踪器。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.3,
        )

    async def update_threads(
        self,
        chapter_num: int,
        chapter_content: str,
        current_threads: dict[str, PlotThread],
    ) -> dict[str, PlotThread]:
        """
        根据章节内容更新情节线索。

        Args:
            chapter_num: 章节序号
            chapter_content: 章节内容
            current_threads: 当前情节线索

        Returns:
            更新后的情节线索
        """
        prompt = f"""分析以下章节内容，更新情节线索状态。

章节内容（前2000字）：
{chapter_content[:2000]}...

当前情节线索：
{json.dumps(current_threads, ensure_ascii=False, indent=2)}

请分析：
1. 哪些线索在本章有进展
2. 是否有新线索开始
3. 是否有线索被解决或放弃

输出 JSON 格式的更新：
{{
    "updated": {{
        "线索ID": {{
            "thread_id": "线索ID",
            "description": "线索描述",
            "status": "active/resolved/abandoned",
            "chapters_involved": [涉及的章节号],
            "key_events": ["关键事件"]
        }}
    }},
    "new": [
        {{
            "thread_id": "新线索ID",
            "description": "新线索描述",
            "status": "active",
            "chapters_involved": [{chapter_num}],
            "key_events": ["起始事件"]
        }}
    ]
}}"""

        messages = [
            SystemMessage(content="你是情节分析专家，负责追踪小说中的情节线索。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            content = raw_content if isinstance(raw_content, str) else str(raw_content)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            updates = json.loads(json_str)

            # 合并更新
            new_threads = dict(current_threads)

            # 更新现有线索
            for thread_id, thread in updates.get("updated", {}).items():
                new_threads[thread_id] = thread

            # 添加新线索
            for thread in updates.get("new", []):
                thread_id = thread.get("thread_id", f"thread_{len(new_threads) + 1}")
                new_threads[thread_id] = thread

            return new_threads

        except (json.JSONDecodeError, IndexError, KeyError):
            return current_threads

    def get_active_threads(self, threads: dict[str, PlotThread]) -> list[PlotThread]:
        """获取活跃的情节线索。"""
        return [t for t in threads.values() if t.get("status") == "active"]


class ConflictDetector:
    """设定冲突检测器。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.2,
        )

    async def check_chapter_conflicts(
        self,
        chapter_content: str,
        world_setting: dict[str, Any],
        character_profiles: dict[str, Any],
        character_states: dict[str, CharacterState],
        previous_chapters: list[str],
    ) -> list[dict[str, Any]]:
        """
        检测章节内容中的设定冲突。

        Args:
            chapter_content: 章节内容
            world_setting: 世界观设定
            character_profiles: 人物档案
            character_states: 人物当前状态
            previous_chapters: 前文章节摘要

        Returns:
            冲突列表
        """
        prompt = f"""检测以下章节内容中的设定冲突。

章节内容：
{chapter_content[:2000]}...

世界观设定：
{json.dumps(world_setting, ensure_ascii=False, indent=2)[:500]}...

人物档案：
{json.dumps(list(character_profiles.keys()), ensure_ascii=False)}

人物当前状态：
{json.dumps(character_states, ensure_ascii=False, indent=2)}

前文摘要：
{chr(10).join(previous_chapters[-3:])}

请检测以下类型的冲突：
1. 人物行为偏离设定
2. 世界观规则违反
3. 与前文情节矛盾
4. 时间线错误
5. 人物位置不一致

输出 JSON 格式的冲突报告：
{{
    "conflicts": [
        {{
            "type": "冲突类型",
            "severity": "high/medium/low",
            "description": "冲突描述",
            "location": "在内容中的位置",
            "suggestion": "修复建议"
        }}
    ],
    "warnings": [
        "可能的问题（不一定是冲突）"
    ]
}}"""

        messages = [
            SystemMessage(content="你是设定一致性检查专家，负责检测小说中的设定冲突。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            content = raw_content if isinstance(raw_content, str) else str(raw_content)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            result: dict[str, Any] = json.loads(json_str)
            conflicts: list[dict[str, Any]] = result.get("conflicts", [])
            return conflicts

        except (json.JSONDecodeError, IndexError, KeyError):
            return []


class ChapterSummarizer:
    """章节摘要生成器。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.3,
        )

    async def summarize(
        self,
        chapter_num: int,
        chapter_title: str,
        chapter_content: str,
    ) -> ChapterSummary:
        """
        生成章节摘要。

        Args:
            chapter_num: 章节序号
            chapter_title: 章节标题
            chapter_content: 章节内容

        Returns:
            章节摘要
        """
        prompt = f"""请为以下章节生成摘要。

章节：第{chapter_num}章 {chapter_title}

内容：
{chapter_content[:3000]}...

请输出 JSON 格式的摘要：
{{
    "chapter_num": {chapter_num},
    "title": "{chapter_title}",
    "summary": "100字以内的章节摘要",
    "key_events": ["关键事件1", "关键事件2", "关键事件3"],
    "character_changes": {{
        "人物名": "本章中的变化"
    }}
}}"""

        messages = [
            SystemMessage(content="你是专业的内容摘要专家，负责为小说章节生成精炼的摘要。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            content = raw_content if isinstance(raw_content, str) else str(raw_content)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            summary: ChapterSummary = json.loads(json_str)
            return summary

        except (json.JSONDecodeError, IndexError, KeyError):
            return {
                "chapter_num": chapter_num,
                "title": chapter_title,
                "summary": chapter_content[:100] + "...",
                "key_events": [],
                "character_changes": {},
            }

    async def get_context_for_chapter(
        self,
        chapter_num: int,
        chapter_summaries: dict[int, ChapterSummary],
        max_chapters: int = 3,
    ) -> str:
        """
        获取指定章节的前文上下文。

        Args:
            chapter_num: 目标章节序号
            chapter_summaries: 所有章节摘要
            max_chapters: 最多包含的章节数

        Returns:
            前文上下文字符串
        """
        previous_summaries = [
            chapter_summaries[i]
            for i in sorted(chapter_summaries.keys())
            if i < chapter_num
        ][-max_chapters:]

        if not previous_summaries:
            return "这是第一章，没有前文。"

        lines = []
        for summary in previous_summaries:
            lines.append(f"第{summary['chapter_num']}章 {summary['title']}")
            lines.append(summary['summary'])
            if summary.get('key_events'):
                lines.append(f"关键事件: {', '.join(summary['key_events'])}")
            lines.append("")

        return "\n".join(lines)


class ForeshadowingTracker:
    """伏笔追踪器。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.3,
        )

    async def detect_and_track(
        self,
        chapter_num: int,
        chapter_content: str,
        current_foreshadowing: list[Foreshadowing],
    ) -> tuple[list[Foreshadowing], list[Foreshadowing]]:
        """
        检测并追踪伏笔。

        Args:
            chapter_num: 章节序号
            chapter_content: 章节内容
            current_foreshadowing: 当前伏笔列表

        Returns:
            (更新后的伏笔列表, 本章揭晓的伏笔)
        """
        prompt = f"""分析以下章节内容，检测伏笔。

章节内容：
{chapter_content[:2000]}...

当前伏笔追踪：
{json.dumps(current_foreshadowing, ensure_ascii=False, indent=2)}

请分析：
1. 本章是否有新伏笔
2. 是否有伏笔在本章揭晓
3. 揭晓是否合理

输出 JSON 格式：
{{
    "new_foreshadowing": [
        {{
            "content": "伏笔内容",
            "chapter_planted": {chapter_num},
            "chapter_to_reveal": 预计揭晓章节,
            "revealed": false,
            "notes": "备注"
        }}
    ],
    "revealed": [
        {{
            "content": "已揭晓的伏笔内容",
            "chapter_planted": 埋设章节,
            "chapter_to_reveal": {chapter_num},
            "revealed": true,
            "notes": "揭晓方式"
        }}
    ]
}}"""

        messages = [
            SystemMessage(content="你是伏笔分析专家，负责追踪小说中的伏笔埋设和揭晓。"),
            HumanMessage(content=prompt),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            raw_content = response.content
            content = raw_content if isinstance(raw_content, str) else str(raw_content)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)

            # 合并更新
            new_list = list(current_foreshadowing)
            new_list.extend(result.get("new_foreshadowing", []))

            # 标记已揭晓
            revealed_contents = {r.get("content") for r in result.get("revealed", [])}
            for f in new_list:
                if f.get("content") in revealed_contents:
                    f["revealed"] = True

            return new_list, result.get("revealed", [])

        except (json.JSONDecodeError, IndexError, KeyError):
            return current_foreshadowing, []


# 导出工具类
__all__ = [
    "CharacterStateTracker",
    "PlotThreadTracker",
    "ConflictDetector",
    "ChapterSummarizer",
    "ForeshadowingTracker",
]
