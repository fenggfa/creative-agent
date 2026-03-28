"""内容评估器 - 实现 GAN 风格的生成-评估反馈循环。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings


class EvaluationDimension(str, Enum):
    """评估维度。"""

    CONSISTENCY = "consistency"  # 设定一致性
    CREATIVITY = "creativity"  # 创意性
    QUALITY = "quality"  # 文笔质量
    COMPLETENESS = "completeness"  # 任务完成度
    LOGIC = "logic"  # 逻辑合理性


@dataclass
class EvaluationCriteria:
    """评估标准配置。"""

    # 各维度权重
    weights: dict[EvaluationDimension, float] = field(
        default_factory=lambda: {
            EvaluationDimension.CONSISTENCY: 0.25,
            EvaluationDimension.CREATIVITY: 0.20,
            EvaluationDimension.QUALITY: 0.20,
            EvaluationDimension.COMPLETENESS: 0.20,
            EvaluationDimension.LOGIC: 0.15,
        }
    )

    # 通过阈值
    passing_threshold: float = 0.70

    # 各维度最低分
    min_scores: dict[EvaluationDimension, float] = field(
        default_factory=lambda: {
            EvaluationDimension.CONSISTENCY: 0.60,  # 一致性要求较高
            EvaluationDimension.COMPLETENESS: 0.60,
        }
    )


@dataclass
class DimensionScore:
    """单维度评分。"""

    dimension: EvaluationDimension
    score: float  # 0.0 - 1.0
    reasoning: str
    issues: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """评估结果。"""

    scores: list[DimensionScore]
    total_score: float
    passed: bool
    overall_feedback: str
    improvement_suggestions: list[str] = field(default_factory=list)

    def get_dimension_score(self, dimension: EvaluationDimension) -> DimensionScore | None:
        """获取特定维度的评分。"""
        for score in self.scores:
            if score.dimension == dimension:
                return score
        return None


# 评估器系统提示词 - 借鉴 GAN 的判别器思想，保持"挑剔"态度
EVALUATOR_SYSTEM_PROMPT = """你是一个严格的内容评估专家。你的职责是客观、批判性地评估创作内容。

评估时请保持以下原则：
1. **高标准严要求**：宁可过于严格，不可放过低质量内容
2. **具体明确**：指出具体问题位置和改进方向
3. **客观公正**：基于事实评估，不受主观偏好影响
4. **建设性反馈**：每条批评都应附带改进建议

你必须对以下五个维度分别打分（0.0-1.0）：

## 一、设定一致性 (consistency)
- 人物性格、能力是否与原作设定一致
- 世界观、背景设定是否忠实
- 是否有违和的"出戏"元素

## 二、创意性 (creativity)
- 是否有原创性的创意决策
- 是否避免了 AI 生成的典型模式
- 是否有令人惊喜的情节设计

## 三、文笔质量 (quality)
- 语言是否流畅生动
- 描写是否有画面感
- 对话是否自然

## 四、任务完成度 (completeness)
- 是否完成了指定的创作任务
- 内容是否完整、有头有尾
- 是否遗漏了关键要素

## 五、逻辑合理性 (logic)
- 情节发展是否合理
- 是否有明显逻辑漏洞
- 人物行为是否符合其动机

