"""智能体记忆模块 - 持久化"什么情况下什么方法有效"。

Harness Engineering 核心要求：
- 解决"换班失忆"
- 记录成功/失败案例
- 提供历史参考

用途：
- 记录每个智能体的成功/失败经验
- 在相似任务时提供参考
- 支持模式匹配和经验复用
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class OutcomeType(str, Enum):
    """结果类型。"""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


class TaskCategory(str, Enum):
    """任务类别。"""

    CREATION = "creation"  # 创作
    REVISION = "revision"  # 修改
    ANALYSIS = "analysis"  # 分析
    PLANNING = "planning"  # 规划


@dataclass
class AgentExperience:
    """智能体经验记录。"""

    experience_id: str
    agent_type: str
    task_category: TaskCategory
    task_description: str
    outcome: OutcomeType
    timestamp: str

    # 任务特征
    task_features: dict[str, Any] = field(default_factory=dict)

    # 使用的策略
    strategy_used: str = ""
    tools_used: list[str] = field(default_factory=list)

    # 结果详情
    result_summary: str = ""
    score: float = 0.0
    violations: list[str] = field(default_factory=list)

    # 学到的教训
    lessons_learned: list[str] = field(default_factory=list)

    # 可复用的内容
    reusable_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "experience_id": self.experience_id,
            "agent_type": self.agent_type,
            "task_category": self.task_category.value,
            "task_description": self.task_description,
            "outcome": self.outcome.value,
            "timestamp": self.timestamp,
            "task_features": self.task_features,
            "strategy_used": self.strategy_used,
            "tools_used": self.tools_used,
            "result_summary": self.result_summary,
            "score": self.score,
            "violations": self.violations,
            "lessons_learned": self.lessons_learned,
            "reusable_patterns": self.reusable_patterns,
        }


@dataclass
class PatternMatch:
    """模式匹配结果。"""

    experience: AgentExperience
    similarity: float
    matched_features: list[str]


class AgentMemory:
    """智能体记忆系统。"""

    def __init__(
        self,
        memory_dir: str = ".claude/memory",
        experiences_file: str = "agent_experiences.json",
    ):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.experiences_file = self.memory_dir / experiences_file

        self._experiences: list[AgentExperience] = []
        self._load_experiences()

    def _load_experiences(self) -> None:
        """加载历史经验。"""
        if self.experiences_file.exists():
            with open(self.experiences_file, encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("experiences", []):
                    try:
                        exp = AgentExperience(
                            experience_id=item["experience_id"],
                            agent_type=item["agent_type"],
                            task_category=TaskCategory(item["task_category"]),
                            task_description=item["task_description"],
                            outcome=OutcomeType(item["outcome"]),
                            timestamp=item["timestamp"],
                            task_features=item.get("task_features", {}),
                            strategy_used=item.get("strategy_used", ""),
                            tools_used=item.get("tools_used", []),
                            result_summary=item.get("result_summary", ""),
                            score=item.get("score", 0.0),
                            violations=item.get("violations", []),
                            lessons_learned=item.get("lessons_learned", []),
                            reusable_patterns=item.get("reusable_patterns", []),
                        )
                        self._experiences.append(exp)
                    except (KeyError, ValueError):
                        continue

    def _save_experiences(self) -> None:
        """保存经验到文件。"""
        data = {
            "experiences": [exp.to_dict() for exp in self._experiences],
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.experiences_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_experience(
        self,
        agent_type: str,
        task_category: TaskCategory,
        task_description: str,
        outcome: OutcomeType,
        task_features: dict[str, Any] | None = None,
        strategy_used: str = "",
        tools_used: list[str] | None = None,
        result_summary: str = "",
        score: float = 0.0,
        violations: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        reusable_patterns: list[str] | None = None,
    ) -> AgentExperience:
        """记录经验。"""
        experience = AgentExperience(
            experience_id=f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self._experiences)}",
            agent_type=agent_type,
            task_category=task_category,
            task_description=task_description,
            outcome=outcome,
            timestamp=datetime.now().isoformat(),
            task_features=task_features or {},
            strategy_used=strategy_used,
            tools_used=tools_used or [],
            result_summary=result_summary,
            score=score,
            violations=violations or [],
            lessons_learned=lessons_learned or [],
            reusable_patterns=reusable_patterns or [],
        )

        self._experiences.append(experience)
        self._save_experiences()

        return experience

    def find_similar_experiences(
        self,
        agent_type: str,
        task_description: str,
        task_features: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> list[PatternMatch]:
        """查找相似经验。

        Args:
            agent_type: 智能体类型
            task_description: 任务描述
            task_features: 任务特征
            limit: 返回数量限制

        Returns:
            相似经验列表
        """
        matches: list[PatternMatch] = []

        for exp in self._experiences:
            # 只匹配相同类型的智能体
            if exp.agent_type != agent_type:
                continue

            # 计算相似度
            similarity, matched_features = self._calculate_similarity(
                task_description, task_features or {}, exp
            )

            if similarity > 0.3:  # 相似度阈值
                matches.append(PatternMatch(
                    experience=exp,
                    similarity=similarity,
                    matched_features=matched_features,
                ))

        # 按相似度排序
        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches[:limit]

    def _calculate_similarity(
        self,
        task_description: str,
        task_features: dict[str, Any],
        experience: AgentExperience,
    ) -> tuple[float, list[str]]:
        """计算相似度。"""
        similarity = 0.0
        matched_features: list[str] = []

        # 1. 描述相似度（关键词匹配）
        desc_keywords = set(task_description.lower().split())
        exp_keywords = set(experience.task_description.lower().split())
        keyword_overlap = len(desc_keywords & exp_keywords)
        if keyword_overlap > 0:
            max_len = max(len(desc_keywords), len(exp_keywords), 1)
            desc_similarity = keyword_overlap / max_len
            similarity += desc_similarity * 0.4
            if keyword_overlap >= 2:
                matched_features.append(f"关键词匹配: {keyword_overlap}个")

        # 2. 特征相似度
        if task_features and experience.task_features:
            feature_matches = 0
            for key, value in task_features.items():
                if key in experience.task_features and experience.task_features[key] == value:
                    feature_matches += 1
                    matched_features.append(f"特征匹配: {key}")

            if feature_matches > 0:
                feature_similarity = feature_matches / max(len(task_features), 1)
                similarity += feature_similarity * 0.3

        # 3. 任务类别匹配
        # 通过特征推断类别

        return similarity, matched_features

    def get_successful_patterns(
        self,
        agent_type: str,
        task_category: TaskCategory | None = None,
    ) -> list[str]:
        """获取成功模式。

        Args:
            agent_type: 智能体类型
            task_category: 任务类别（可选）

        Returns:
            成功模式列表
        """
        patterns: list[str] = []

        for exp in self._experiences:
            if exp.agent_type != agent_type:
                continue
            if exp.outcome != OutcomeType.SUCCESS:
                continue
            if task_category and exp.task_category != task_category:
                continue

            patterns.extend(exp.reusable_patterns)

        # 去重
        return list(dict.fromkeys(patterns))

    def get_lessons_learned(
        self,
        agent_type: str,
        outcome: OutcomeType | None = OutcomeType.FAILURE,
    ) -> list[str]:
        """获取教训。

        Args:
            agent_type: 智能体类型
            outcome: 结果类型

        Returns:
            教训列表
        """
        lessons: list[str] = []

        for exp in self._experiences:
            if exp.agent_type != agent_type:
                continue
            if outcome and exp.outcome != outcome:
                continue

            lessons.extend(exp.lessons_learned)

        return list(dict.fromkeys(lessons))

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息。"""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0}

        by_agent: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        total_score = 0.0

        for exp in self._experiences:
            by_agent[exp.agent_type] = by_agent.get(exp.agent_type, 0) + 1
            by_outcome[exp.outcome.value] = by_outcome.get(exp.outcome.value, 0) + 1
            total_score += exp.score

        return {
            "total": total,
            "by_agent": by_agent,
            "by_outcome": by_outcome,
            "average_score": total_score / total,
            "success_rate": by_outcome.get("success", 0) / total,
        }

    def cleanup_old_experiences(self, keep_recent: int = 1000) -> int:
        """清理旧经验。

        Args:
            keep_recent: 保留最近的数量

        Returns:
            删除的数量
        """
        if len(self._experiences) <= keep_recent:
            return 0

        removed = len(self._experiences) - keep_recent
        self._experiences = self._experiences[-keep_recent:]
        self._save_experiences()

        return removed


