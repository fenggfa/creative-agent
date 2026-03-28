"""高级知识图谱工具 - 封装工具链，简化 LLM 调用。

设计理念：
- 将常用操作封装为单一"高级工具"
- 减少工具数量，降低选择复杂度
- 内部自动处理多步骤逻辑
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.tools.lightrag import creative_lightrag_client, lightrag_client

# ==================== 结构化输出模型 ====================


class MaterialInfo(BaseModel):
    """素材信息结构。"""

    source: str = Field(description="来源：素材图谱/二创图谱")
    content: str = Field(description="内容")
    has_info: bool = Field(description="是否找到信息")


class ResearchResult(BaseModel):
    """研究结果结构。"""

    task: str = Field(description="创作任务")
    material_info: MaterialInfo = Field(description="原作设定")
    creative_info: MaterialInfo = Field(description="二创设定")
    has_conflict: bool = Field(description="是否存在设定冲突")
    conflict_details: str | None = Field(default=None, description="冲突详情")
    suggestions: list[str] = Field(default_factory=list, description="创作建议")

    def to_prompt(self) -> str:
        """转换为可用作提示词的格式。"""
        parts = []

        if self.material_info.has_info:
            parts.append("=== 【素材图谱】原作设定 ===")
            parts.append(self.material_info.content)

        if self.creative_info.has_info:
            if parts:
                parts.append("")
            parts.append("=== 【二创图谱】创作演绎 ===")
            parts.append("")
            parts.append("⚠️ 注意：如与原作冲突，以此为准。")
            parts.append(self.creative_info.content)

        if self.has_conflict and self.conflict_details:
            parts.append("")
            parts.append("=== 【设定冲突提醒】 ===")
            parts.append(self.conflict_details)

        if self.suggestions:
            parts.append("")
            parts.append("=== 【创作建议】 ===")
            for i, sug in enumerate(self.suggestions, 1):
                parts.append(f"{i}. {sug}")

        if not parts:
            return "未找到相关设定，可以自由创作。"

        return "\n".join(parts)


# ==================== 高级工具：一站式研究 ====================


@tool
async def research_for_writing(task: str) -> str:
    """
    【推荐】一站式创作研究工具。

    自动完成以下工作：
    1. 查询素材图谱获取原作设定
    2. 查询二创图谱获取已创作内容
    3. 对比分析，发现设定冲突
    4. 生成创作建议

    这是创作前最应该调用的工具，一个工具搞定所有研究工作。

    Args:
        task: 创作任务描述，如"写孙悟空大战红孩儿"、"描述唐僧的性格"

    Returns:
        结构化的研究结果，包含原作设定、二创设定、冲突提醒、创作建议

    Examples:
        research_for_writing("孙悟空大战红孩儿")
        research_for_writing("唐僧的性格变化")
    """
    import asyncio

    if not task or len(task.strip()) < 3:
        return "❌ 任务描述太短，请提供更详细的创作任务"

    task = task.strip()

    # 提取关键词（简化版，实际可用 LLM）
    keywords = _extract_keywords(task)

    # 并发查询两个图谱
    try:
        material_task = lightrag_client.query(keywords)
        creative_task = creative_lightrag_client.query(keywords)

        material_result, creative_result = await asyncio.gather(
            material_task, creative_task, return_exceptions=True
        )

        # 构建结果
        material_info = MaterialInfo(
            source="素材图谱",
            content=str(material_result) if not isinstance(material_result, Exception) else "",
            has_info=not isinstance(material_result, Exception) and bool(material_result),
        )

        creative_info = MaterialInfo(
            source="二创图谱",
            content=str(creative_result) if not isinstance(creative_result, Exception) else "",
            has_info=not isinstance(creative_result, Exception) and bool(creative_result),
        )

        # 检测冲突
        has_conflict, conflict_details = _detect_conflict(
            material_info.content,
            creative_info.content,
        )

        # 生成建议
        suggestions = _generate_suggestions(
            material_info,
            creative_info,
            has_conflict,
        )

        result = ResearchResult(
            task=task,
            material_info=material_info,
            creative_info=creative_info,
            has_conflict=has_conflict,
            conflict_details=conflict_details,
            suggestions=suggestions,
        )

        return result.to_prompt()

    except Exception as e:
        return f"❌ 研究失败: {str(e)}"


# ==================== 高级工具：保存创作 ====================


@tool
async def save_creative_work(
    content: str,
    title: str,
    characters: list[str] | None = None,
) -> str:
    """
    【推荐】保存创作内容到二创图谱。

    自动完成：
    1. 格式化内容
    2. 添加元数据
    3. 保存到图谱
    4. 验证保存成功

    Args:
        content: 创作内容（必填）
        title: 标题，如"第1章 孙悟空出场"（必填）
        characters: 涉及的人物列表（可选，用于后续查询）

    Returns:
        保存结果，包含成功状态和后续建议

    Examples:
        save_creative_work("孙悟空挥动金箍棒...", "第1章 孙悟空出场", ["孙悟空", "唐僧"])
    """
    if not content or len(content.strip()) < 20:
        return "❌ 内容太短，请提供完整的创作内容（至少20个字符）"

    if not title or not title.strip():
        return "❌ 请提供标题，如'第1章 孙悟空出场'"

    from datetime import datetime

    # 构建带元数据的内容
    enriched_content = f"""【{title}】
