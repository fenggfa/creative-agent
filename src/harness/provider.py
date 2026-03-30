"""约束提供者 - 解析 MD 文件并注入约束规则。"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.constraints.rules import ConstraintChecker, ContentRules, QualityThresholds


@dataclass
class ParsedRules:
    """从 MD 文件解析出的规则。"""

    # 核心原则
    core_principles: list[str] = field(default_factory=list)

    # 禁止模式（从 MD 表格解析）
    forbidden_patterns: list[str] = field(default_factory=list)

    # 约束边界
    constraints_boundary: dict[str, str] = field(default_factory=dict)

    # 通过标准
    passing_criteria: dict[str, Any] = field(default_factory=dict)

    # 原始 MD 内容
    raw_content: str = ""


class ConstraintProvider:
    """约束提供者 - 负责解析约束并注入到智能体。"""

    def __init__(self, md_path: str = "AGENTS.md"):
        """初始化约束提供者。

        Args:
            md_path: 约束 MD 文件路径
        """
        self.md_path = Path(md_path)
        self._cached_rules: ParsedRules | None = None

    def parse_md_rules(self, force_reload: bool = False) -> ParsedRules:
        """解析 MD 文件提取规则。

        Args:
            force_reload: 是否强制重新加载

        Returns:
            解析后的规则对象
        """
        if self._cached_rules and not force_reload:
            return self._cached_rules

        if not self.md_path.exists():
            return ParsedRules()

        content = self.md_path.read_text(encoding="utf-8")
        rules = ParsedRules(raw_content=content)

        # 解析核心原则
        rules.core_principles = self._parse_core_principles(content)

        # 解析禁止模式
        rules.forbidden_patterns = self._parse_forbidden_patterns(content)

        # 解析约束边界
        rules.constraints_boundary = self._parse_constraints_boundary(content)

        # 解析通过标准
        rules.passing_criteria = self._parse_passing_criteria(content)

        self._cached_rules = rules
        return rules

    def _parse_core_principles(self, content: str) -> list[str]:
        """解析核心原则部分。"""
        principles = []

        # 匹配 "## 核心原则" 后的列表项
        pattern = r"##\s*核心原则\s*\n((?:\d+\.\s*.+\n?)+)"
        match = re.search(pattern, content)

        if match:
            items = match.group(1)
            # 提取每条原则
            for line in items.strip().split("\n"):
                # 移除编号，提取原则内容
                cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
                if cleaned:
                    principles.append(cleaned)

        return principles

    def _parse_forbidden_patterns(self, content: str) -> list[str]:
        """解析禁止模式表格。"""
        patterns = []

        # 匹配 "## 约束边界" 下的表格
        pattern = r"##\s*约束边界\s*\n\|.*?\n\|.*?\n((?:\|.+\|\n?)+)"
        match = re.search(pattern, content)

        if match:
            table_rows = match.group(1)
            for row in table_rows.strip().split("\n"):
                if not row.startswith("|"):
                    continue
                # 解析表格列
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if cols and cols[0] not in ("禁止", ""):
                    patterns.append(cols[0])

        # 添加预定义的 AI 典型表达模式
        predefined_patterns = [
            r"首先，让我们",
            r"总之，",
            r"综上所述，",
            r"在当今社会",
            r"众所周知",
        ]
        patterns.extend(predefined_patterns)

        return patterns

    def _parse_constraints_boundary(self, content: str) -> dict[str, str]:
        """解析约束边界表格。"""
        boundaries = {}

        pattern = r"##\s*约束边界\s*\n\|.*?\n\|.*?\n((?:\|.+\|\n?)+)"
        match = re.search(pattern, content)

        if match:
            table_rows = match.group(1)
            for row in table_rows.strip().split("\n"):
                if not row.startswith("|"):
                    continue
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if len(cols) >= 2 and cols[0] not in ("禁止", ""):
                    boundaries[cols[0]] = cols[1] if len(cols) > 1 else ""

        return boundaries

    def _parse_passing_criteria(self, content: str) -> dict[str, Any]:
        """解析通过标准。"""
        criteria = {
            "total_threshold": 0.70,
            "min_consistency": 0.60,
            "min_completeness": 0.60,
        }

        # 匹配 "## 反馈机制" 下的通过标准
        pattern = r"通过标准[：:]\s*总分\s*≥?\s*([\d.]+)"
        match = re.search(pattern, content)

        if match:
            criteria["total_threshold"] = float(match.group(1))

        # 匹配维度最低分
        pattern2 = r"一致性\s*&\s*完成度\s*≥?\s*([\d.]+)"
        match2 = re.search(pattern2, content)

        if match2:
            criteria["min_consistency"] = float(match2.group(1))
            criteria["min_completeness"] = float(match2.group(1))

        return criteria

    def get_system_prompt_injection(self, agent_type: str) -> str:
        """生成智能体系统提示词注入。

        Args:
            agent_type: 智能体类型
                - 单篇模式: researcher/writer/reviewer
                - 整书模式: director/plot_architect/prose_writer/critic

        Returns:
            注入到系统提示词的约束内容
        """
        rules = self.parse_md_rules()

        injection_parts = []

        # 添加核心原则
        if rules.core_principles:
            injection_parts.append("## 必须遵循的核心原则")
            for i, principle in enumerate(rules.core_principles, 1):
                injection_parts.append(f"{i}. {principle}")

        # 添加禁止模式
        if rules.forbidden_patterns:
            injection_parts.append("\n## 禁止使用的表达模式")
            injection_parts.append("以下表达是 AI 典型模式，严禁使用：")
            for pattern in rules.forbidden_patterns:
                injection_parts.append(f"- {pattern}")

        # 根据智能体类型添加特定约束
        constraint_methods = {
            # 单篇模式
            "researcher": self._get_researcher_constraints,
            "writer": self._get_writer_constraints,
            "reviewer": self._get_reviewer_constraints,
            # 整书模式
            "director": self._get_director_constraints,
            "plot_architect": self._get_plot_architect_constraints,
            "prose_writer": self._get_prose_writer_constraints,
            "critic": self._get_critic_constraints,
            # 知识图谱
            "kg_builder": self._get_kg_builder_constraints,
        }

        if agent_type in constraint_methods:
            injection_parts.extend(constraint_methods[agent_type](rules))

        return "\n".join(injection_parts)

    def _get_writer_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 Writer 智能体的特定约束。"""
        constraints = [
            "\n## 创作约束",
            "- 必须忠实于原作设定",
            "- 禁止改变人物性格和能力",
            "- 避免使用 AI 典型表达模式",
        ]

        if rules.passing_criteria:
            threshold = rules.passing_criteria.get("total_threshold", 0.70)
            constraints.append(f"- 内容需达到 {threshold:.0%} 质量标准")

        return constraints

    def _get_researcher_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 Researcher（素材收集）智能体的特定约束。"""
        constraints = [
            "\n## 素材收集约束",
            "- 必须从知识图谱检索素材",
            "- 返回与任务相关的设定、人物、背景信息",
            "- 不要杜撰不存在的设定",
        ]

        if rules.core_principles:
            constraints.append("- 遵循项目核心原则进行素材筛选")

        return constraints

    def _get_reviewer_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 Reviewer 智能体的特定约束。"""
        constraints = [
            "\n## 审核约束",
            "- 使用五维评估标准",
            "- 必须给出具体改进建议",
        ]

        if rules.passing_criteria:
            threshold = rules.passing_criteria.get("total_threshold", 0.70)
            min_consistency = rules.passing_criteria.get("min_consistency", 0.60)
            constraints.extend([
                f"- 总分通过阈值: {threshold:.0%}",
                f"- 一致性最低分: {min_consistency:.0%}",
            ])

        return constraints

    def _get_director_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 Director（总监制）智能体的特定约束。"""
        constraints = [
            "\n## 总监制约束",
            "- 必须解析用户意图，明确创作目标",
            "- 协调各智能体按顺序工作",
            "- 严格把控章节进度和质量",
            "- 发现质量问题必须要求重写",
        ]

        if rules.passing_criteria:
            threshold = rules.passing_criteria.get("total_threshold", 0.70)
            constraints.append(f"- 最终输出必须达到 {threshold:.0%} 质量标准")

        return constraints

    def _get_plot_architect_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 PlotArchitect（故事架构师）智能体的特定约束。"""
        constraints = [
            "\n## 故事架构师约束",
            "- 大纲必须结构完整、逻辑清晰",
            "- 章节之间要有自然过渡",
            "- 伏笔埋设与揭晓要合理规划",
            "- 情节线索要有明确起止",
            "- 避免俗套剧情，追求差异化",
        ]

        if rules.core_principles:
            constraints.append("- 大纲设计需符合项目核心原则")

        return constraints

    def _get_prose_writer_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 ProseWriter（风格写稿师）智能体的特定约束。"""
        constraints = [
            "\n## 写稿师约束",
            "- 必须忠实于原作设定和大纲",
            "- 人物性格不能偏离设定",
            "- 文风必须与指定风格一致",
            "- 场景描写要生动有画面感",
            "- 对话要符合人物性格特点",
            "- 严禁使用 AI 典型表达模式",
        ]

        if rules.forbidden_patterns:
            constraints.append(f"- 禁止使用 {len(rules.forbidden_patterns)} 种 AI 典型表达")

        if rules.passing_criteria:
            threshold = rules.passing_criteria.get("total_threshold", 0.70)
            constraints.append(f"- 内容需达到 {threshold:.0%} 质量标准")

        return constraints

    def _get_critic_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 Critic（批评审核师）智能体的特定约束。"""
        constraints = [
            "\n## 审核师约束",
            "- 使用五维评估标准进行审核",
            "- 检查人物设定一致性",
            "- 检查情节逻辑合理性",
            "- 检查世界观规则是否被违反",
            "- 必须给出具体、可操作的修改建议",
        ]

        if rules.passing_criteria:
            threshold = rules.passing_criteria.get("total_threshold", 0.70)
            min_consistency = rules.passing_criteria.get("min_consistency", 0.60)
            constraints.extend([
                f"- 总分通过阈值: {threshold:.0%}",
                f"- 一致性最低分: {min_consistency:.0%}",
            ])

        return constraints

    def _get_kg_builder_constraints(self, rules: ParsedRules) -> list[str]:
        """获取 KG Builder（知识图谱构建师）智能体的特定约束。"""
        constraints = [
            "\n## 知识图谱构建约束",
            "- 实体名称必须统一，避免同义多形",
            "- 关系必须有明确的语义类型",
            "- 优先提取核心实体，避免过度提取",
            "- 置信度评估要基于文本明确程度",
            "- 只提取文本中明确描述的关系",
        ]

        if rules.core_principles:
            constraints.append("- 图谱构建需符合项目核心原则")

        return constraints

    def create_checker(
        self,
        additional_forbidden_patterns: list[str] | None = None,
        custom_thresholds: QualityThresholds | None = None,
    ) -> ConstraintChecker:
        """创建配置好的 ConstraintChecker。

        Args:
            additional_forbidden_patterns: 额外的禁止模式
            custom_thresholds: 自定义质量阈值

        Returns:
            配置好的约束检查器
        """
        rules = self.parse_md_rules()

        # 合并禁止模式
        all_patterns = list(rules.forbidden_patterns)
        if additional_forbidden_patterns:
            all_patterns.extend(additional_forbidden_patterns)

        # 创建内容规则
        content_rules = ContentRules(forbidden_patterns=all_patterns)

        # 创建检查器
        return ConstraintChecker(
            rules=content_rules,
            thresholds=custom_thresholds or QualityThresholds(),
        )

    def get_constraint_rules_dict(self) -> dict[str, Any]:
        """获取约束规则的字典表示，用于存储到状态。"""
        rules = self.parse_md_rules()
        return {
            "core_principles": rules.core_principles,
            "forbidden_patterns": rules.forbidden_patterns,
            "constraints_boundary": rules.constraints_boundary,
            "passing_criteria": rules.passing_criteria,
        }


# 全局约束提供者实例
_provider_instance: ConstraintProvider | None = None


def get_constraint_provider(md_path: str = "AGENTS.md") -> ConstraintProvider:
    """获取全局约束提供者实例。

    Args:
        md_path: 约束 MD 文件路径

    Returns:
        约束提供者实例
    """
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = ConstraintProvider(md_path)
    return _provider_instance


async def inject_constraints_to_state(state: dict[str, Any]) -> dict[str, Any]:
    """将约束注入到工作流状态。

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态
    """
    provider = get_constraint_provider()
    provider.parse_md_rules()  # 确保规则已加载

    updates: dict[str, Any] = {
        "constraints_injected": True,
        "constraint_rules": provider.get_constraint_rules_dict(),
        "violations": [],
    }

    return {**state, **updates}
