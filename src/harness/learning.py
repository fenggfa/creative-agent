"""学习模块 - 从失败中学习，提取新约束规则。

Harness Engineering 核心要求：
- "每次Agent犯错，就加一条规则"
- 将错误信号转化为可执行任务
- 实现自动反馈与自我进化

工作流程：
失败检测 → 模式分析 → 规则提取 → 规则验证 → 更新约束
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings


class LearningSource(str, Enum):
    """学习来源。"""

    CONSTRAINT_VIOLATION = "constraint_violation"  # 约束违规
    EVALUATION_FAILURE = "evaluation_failure"  # 评估失败
    E2E_FAILURE = "e2e_failure"  # E2E 测试失败
    ENTROPY_ISSUE = "entropy_issue"  # 熵问题
    MANUAL_FEEDBACK = "manual_feedback"  # 人工反馈


class RuleType(str, Enum):
    """规则类型。"""

    FORBIDDEN_PATTERN = "forbidden_pattern"  # 禁止模式
    REQUIRED_PATTERN = "required_pattern"  # 必须模式
    CONSTRAINT = "constraint"  # 约束条件
    PRINCIPLE = "principle"  # 核心原则
    THRESHOLD = "threshold"  # 阈值标准


@dataclass
class LearningPattern:
    """学习到的模式。"""

    pattern_id: str
    source: LearningSource
    rule_type: RuleType
    description: str
    pattern: str  # 正则表达式或具体模式
    severity: str  # critical, high, medium, low
    occurrence_count: int = 1
    last_seen: str = ""
    suggested_fix: str = ""
    confidence: float = 0.0
    approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "pattern_id": self.pattern_id,
            "source": self.source.value,
            "rule_type": self.rule_type.value,
            "description": self.description,
            "pattern": self.pattern,
            "severity": self.severity,
            "occurrence_count": self.occurrence_count,
            "last_seen": self.last_seen,
            "suggested_fix": self.suggested_fix,
            "confidence": self.confidence,
            "approved": self.approved,
        }


@dataclass
class LearningSession:
    """学习会话。"""

    session_id: str
    timestamp: str
    agent_type: str
    task: str
    failures: list[dict[str, Any]]
    patterns_extracted: list[LearningPattern] = field(default_factory=list)
    rules_proposed: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "agent_type": self.agent_type,
            "task": self.task,
            "failures": self.failures,
            "patterns_extracted": [p.to_dict() for p in self.patterns_extracted],
            "rules_proposed": self.rules_proposed,
        }


class FailureAnalyzer:
    """失败分析器 - 分析失败模式。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.3,
        )

    async def analyze_violations(
        self,
        violations: list[dict[str, Any]],
        agent_type: str,
        _context: dict[str, Any] | None = None,
    ) -> list[LearningPattern]:
        """分析违规记录，提取模式。"""
        if not violations:
            return []

        patterns: list[LearningPattern] = []

        # 按规则名称分组
        rule_counts: dict[str, list[dict[str, Any]]] = {}
        for v in violations:
            rule_name = v.get("rule_name", "unknown")
            if rule_name not in rule_counts:
                rule_counts[rule_name] = []
            rule_counts[rule_name].append(v)

        # 对重复出现的违规进行模式分析
        for rule_name, v_list in rule_counts.items():
            if len(v_list) >= 2:  # 出现2次以上才值得学习
                pattern = await self._extract_pattern(rule_name, v_list, agent_type)
                if pattern:
                    patterns.append(pattern)

        return patterns

    async def analyze_evaluation_failure(
        self,
        evaluation_result: dict[str, Any],
        _agent_type: str,
        content: str,
    ) -> list[LearningPattern]:
        """分析评估失败，提取模式。"""
        patterns: list[LearningPattern] = []

        if evaluation_result.get("passed", True):
            return patterns

        scores = evaluation_result.get("scores", [])
        for score in scores:
            if score.get("score", 1.0) < 0.6:
                # 低分维度需要学习
                dimension = score.get("dimension", "unknown")
                issues = score.get("issues", [])

                for issue in issues:
                    pattern = LearningPattern(
                        pattern_id=f"eval_{dimension}_{hash(issue) % 10000:04d}",
                        source=LearningSource.EVALUATION_FAILURE,
                        rule_type=RuleType.CONSTRAINT,
                        description=f"[{dimension}] {issue}",
                        pattern=self._extract_content_pattern(issue, content),
                        severity="medium",
                        last_seen=datetime.now().isoformat(),
                        suggested_fix=f"改进{dimension}维度表现",
                        confidence=0.7,
                    )
                    patterns.append(pattern)

        return patterns

    async def _extract_pattern(
        self,
        rule_name: str,
        violations: list[dict[str, Any]],
        agent_type: str,
    ) -> LearningPattern | None:
        """使用 LLM 提取模式。"""
        # 收集违规样本
        samples = [v.get("message", "") for v in violations[:5]]
        suggestions = [v.get("suggestion", "") for v in violations if v.get("suggestion")]

        prompt = f"""分析以下违规记录，提取一个通用的规则模式。

规则名称：{rule_name}
智能体类型：{agent_type}
违规样本：
{json.dumps(samples, ensure_ascii=False, indent=2)}

改进建议：
{json.dumps(suggestions[:3], ensure_ascii=False, indent=2)}

请输出 JSON 格式：
{{
    "description": "规则描述（简洁明确）",
    "pattern": "正则表达式模式（如果适用）",
    "severity": "critical/high/medium/low",
    "suggested_fix": "修复建议",
    "confidence": 0.0-1.0
}}"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是规则提取专家，负责从失败中学习。"),
                HumanMessage(content=prompt),
            ])

            content = response.content
            if isinstance(content, str) and "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                result = json.loads(json_str)

                return LearningPattern(
                    pattern_id=f"learned_{rule_name}_{datetime.now().strftime('%Y%m%d%H%M')}",
                    source=LearningSource.CONSTRAINT_VIOLATION,
                    rule_type=RuleType.FORBIDDEN_PATTERN,
                    description=result.get("description", ""),
                    pattern=result.get("pattern", ""),
                    severity=result.get("severity", "medium"),
                    occurrence_count=len(violations),
                    last_seen=datetime.now().isoformat(),
                    suggested_fix=result.get("suggested_fix", ""),
                    confidence=result.get("confidence", 0.5),
                )

        except Exception as e:
            import logging

            logging.warning(f"模式提取失败: {e}")

        # 回退：创建基本模式
        return LearningPattern(
            pattern_id=f"learned_{rule_name}_{datetime.now().strftime('%Y%m%d%H%M')}",
            source=LearningSource.CONSTRAINT_VIOLATION,
            rule_type=RuleType.CONSTRAINT,
            description=f"避免 {rule_name} 违规",
            pattern="",
            severity="medium",
            occurrence_count=len(violations),
            last_seen=datetime.now().isoformat(),
            suggested_fix=suggestions[0] if suggestions else "",
            confidence=0.5,
        )

    def _extract_content_pattern(self, issue: str, _content: str) -> str:
        """从内容和问题中提取模式。"""
        # 简单的关键词提取
        keywords = re.findall(r"[\u4e00-\u9fa5]{2,4}", issue)
        if keywords:
            return "|".join(keywords[:3])
        return ""


class RuleProposer:
    """规则提议器 - 基于学习模式提议新规则。"""

    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            temperature=0.5,
        )

    async def propose_rules(
        self,
        patterns: list[LearningPattern],
        existing_rules: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """基于学习模式提议新规则。"""
        if not patterns:
            return []

        # 过滤掉已存在的规则
        new_patterns = [
            p for p in patterns
            if p.description not in str(existing_rules)
            and p.pattern not in str(existing_rules)
        ]

        if not new_patterns:
            return []

        # 高置信度模式直接提议
        proposed: list[dict[str, Any]] = []
        for pattern in new_patterns:
            if pattern.confidence >= 0.7:
                rule = self._pattern_to_rule(pattern)
                proposed.append(rule)

        # 低置信度模式需要 LLM 判断
        low_confidence = [p for p in new_patterns if p.confidence < 0.7]
        if low_confidence:
            llm_proposed = await self._llm_propose_rules(low_confidence, existing_rules)
            proposed.extend(llm_proposed)

        return proposed

    def _pattern_to_rule(self, pattern: LearningPattern) -> dict[str, Any]:
        """将模式转换为规则格式。"""
        return {
            "rule_id": pattern.pattern_id,
            "type": pattern.rule_type.value,
            "description": pattern.description,
            "pattern": pattern.pattern,
            "severity": pattern.severity,
            "source": pattern.source.value,
            "occurrence_count": pattern.occurrence_count,
            "suggested_fix": pattern.suggested_fix,
            "confidence": pattern.confidence,
            "created_at": datetime.now().isoformat(),
        }

    async def _llm_propose_rules(
        self,
        patterns: list[LearningPattern],
        existing_rules: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """使用 LLM 判断是否应该成为规则。"""
        pattern_data = [p.to_dict() for p in patterns]

        prompt = f"""判断以下学习模式是否应该成为正式规则。

