"""使用 LangGraph 编排工作流。

工作流架构：
===========================================

单篇模式：
START → researcher → writer → reviewer → output → END
                            ↑          │
                            └──────────┘ (审核不通过时修改)

整书模式：
START → director → plot_architect → [chapter_loop] → output → END
                                      ↓
                        ┌─────────────────────────────┐
                        │ FOR each chapter:           │
                        │   plot_architect (细纲)     │
                        │   → prose_writer            │
                        │   → critic                  │
                        │   → continuity_check        │
                        │   → save_chapter            │
                        └─────────────────────────────┘
"""

import os
from typing import Any

from langgraph.graph import END, StateGraph

from src.agents.critic import critic_node
from src.agents.director import director_node
from src.agents.plot_architect import plot_architect_node
from src.agents.prose_writer import prose_writer_node
from src.agents.researcher import researcher_node
from src.agents.reviewer import reviewer_node
from src.agents.writer import writer_node
from src.config import settings
from src.output import clean_final_output, save_creative_output
from src.tools.continuity import (
    ChapterSummarizer,
    CharacterStateTracker,
    ConflictDetector,
)
from src.workflow.state import AgentState, BookState


async def output_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    输出节点：保存创作内容到 Obsidian 和 LightRAG。
    """
    task = state.get("task", "")
    draft = state.get("draft", "")
    source_work = state.get("source_work", "西游记")
    book_mode = state.get("book_mode", False)

    if book_mode:
        # 整书模式：输出全书内容
        return await _output_book(state)

    # 单篇模式
    cleaned_draft = clean_final_output(draft)

    result = await save_creative_output(
        content=cleaned_draft,
        task=task,
        source_work=source_work,
        evaluation=state.get("evaluation_result"),
    )

    final_output = cleaned_draft
    if result.get("success"):
        final_output = f"{cleaned_draft}\n\n---\n\n✅ 已保存到图谱和 Obsidian"

    output_state: dict[str, Any] = {
        "final_output": final_output,
        "output_result": result,
        "lightrag_saved": result.get("lightrag", {}).get("success", False),
    }

    if os.environ.get("HARNESS_E2E"):
        e2e_results = await _run_e2e_validation()
        if e2e_results:
            output_state["e2e_results"] = e2e_results

    return output_state


async def _output_book(state: dict[str, Any]) -> dict[str, Any]:
    """输出整书内容。"""
    book_outline = state.get("book_outline", {})
    chapter_contents = state.get("chapter_contents", {})

    # 组装全书内容
    lines = [
        f"# {book_outline.get('title', '未命名作品')}",
        "",
        f"**主题**: {book_outline.get('theme', '')}",
        "",
        "---",
        "",
    ]

    # 目录
    lines.append("## 目录\n")
    chapters = book_outline.get("chapters", [])
    for chapter in chapters:
        chapter_num = chapter.get("chapter_num", 0)
        title = chapter.get("title", f"第{chapter_num}章")
        lines.append(f"- 第{chapter_num}章 {title}")
    lines.append("\n---\n")

    # 正文
    for chapter_num in sorted(chapter_contents.keys()):
        content = chapter_contents[chapter_num]
        chapter_info = next(
            (c for c in chapters if c.get("chapter_num") == chapter_num),
            {"title": f"第{chapter_num}章"},
        )
        lines.append(f"## 第{chapter_num}章 {chapter_info.get('title', '')}\n")
        lines.append(content)
        lines.append("\n\n")

    full_content = "\n".join(lines)

    # 保存
    result = await save_creative_output(
        content=full_content,
        task=state.get("task", ""),
        source_work=state.get("source_work", "原创"),
        evaluation=state.get("evaluation_result"),
    )

    return {
        "final_output": full_content,
        "output_result": result,
        "lightrag_saved": result.get("lightrag", {}).get("success", False),
    }


async def _run_e2e_validation() -> list[str] | None:
    """运行 E2E 验证（可选）。"""
    try:
        from src.harness import E2EValidator

        validator = E2EValidator()
        results = await validator.run_all_tests()

        passed_features = [
            r.feature_id for r in results
            if r.status.value == "passed"
        ]

        if passed_features:
            print(f"\n✅ E2E 验证通过: {passed_features}")

        return passed_features

    except Exception as e:
        print(f"\n⚠️ E2E 验证失败: {e}")
        return None


# ============================================================================
# 单篇模式路由
# ============================================================================


def should_continue(state: AgentState) -> str:
    """判断是否继续修改或结束工作流。"""
    if state.get("approved", False):
        return "output"

    revision_count = state.get("revision_count", 0)
    if revision_count >= settings.MAX_REVISIONS:
        return "output"

    return "writer"


# ============================================================================
# 整书模式节点和路由
# ============================================================================


async def chapter_loop_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    章节循环节点。

    执行单个章节的完整创作流程。
    """
    current_chapter = state.get("current_chapter", 0)
    book_outline = state.get("book_outline", {})
    total_chapters = book_outline.get("total_chapters", 0)

    # 检查是否完成所有章节
    if current_chapter > total_chapters:
        return {"_phase": "output"}

    # 开始新章节
    if current_chapter == 0:
        current_chapter = 1

    return {
        "current_chapter": current_chapter,
        "_phase": "write_chapter",
        "revision_count": 0,
    }