输出格式（必须严格遵守）：
```
[维度名称] 分数: X.XX
理由: ...
问题: - 问题1 - 问题2
建议: ...

[总分] X.XX
[通过/不通过]
[总体反馈] ...
[改进建议] 1. ... 2. ... 3. ...
```"""


class ContentEvaluator:
    """内容评估器 - 独立的评估智能体。"""

    def __init__(
        self,
        criteria: EvaluationCriteria | None = None,
        model: str | None = None,
    ):
        self.criteria = criteria or EvaluationCriteria()
        self.model = model or settings.LLM_MODEL

    async def evaluate(
        self,
        task: str,
        content: str,
        materials: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        """
        评估创作内容。

        Args:
            task: 创作任务描述
            content: 待评估内容
            materials: 参考素材
            context: 额外上下文（如人物信息）

        Returns:
            评估结果
        """
        llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=self.model,
            temperature=0.3,  # 较低温度保证评估一致性
            timeout=60.0,
        )

        prompt = self._build_evaluation_prompt(task, content, materials, context)

        response = await llm.ainvoke([
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return self._parse_evaluation_result(response.content)

    def _build_evaluation_prompt(
        self,
        task: str,
        content: str,
        materials: str | None,
        context: dict[str, Any] | None,
    ) -> str:
        """构建评估提示词。"""
        prompt_parts = [
            "## 创作任务",
            task,
            "",
            "## 待评估内容",
            content,
        ]

        if materials:
            prompt_parts.extend([
                "",
                "## 参考素材（请对照检查一致性）",
                materials[:2000],  # 限制长度
            ])

        if context and "character_info" in context:
            prompt_parts.extend([
                "",
                "## 人物设定（必须保持一致）",
                self._format_character_info(context["character_info"]),
            ])

        prompt_parts.extend([
            "",
            "请严格按照五个维度进行评估，给出具体分数和反馈。",
        ])

        return "\n".join(prompt_parts)

    def _format_character_info(self, character_info: dict[str, Any]) -> str:
        """格式化人物信息。"""
        lines = []
        for name, info in character_info.items():
            lines.append(f"### {name}")
            if "description" in info:
                lines.append(f"外貌: {info['description']}")
            if "abilities" in info:
                lines.append(f"能力: {', '.join(info['abilities'])}")
            if "personality" in info:
                lines.append(f"性格: {info['personality']}")
        return "\n".join(lines)

    def _parse_evaluation_result(self, response: str) -> EvaluationResult:
        """解析评估结果。"""
        import re

        scores = []

        # 解析各维度分数
        dimension_patterns = {
            EvaluationDimension.CONSISTENCY: r"设定一致性|consistency",
            EvaluationDimension.CREATIVITY: r"创意性|creativity",
            EvaluationDimension.QUALITY: r"文笔质量|quality",
            EvaluationDimension.COMPLETENESS: r"任务完成度|completeness",
            EvaluationDimension.LOGIC: r"逻辑合理性|logic",
        }

        for dimension, pattern in dimension_patterns.items():
            # 匹配 "[维度名] 分数: X.XX" 格式
            match = re.search(
                rf"\[?{pattern}\]?.*?分数[:\s]+(\d+\.?\d*)",
                response,
                re.IGNORECASE | re.DOTALL,
            )
            if match:
                score = float(match.group(1))
                if score > 1:
                    score = score / 10  # 如果是百分制，转换为小数
                scores.append(DimensionScore(
                    dimension=dimension,
                    score=score,
                    reasoning="从评估响应中提取",
                ))

        # 计算加权总分
        total_score = sum(
            s.score * self.criteria.weights.get(s.dimension, 0.2)
            for s in scores
        )

        # 判断是否通过
        passed = total_score >= self.criteria.passing_threshold

        # 检查各维度最低分
        for score in scores:
            min_score = self.criteria.min_scores.get(score.dimension)
            if min_score and score.score < min_score:
                passed = False
                break

        # 解析总体反馈
        overall_feedback = ""
        feedback_match = re.search(
            r"\[总体反馈\][:：\s]*(.+?)(?=\[|$)",
            response,
            re.DOTALL,
        )
        if feedback_match:
            overall_feedback = feedback_match.group(1).strip()

        # 解析改进建议
        suggestions = []
        suggestions_match = re.search(
            r"\[改进建议\][:：\s]*(.+?)$",
            response,
            re.DOTALL,
        )
        if suggestions_match:
            suggestion_text = suggestions_match.group(1)
            suggestions = [
                s.strip().lstrip("0123456789.、")
                for s in suggestion_text.split("\n")
                if s.strip()
            ]

        return EvaluationResult(
            scores=scores,
            total_score=round(total_score, 2),
            passed=passed,
            overall_feedback=overall_feedback or "评估完成",
            improvement_suggestions=suggestions,
        )


async def evaluate_content(
    task: str,
    content: str,
    materials: str | None = None,
) -> EvaluationResult:
    """便捷函数：评估内容。"""
    evaluator = ContentEvaluator()
    return await evaluator.evaluate(task, content, materials)
