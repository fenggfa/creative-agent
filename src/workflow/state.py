"""多智能体工作流状态定义。"""

from typing import Any, Literal, TypedDict


class ChapterSummary(TypedDict):
    """章节摘要。"""

    chapter_num: int
    title: str
    summary: str
    key_events: list[str]
    character_changes: dict[str, Any]


class CharacterState(TypedDict, total=False):
    """人物状态追踪。"""

    name: str
    location: str
    mood: str
    relationships: dict[str, str]  # {其他人物: 关系状态}
    current_goal: str
    last_appearance: int  # 最后出现的章节号
    development_notes: list[str]


class PlotThread(TypedDict, total=False):
    """情节线索追踪。"""

    thread_id: str
    description: str
    status: Literal["active", "resolved", "abandoned"]
    chapters_involved: list[int]
    key_events: list[str]


class Foreshadowing(TypedDict, total=False):
    """伏笔追踪。"""

    content: str
    chapter_planted: int
    chapter_to_reveal: int
    revealed: bool
    notes: str


class BookOutline(TypedDict, total=False):
    """整书大纲。"""

    title: str
    theme: str
    total_chapters: int
    chapters: list[dict[str, Any]]  # [{chapter_num, title, summary, key_events}]
    plot_threads: list[PlotThread]
    main_characters: list[str]


class AgentState(TypedDict, total=False):
    """智能体之间传递的工作流状态。"""

    # 创作任务
    task: str
    # 收集的素材
    materials: str
    # 是否使用工具调用模式
    use_tools: bool
    # 创作内容
    draft: str
    # 审核反馈
    review_feedback: str
    # 审核是否通过
    approved: bool
    # 修改次数
    revision_count: int
    # 最终输出
    final_output: str

    # === 约束注入相关字段 ===
    # 约束是否已注入
    constraints_injected: bool
    # 当前生效的约束规则
    constraint_rules: dict[str, Any]
    # 约束违规记录
    violations: list[dict[str, Any]]
    # 评估结果
    evaluation_result: dict[str, Any] | None

    # === 输出相关字段 (2026-03-28 新增) ===
    # 原作名称（如"西游记"）
    source_work: str
    # Obsidian 保存路径
    obsidian_path: str
    # LightRAG 保存状态
    lightrag_saved: bool
    # 输出结果汇总
    output_result: dict[str, Any]


class BookState(TypedDict, total=False):
    """整书创作状态（扩展自 AgentState）。"""

    # === 基本信息 ===
    task: str
    book_mode: bool  # 是否整书模式
    source_work: str  # 原作名称

    # === 策划阶段产物 ===
    world_setting: dict[str, Any]  # 世界观设定
    character_profiles: dict[str, Any]  # 人物档案 {name: profile}
    book_outline: BookOutline  # 整书大纲

    # === 创作状态 ===
    current_chapter: int  # 当前章节序号
    chapter_contents: dict[int, str]  # 已完成章节内容 {chapter_num: content}
    chapter_summaries: dict[int, ChapterSummary]  # 章节摘要

    # === 状态追踪 ===
    character_states: dict[str, CharacterState]  # 人物当前状态
    plot_threads: dict[str, PlotThread]  # 情节线索
    foreshadowing: list[Foreshadowing]  # 伏笔清单

    # === 审核记录 ===
    review_history: list[dict[str, Any]]  # 审核历史
    violations: list[dict[str, Any]]  # 约束违规记录
    evaluation_result: dict[str, Any] | None

    # === 输出 ===
    final_output: str
    obsidian_path: str
    lightrag_saved: bool
    output_result: dict[str, Any]

    # === 兼容 AgentState 字段 ===
    materials: str
    draft: str
    review_feedback: str
    approved: bool
    revision_count: int
    use_tools: bool
    constraints_injected: bool
    constraint_rules: dict[str, Any]