class MemoryEnhancedAgent:
    """记忆增强的智能体基类。

    提供记忆查询和记录的便捷方法。
    """

    def __init__(self, agent_type: str) -> None:
        self.agent_type = agent_type
        self.memory = AgentMemory()

    def query_similar_cases(
        self,
        task_description: str,
        task_features: dict[str, Any] | None = None,
    ) -> list[PatternMatch]:
        """查询相似案例。"""
        return self.memory.find_similar_experiences(
            self.agent_type,
            task_description,
            task_features,
        )

    def record_success(
        self,
        task_description: str,
        strategy_used: str,
        result_summary: str,
        score: float,
        reusable_patterns: list[str] | None = None,
    ) -> AgentExperience:
        """记录成功经验。"""
        return self.memory.record_experience(
            agent_type=self.agent_type,
            task_category=TaskCategory.CREATION,
            task_description=task_description,
            outcome=OutcomeType.SUCCESS,
            strategy_used=strategy_used,
            result_summary=result_summary,
            score=score,
            reusable_patterns=reusable_patterns,
        )

    def record_failure(
        self,
        task_description: str,
        violations: list[str],
        lessons_learned: list[str],
        score: float = 0.0,
    ) -> AgentExperience:
        """记录失败经验。"""
        return self.memory.record_experience(
            agent_type=self.agent_type,
            task_category=TaskCategory.CREATION,
            task_description=task_description,
            outcome=OutcomeType.FAILURE,
            violations=violations,
            lessons_learned=lessons_learned,
            score=score,
        )

    def get_successful_strategies(self) -> list[str]:
        """获取成功策略。"""
        return self.memory.get_successful_patterns(self.agent_type)


# 全局记忆实例
_memory: AgentMemory | None = None


def get_agent_memory() -> AgentMemory:
    """获取全局记忆实例。"""
    global _memory
    if _memory is None:
        _memory = AgentMemory()
    return _memory