现有规则摘要：
- 核心原则数量：{len(existing_rules.get('core_principles', []))}
- 禁止模式数量：{len(existing_rules.get('forbidden_patterns', []))}

候选模式：
{json.dumps(pattern_data, ensure_ascii=False, indent=2)}

请判断每个模式是否值得成为规则，输出 JSON：
{{
    "approved": [
        {{
            "pattern_id": "模式ID",
            "reason": "批准原因",
            "suggested_priority": "critical/high/medium/low"
        }}
    ],
    "rejected": [
        {{
            "pattern_id": "模式ID",
            "reason": "拒绝原因"
        }}
    ]
}}"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="你是规则审核专家，负责判断学习模式的价值。"),
                HumanMessage(content=prompt),
            ])

            content = response.content
            if isinstance(content, str) and "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                result = json.loads(json_str)

                approved_ids = {a["pattern_id"] for a in result.get("approved", [])}
                proposed: list[dict[str, Any]] = []

                for pattern in patterns:
                    if pattern.pattern_id in approved_ids:
                        rule = self._pattern_to_rule(pattern)
                        # 更新优先级
                        for a in result.get("approved", []):
                            if a["pattern_id"] == pattern.pattern_id:
                                rule["severity"] = a.get("suggested_priority", rule["severity"])
                        proposed.append(rule)

                return proposed

        except Exception as e:
            import logging

            logging.warning(f"规则提议失败: {e}")

        return []


