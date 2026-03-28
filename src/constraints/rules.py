"""内容约束规则和检查器。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    """内容类型枚举。"""

    STORY = "story"  # 故事
    ARTICLE = "article"  # 文章
    DIALOGUE = "dialogue"  # 对话
    DESCRIPTION = "description"  # 描写


class Severity(str, Enum):
    """问题严重程度。"""

    ERROR = "error"  # 必须修复
    WARNING = "warning"  # 建议修复
    INFO = "info"  # 提示信息


@dataclass
class ConstraintViolation:
    """约束违规记录。"""

    rule_name: str
    severity: Severity
    message: str
    position: tuple[int, int] | None = None  # (start, end) 字符位置
    suggestion: str | None = None


@dataclass
class QualityThresholds:
    """质量阈值配置。"""

    min_length: int = 100  # 最小字数
    max_length: int = 10000  # 最大字数
    min_coherence_score: float = 0.6  # 最低连贯性分数
    max_revision_ratio: float = 0.5  # 最大单次修改比例


@dataclass
class ContentRules:
    """内容规则配置。"""

    # 禁止模式
    forbidden_patterns: list[str] = field(
        default_factory=lambda: [
            # AI 常见过度使用模式
            r"首先，让我们",
            r"总之，",
            r"综上所述，",
            r"在当今社会",
            r"众所周知",
        ]
    )

    # 必需元素
    required_elements: dict[str, bool] = field(
        default_factory=lambda: {
            "proper_nouns_preserved": True,  # 专有名词保持原样
            "character_consistency": True,  # 人物一致性
            "plot_logic": True,  # 情节逻辑
        }
    )

    # 内容类型特定规则
    type_specific_rules: dict[ContentType, dict[str, Any]] = field(
        default_factory=lambda: {
            ContentType.STORY: {
                "min_scenes": 1,
                "require_dialogue": True,
                "require_description": True,
            },
            ContentType.DIALOGUE: {
                "min_speakers": 2,
                "max_monologue_ratio": 0.3,
            },
        }
    )


class ConstraintChecker:
    """约束检查器 - 验证内容是否符合规则。"""

    def __init__(
        self,
        rules: ContentRules | None = None,
        thresholds: QualityThresholds | None = None,
    ):
        self.rules = rules or ContentRules()
        self.thresholds = thresholds or QualityThresholds()

    def check_length(self, content: str) -> list[ConstraintViolation]:
        """检查内容长度。"""
        violations = []
        length = len(content)

        if length < self.thresholds.min_length:
            violations.append(
                ConstraintViolation(
                    rule_name="min_length",
                    severity=Severity.ERROR,
                    message=f"内容过短：{length} 字，最少需要 {self.thresholds.min_length} 字",
                    suggestion="请扩充内容，增加更多细节描写",
                )
            )

        if length > self.thresholds.max_length:
            violations.append(
                ConstraintViolation(
                    rule_name="max_length",
                    severity=Severity.WARNING,
                    message=f"内容过长：{length} 字，最多允许 {self.thresholds.max_length} 字",
                    suggestion="请精简内容，删除冗余部分",
                )
            )

        return violations

    def check_forbidden_patterns(self, content: str) -> list[ConstraintViolation]:
        """检查禁止模式。"""
        import re

        violations = []

        for pattern in self.rules.forbidden_patterns:
            matches = list(re.finditer(pattern, content))
            for match in matches:
                violations.append(
                    ConstraintViolation(
                        rule_name="forbidden_pattern",
                        severity=Severity.WARNING,
                        message=f"检测到 AI 典型表达模式：'{match.group()}'",
                        position=(match.start(), match.end()),
                        suggestion="请使用更自然的表达方式",
                    )
                )

        return violations

    def check_character_consistency(
        self,
        content: str,
        character_info: dict[str, Any],
    ) -> list[ConstraintViolation]:
        """检查人物一致性。"""
        violations = []

        # 检查人物名称是否正确
        for name, info in character_info.items():
            if name not in content:
                continue  # 人物未出现，跳过

            # 检查能力描述是否一致
            abilities = info.get("abilities", [])
            for ability in abilities:
                # 简单检查：能力关键词是否存在
                if ability.lower() not in content.lower():
                    violations.append(
                        ConstraintViolation(
                            rule_name="character_ability",
                            severity=Severity.INFO,
                            message=f"人物 '{name}' 的能力 '{ability}' 未体现",
                            suggestion=f"考虑在适当位置展现 {name} 的 {ability} 能力",
                        )
                    )

        return violations

    def run_all_checks(
        self,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> list[ConstraintViolation]:
        """运行所有检查。"""
        violations = []

        violations.extend(self.check_length(content))
        violations.extend(self.check_forbidden_patterns(content))

        if context and "character_info" in context:
            violations.extend(
                self.check_character_consistency(content, context["character_info"])
            )

        return violations

    def get_summary(self, violations: list[ConstraintViolation]) -> dict[str, Any]:
        """生成违规摘要。"""
        return {
            "total": len(violations),
            "errors": sum(1 for v in violations if v.severity == Severity.ERROR),
            "warnings": sum(1 for v in violations if v.severity == Severity.WARNING),
            "infos": sum(1 for v in violations if v.severity == Severity.INFO),
            "passed": not any(v.severity == Severity.ERROR for v in violations),
        }
