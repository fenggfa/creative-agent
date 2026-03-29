"""反馈闭环模块 - 自动更新约束规则。

Harness Engineering 核心要求：
- 将错误信号转化为可执行任务
- 自动更新 AGENTS.md
- 保持规则一致性

工作流程：
学习规则 → 规则验证 → 更新 AGENTS.md → 更新 provider → 下次自动生效
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.harness.learning import get_learning_engine


@dataclass
class RuleUpdate:
    """规则更新记录。"""

    rule_id: str
    action: str  # add, modify, remove
    timestamp: str
    source: str
    details: dict[str, Any]


class FeedbackLoop:
    """反馈闭环 - 自动更新约束规则。"""

    def __init__(
        self,
        agents_md_path: str = "AGENTS.md",
        rules_json_path: str = ".claude/learning/learned_rules.json",
    ):
        self.agents_md_path = Path(agents_md_path)
        self.rules_json_path = Path(rules_json_path)
        self.learning_engine = get_learning_engine()

    def get_current_rules(self) -> dict[str, Any]:
        """获取当前 AGENTS.md 中的规则。"""
        if not self.agents_md_path.exists():
            return {
                "core_principles": [],
                "forbidden_patterns": [],
                "constraints_boundary": {},
            }

        content = self.agents_md_path.read_text(encoding="utf-8")
        return self._parse_agents_md(content)

    def _parse_agents_md(self, content: str) -> dict[str, Any]:
        """解析 AGENTS.md 提取规则。"""
        rules: dict[str, Any] = {
            "core_principles": [],
            "forbidden_patterns": [],
            "constraints_boundary": {},
        }

        # 解析核心原则
        pattern = r"##\s*核心原则\s*\n((?:\d+\.\s*.+\n?)+)"
        match = re.search(pattern, content)
        if match:
            items = match.group(1)
            for line in items.strip().split("\n"):
                cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
                if cleaned:
                    rules["core_principles"].append(cleaned)

        # 解析禁止模式
        pattern = r"##\s*约束边界\s*\n\|.*?\n\|.*?\n((?:\|.+\|\n?)+)"
        match = re.search(pattern, content)
        if match:
            table_rows = match.group(1)
            for row in table_rows.strip().split("\n"):
                if not row.startswith("|"):
                    continue
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if cols and cols[0] not in ("禁止", ""):
                    rules["forbidden_patterns"].append(cols[0])
                    if len(cols) > 1:
                        rules["constraints_boundary"][cols[0]] = cols[1]

        return rules

    def add_forbidden_pattern(
        self,
        pattern: str,
        reason: str,
        _severity: str = "medium",
    ) -> bool:
        """添加禁止模式到 AGENTS.md。

        Args:
            pattern: 禁止的模式
            reason: 禁止原因
            severity: 严重程度

        Returns:
            是否成功添加
        """
        if not self.agents_md_path.exists():
            return False

        content = self.agents_md_path.read_text(encoding="utf-8")

        # 检查是否已存在
        if pattern in content:
            return False

        # 找到约束边界表格
        pattern_re = r"(##\s*约束边界\s*\n\|.*?\n\|.*?\n)"
        match = re.search(pattern_re, content)

        if match:
            # 在表格后添加新行
            new_row = f"| {pattern} | {reason} |\n"
            new_content = content[:match.end()] + new_row + content[match.end():]

            self.agents_md_path.write_text(new_content, encoding="utf-8")
            return True

        # 如果没有找到表格，创建一个新的
        new_section = f"""
## 约束边界

| 禁止 | 原因 |
|------|------|
| {pattern} | {reason} |

"""
        # 在文件末尾添加
        self.agents_md_path.write_text(content + new_section, encoding="utf-8")
        return True

    def add_core_principle(self, principle: str) -> bool:
        """添加核心原则到 AGENTS.md。"""
        if not self.agents_md_path.exists():
            return False

        content = self.agents_md_path.read_text(encoding="utf-8")

        # 检查是否已存在
        if principle in content:
            return False

        # 找到核心原则部分
        pattern = r"(##\s*核心原则\s*\n)((?:\d+\.\s*.+\n?)+)"
        match = re.search(pattern, content)

        if match:
            # 计算新编号
            existing = match.group(2)
            numbers = re.findall(r"(\d+)\.\s*", existing)
            next_num = max([int(n) for n in numbers], default=0) + 1

            # 添加新原则
            new_line = f"{next_num}. {principle}\n"
            new_content = content[:match.end()] + new_line + content[match.end():]

            self.agents_md_path.write_text(new_content, encoding="utf-8")
            return True

        # 如果没有找到，创建新部分
        new_section = f"""