class LearningEngine:
    """学习引擎 - 协调学习流程。"""

    def __init__(
        self,
        learning_dir: str = ".claude/learning",
        rules_file: str = "learned_rules.json",
    ):
        self.learning_dir = Path(learning_dir)
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        self.rules_file = self.learning_dir / rules_file

        self.analyzer = FailureAnalyzer()
        self.proposer = RuleProposer()

        self._load_learned_rules()

    def _load_learned_rules(self) -> dict[str, Any]:
        """加载已学习的规则。"""
        if self.rules_file.exists():
            with open(self.rules_file, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        return {"rules": [], "sessions": []}

    def _save_learned_rules(self, data: dict[str, Any]) -> None:
        """保存学习的规则。"""
        with open(self.rules_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def learn_from_violations(
        self,
        violations: list[dict[str, Any]],
        agent_type: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """从违规中学习。

        Args:
            violations: 违规记录列表
            agent_type: 智能体类型
            context: 额外上下文

        Returns:
            新提议的规则列表
        """
        if not violations:
            return []

        # 创建学习会话
        session = LearningSession(
            session_id=f"learn_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            agent_type=agent_type,
            task=context.get("task", "") if context else "",
            failures=violations,
        )

        # 分析违规，提取模式
        patterns = await self.analyzer.analyze_violations(
            violations, agent_type, context
        )
        session.patterns_extracted = patterns

        # 加载现有规则
        existing_rules = self._load_learned_rules()

        # 提议新规则
        proposed_rules = await self.proposer.propose_rules(patterns, existing_rules)
        session.rules_proposed = proposed_rules

        # 记录学习会话
        self._record_session(session)

        return proposed_rules

    async def learn_from_evaluation(
        self,
        evaluation_result: dict[str, Any],
        agent_type: str,
        content: str,
    ) -> list[dict[str, Any]]:
        """从评估失败中学习。"""
        patterns = await self.analyzer.analyze_evaluation_failure(
            evaluation_result, agent_type, content
        )

        if not patterns:
            return []

        existing_rules = self._load_learned_rules()
        proposed_rules = await self.proposer.propose_rules(patterns, existing_rules)

        # 记录
        session = LearningSession(
            session_id=f"eval_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            agent_type=agent_type,
            task="evaluation_analysis",
            failures=[evaluation_result],
            patterns_extracted=patterns,
            rules_proposed=proposed_rules,
        )
        self._record_session(session)

        return proposed_rules

    def _record_session(self, session: LearningSession) -> None:
        """记录学习会话。"""
        data = self._load_learned_rules()

        # 添加会话记录
        sessions = data.get("sessions", [])
        sessions.append(session.to_dict())

        # 只保留最近100个会话
        if len(sessions) > 100:
            sessions = sessions[-100:]

        data["sessions"] = sessions
        self._save_learned_rules(data)

    def approve_rule(self, rule_id: str) -> bool:
        """批准规则。"""
        data = self._load_learned_rules()
        rules = data.get("rules", [])

        for rule in rules:
            if rule.get("rule_id") == rule_id:
                rule["approved"] = True
                rule["approved_at"] = datetime.now().isoformat()
                self._save_learned_rules(data)
                return True

        return False

    def get_approved_rules(self) -> list[dict[str, Any]]:
        """获取已批准的规则。"""
        data = self._load_learned_rules()
        return [r for r in data.get("rules", []) if r.get("approved", False)]

    def get_pending_rules(self) -> list[dict[str, Any]]:
        """获取待批准的规则。"""
        data = self._load_learned_rules()
        return [r for r in data.get("rules", []) if not r.get("approved", False)]


# 全局学习引擎实例
_learning_engine: LearningEngine | None = None


def get_learning_engine() -> LearningEngine:
    """获取全局学习引擎实例。"""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = LearningEngine()
    return _learning_engine


async def learn_from_failure(
    violations: list[dict[str, Any]],
    agent_type: str,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """便捷函数：从失败中学习。"""
    engine = get_learning_engine()
    return await engine.learn_from_violations(violations, agent_type, context)