async def save_chapter_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    保存章节节点。

    保存章节内容，更新状态追踪，准备下一章节。
    """
    current_chapter = state.get("current_chapter", 1)
    draft = state.get("draft", "")
    chapter_outline = state.get("_current_chapter_outline", {})

    # 保存章节内容
    chapter_contents = state.get("chapter_contents", {})
    chapter_contents[current_chapter] = draft

    # 生成章节摘要
    summarizer = ChapterSummarizer()
    summary = await summarizer.summarize(
        chapter_num=current_chapter,
        chapter_title=chapter_outline.get("title", f"第{current_chapter}章"),
        chapter_content=draft,
    )

    chapter_summaries = state.get("chapter_summaries", {})
    chapter_summaries[current_chapter] = summary

    # 更新人物状态
    character_profiles = state.get("character_profiles", {})
    character_states = state.get("character_states", {})

    tracker = CharacterStateTracker()
    new_states = await tracker.update_states(
        chapter_num=current_chapter,
        chapter_content=draft,
        current_states=character_states,
        character_profiles=character_profiles,
    )

    # 冲突检测
    world_setting = state.get("world_setting", {})
    detector = ConflictDetector()
    conflicts = await detector.check_chapter_conflicts(
        chapter_content=draft,
        world_setting=world_setting,
        character_profiles=character_profiles,
        character_states=new_states,
        previous_chapters=[s.get("summary", "") for s in chapter_summaries.values()],
    )

    result: dict[str, Any] = {
        "chapter_contents": chapter_contents,
        "chapter_summaries": chapter_summaries,
        "character_states": new_states,
        "current_chapter": current_chapter + 1,  # 准备下一章节
        "draft": "",  # 清空草稿
        "revision_count": 0,
    }

    # 记录冲突
    if conflicts:
        result["_conflicts"] = conflicts

    return result


def book_should_continue(state: BookState) -> str:
    """判断整书模式下一步操作。"""
    phase = state.get("_phase", "start")
    approved = state.get("approved", False)
    revision_count = state.get("revision_count", 0)

    # 根据阶段决定
    if phase == "write_chapter":
        if approved:
            return "save_chapter"
        if revision_count >= settings.MAX_REVISIONS:
            return "save_chapter"  # 强制保存，进入下一章节
        return "prose_writer"

    if phase == "output":
        return "output"

    return "plot_architect"


# ============================================================================
# 工作流创建
# ============================================================================


def create_single_workflow() -> StateGraph[AgentState]:
    """
    创建单篇创作工作流。

    流程:
        START → researcher → writer → reviewer → output → END
    """
    workflow: StateGraph[AgentState] = StateGraph(AgentState)

    workflow.add_node("researcher", researcher_node)  # type: ignore
    workflow.add_node("writer", writer_node)  # type: ignore
    workflow.add_node("reviewer", reviewer_node)  # type: ignore
    workflow.add_node("output", output_node)  # type: ignore

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", "reviewer")

    workflow.add_conditional_edges(
        "reviewer",
        should_continue,
        {"writer": "writer", "output": "output"},
    )

    workflow.add_edge("output", END)

    return workflow


def create_book_workflow() -> StateGraph[BookState]:
    """
    创建整书创作工作流。

    流程:
        START → director → plot_architect → chapter_loop → [循环] → output → END
    """
    workflow: StateGraph[BookState] = StateGraph(BookState)

    # 添加节点
    workflow.add_node("director", director_node)  # type: ignore
    workflow.add_node("plot_architect", plot_architect_node)  # type: ignore
    workflow.add_node("prose_writer", prose_writer_node)  # type: ignore
    workflow.add_node("critic", critic_node)  # type: ignore
    workflow.add_node("save_chapter", save_chapter_node)  # type: ignore
    workflow.add_node("output", output_node)  # type: ignore

    # 入口点
    workflow.set_entry_point("director")

    # 策划阶段
    workflow.add_edge("director", "plot_architect")

    # 章节循环
    workflow.add_conditional_edges(
        "plot_architect",
        book_should_continue,
        {
            "prose_writer": "prose_writer",
            "output": "output",
        },
    )

    workflow.add_edge("prose_writer", "critic")

    workflow.add_conditional_edges(
        "critic",
        book_should_continue,
        {
            "prose_writer": "prose_writer",
            "save_chapter": "save_chapter",
        },
    )

    workflow.add_conditional_edges(
        "save_chapter",
        book_should_continue,
        {
            "plot_architect": "plot_architect",  # 下一章节
            "output": "output",  # 全部完成
        },
    )

    workflow.add_edge("output", END)

    return workflow


def create_workflow(
    book_mode: bool = False,
) -> StateGraph[AgentState] | StateGraph[BookState]:
    """
    创建工作流。

    Args:
        book_mode: 是否为整书模式

    Returns:
        工作流图
    """
    if book_mode:
        return create_book_workflow()
    return create_single_workflow()


def compile_workflow(book_mode: bool = False) -> Any:
    """编译并返回工作流应用。"""
    workflow = create_workflow(book_mode)
    return workflow.compile()


# 预编译的工作流实例（单篇模式）
app: Any = compile_workflow(book_mode=False)

# 整书模式工作流
book_app: Any = compile_workflow(book_mode=True)