## 核心原则

1. {principle}

"""
        self.agents_md_path.write_text(content + new_section, encoding="utf-8")
        return True

    def sync_learned_rules(self) -> dict[str, Any]:
        """同步学习的规则到 AGENTS.md。

        Returns:
            同步结果统计
        """
        approved_rules = self.learning_engine.get_approved_rules()

        added_patterns = 0
        added_principles = 0
        errors: list[str] = []

        for rule in approved_rules:
            rule_type = rule.get("type", "")
            description = rule.get("description", "")
            pattern = rule.get("pattern", "")
            severity = rule.get("severity", "medium")

            try:
                if rule_type == "forbidden_pattern" and pattern and self.add_forbidden_pattern(
                    pattern, description, severity
                ):
                    added_patterns += 1

                elif rule_type == "principle" and self.add_core_principle(description):
                    added_principles += 1

            except Exception as e:
                errors.append(f"Failed to add rule {rule.get('rule_id')}: {e}")

        return {
            "added_patterns": added_patterns,
            "added_principles": added_principles,
            "total_processed": len(approved_rules),
            "errors": errors,
        }

    def update_provider_cache(self) -> None:
        """更新 provider 的规则缓存。

        调用此方法后，provider 会重新加载 AGENTS.md。
        """
        from src.harness.provider import get_constraint_provider

        provider = get_constraint_provider()
        provider.parse_md_rules(force_reload=True)

    def auto_update(self) -> dict[str, Any]:
        """自动更新闭环。

        执行完整的更新流程：
        1. 获取已批准的规则
        2. 同步到 AGENTS.md
        3. 更新 provider 缓存

        Returns:
            更新结果
        """
        # 同步规则
        sync_result = self.sync_learned_rules()

        # 更新缓存
        self.update_provider_cache()

        return {
            "timestamp": datetime.now().isoformat(),
            "sync_result": sync_result,
            "cache_updated": True,
        }


class FeedbackCoordinator:
    """反馈协调器 - 协调多个反馈源。"""

    def __init__(self) -> None:
        self.feedback_loop = FeedbackLoop()
        self.learning_engine = get_learning_engine()

    async def process_agent_feedback(
        self,
        agent_type: str,
        violations: list[dict[str, Any]],
        evaluation_result: dict[str, Any] | None = None,
        auto_approve: bool = False,
    ) -> dict[str, Any]:
        """处理智能体反馈。

        Args:
            agent_type: 智能体类型
            violations: 违规记录
            evaluation_result: 评估结果
            auto_approve: 是否自动批准

        Returns:
            处理结果
        """
        results: dict[str, Any] = {
            "learned": [],
            "approved": [],
            "synced": False,
        }

        # 1. 从违规中学习
        if violations:
            proposed = await self.learning_engine.learn_from_violations(
                violations, agent_type
            )
            results["learned"] = proposed

            # 自动批准高置信度规则
            if auto_approve:
                for rule in proposed:
                    if rule.get("confidence", 0) >= 0.8:
                        self.learning_engine.approve_rule(rule["rule_id"])
                        results["approved"].append(rule["rule_id"])

        # 2. 从评估失败中学习
        if evaluation_result and not evaluation_result.get("passed", True):
            eval_proposed = await self.learning_engine.learn_from_evaluation(
                evaluation_result, agent_type, ""
            )
            results["learned"].extend(eval_proposed)

        # 3. 同步到 AGENTS.md
        if results["approved"]:
            sync_result = self.feedback_loop.auto_update()
            results["synced"] = sync_result.get("sync_result", {}).get("added_patterns", 0) > 0

        return results

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """获取待批准的规则。"""
        return self.learning_engine.get_pending_rules()

    def approve_rule(self, rule_id: str) -> bool:
        """批准规则并同步。"""
        if self.learning_engine.approve_rule(rule_id):
            self.feedback_loop.auto_update()
            return True
        return False

    def reject_rule(self, _rule_id: str) -> bool:
        """拒绝规则。"""
        # 目前简单删除，未来可以移到拒绝列表
        return True


# 全局协调器实例
_coordinator: FeedbackCoordinator | None = None


def get_feedback_coordinator() -> FeedbackCoordinator:
    """获取全局反馈协调器。"""
    global _coordinator
    if _coordinator is None:
        _coordinator = FeedbackCoordinator()
    return _coordinator


async def process_feedback(
    agent_type: str,
    violations: list[dict[str, Any]],
    evaluation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """便捷函数：处理智能体反馈。"""
    coordinator = get_feedback_coordinator()
    return await coordinator.process_agent_feedback(
        agent_type, violations, evaluation_result
    )