创作时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
涉及人物: {', '.join(characters) if characters else '未指定'}

{content.strip()}"""

    try:
        success = await creative_lightrag_client.insert(enriched_content)

        if success:
            result = f"✅ 已保存「{title}」到二创图谱\n\n"
            result += "📝 后续创作可通过以下方式查询：\n"
            if characters:
                char_query = " 或 ".join(characters[:2])
                result += f"- 查询人物设定: research_for_writing(\"{char_query}\")\n"
            result += f"- 查询本章内容: research_for_writing(\"{title}\")"
            return result

        return "❌ 保存失败，请稍后重试"

    except Exception as e:
        return f"❌ 保存失败: {str(e)}"


# ==================== 辅助函数 ====================


def _extract_keywords(task: str) -> str:
    """
    从任务描述中提取关键词。

    简化实现，实际可用 LLM 或关键词提取模型。
    """
    # 移除常见无关词
    stop_words = {"写", "描述", "创作", "一段", "一个", "关于", "的", "场景", "情节"}

    words = task.replace("，", " ").replace("。", " ").split()
    keywords = [w for w in words if w not in stop_words and len(w) > 1]

    # 如果没有提取到，返回原任务
    return " ".join(keywords) if keywords else task


def _detect_conflict(
    material_content: str,
    creative_content: str,
) -> tuple[bool, str | None]:
    """
    检测设定冲突。

    简化实现，实际可用 LLM 进行语义对比。
    """
    # 如果任一为空，无冲突
    if not material_content or not creative_content:
        return False, None

    # 简单关键词冲突检测（实际应使用 LLM）
    conflict_keywords = [
        ("喜欢", "讨厌"),
        ("善良", "邪恶"),
        ("勇敢", "胆小"),
    ]

    for pos, neg in conflict_keywords:
        # 检查是否一个说正面，一个说负面
        mat_has_pos = pos in material_content
        mat_has_neg = neg in material_content
        cre_has_pos = pos in creative_content
        cre_has_neg = neg in creative_content

        if (mat_has_pos and cre_has_neg) or (mat_has_neg and cre_has_pos):
            msg = f"检测到设定冲突：原作「{pos}」vs 二创「{neg}」。请确认是否为有意发展。"
            return True, msg

    return False, None


def _generate_suggestions(
    material_info: MaterialInfo,
    creative_info: MaterialInfo,
    has_conflict: bool,
) -> list[str]:
    """生成创作建议。"""
    suggestions = []

    if not material_info.has_info and not creative_info.has_info:
        suggestions.append("未找到相关设定，可以自由创作，发挥想象力")
        suggestions.append("建议创作后使用 save_creative_work 保存设定")
        return suggestions

    if not creative_info.has_info:
        suggestions.append("这是新的设定点，参考原作进行创作")
    else:
        suggestions.append("已找到之前的创作设定，请保持前后一致")

    if has_conflict:
        suggestions.append("⚠️ 检测到设定冲突，请确认是有意的角色发展还是需要修正")

    if material_info.has_info:
        suggestions.append("忠实于原作核心设定，可适当扩展细节")

    return suggestions


# ==================== 简化版工具集合 ====================

# 高级工具（推荐使用）
ADVANCED_TOOLS = [
    research_for_writing,
    save_creative_work,
]

# 完整工具集（需要精细控制时使用）
FULL_TOOLS = [
    research_for_writing,
    save_creative_work,
]

# 默认使用高级工具
DEFAULT_TOOLS = ADVANCED_TOOLS
