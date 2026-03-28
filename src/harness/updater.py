"""约束更新引擎 - 安全地更新 AGENTS.md 中的约束规则。"""

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class UpdateAction(str, Enum):
    """更新操作类型。"""

    ADD_FORBIDDEN_PATTERN = "add_forbidden_pattern"
    REMOVE_FORBIDDEN_PATTERN = "remove_forbidden_pattern"
    UPDATE_THRESHOLD = "update_threshold"
    ADD_CORE_PRINCIPLE = "add_core_principle"
    MODIFY_CONSTRAINT = "modify_constraint"


class ApprovalStatus(str, Enum):
    """审批状态。"""

    AUTO_APPROVED = "auto_approved"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"


@dataclass
class UpdateRequest:
    """约束更新请求。"""

    action: UpdateAction
    target: str
    value: Any
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: ApprovalStatus = ApprovalStatus.PENDING_APPROVAL


@dataclass
class ViolationPattern:
    """违规模式统计。"""

    pattern: str
    count: int
    last_occurrence: str
    suggestions: list[str] = field(default_factory=list)


# 自动批准的操作白名单
AUTO_APPROVE_ACTIONS: set[UpdateAction] = {
    UpdateAction.ADD_FORBIDDEN_PATTERN,
}

# 需要人工确认的高风险操作
REQUIRES_MANUAL_APPROVAL: set[UpdateAction] = {
    UpdateAction.REMOVE_FORBIDDEN_PATTERN,
    UpdateAction.UPDATE_THRESHOLD,
    UpdateAction.ADD_CORE_PRINCIPLE,
    UpdateAction.MODIFY_CONSTRAINT,
}


class ConstraintUpdateEngine:
    """约束更新引擎 - 分析违规并安全更新约束。"""

    def __init__(self, md_path: str = "AGENTS.md", backup_dir: str = ".constraint_backups"):
        """初始化更新引擎。

        Args:
            md_path: 约束 MD 文件路径
            backup_dir: 备份目录
        """
        self.md_path = Path(md_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self._violation_history: list[dict[str, Any]] = []
        self._pending_updates: list[UpdateRequest] = []

    def record_violation(self, violation: dict[str, Any]) -> None:
        """记录违规信息。

        Args:
            violation: 违规记录字典
        """
        self._violation_history.append({
            **violation,
            "timestamp": datetime.now().isoformat(),
        })

    def analyze_violation_patterns(
        self,
        min_occurrences: int = 3,
    ) -> list[ViolationPattern]:
        """分析违规模式。

        Args:
            min_occurrences: 最小出现次数阈值

        Returns:
            需要关注的违规模式列表
        """
        pattern_counts: dict[str, dict[str, Any]] = {}

        for record in self._violation_history:
            rule_name = record.get("rule_name", "unknown")
            message = record.get("message", "")

            if rule_name not in pattern_counts:
                pattern_counts[rule_name] = {
                    "count": 0,
                    "last_occurrence": "",
                    "messages": set(),
                }

            pattern_counts[rule_name]["count"] += 1
            pattern_counts[rule_name]["last_occurrence"] = record.get("timestamp", "")
            pattern_counts[rule_name]["messages"].add(message)

        # 筛选超过阈值的模式
        patterns = []
        for pattern, data in pattern_counts.items():
            if data["count"] >= min_occurrences:
                patterns.append(ViolationPattern(
                    pattern=pattern,
                    count=data["count"],
                    last_occurrence=data["last_occurrence"],
                    suggestions=list(data["messages"])[:3],  # 最多保留3条示例
                ))

        return sorted(patterns, key=lambda x: x.count, reverse=True)

    def propose_update(
        self,
        action: UpdateAction,
        target: str,
        value: Any,
        reason: str,
    ) -> UpdateRequest:
        """提出更新请求。

        Args:
            action: 更新操作类型
            target: 目标字段
            value: 新值
            reason: 更新原因

        Returns:
            更新请求对象
        """
        request = UpdateRequest(
            action=action,
            target=target,
            value=value,
            reason=reason,
        )

        # 判断是否可以自动批准
        if action in AUTO_APPROVE_ACTIONS:
            request.status = ApprovalStatus.AUTO_APPROVED
        else:
            request.status = ApprovalStatus.PENDING_APPROVAL

        self._pending_updates.append(request)
        return request

    def get_pending_updates(self) -> list[UpdateRequest]:
        """获取待处理的更新请求。"""
        return [r for r in self._pending_updates if r.status == ApprovalStatus.PENDING_APPROVAL]

    def approve_update(self, request_id: str) -> bool:
        """批准更新请求。

        Args:
            request_id: 请求的 timestamp 作为 ID

        Returns:
            是否成功批准
        """
        for request in self._pending_updates:
            if request.timestamp == request_id:
                request.status = ApprovalStatus.AUTO_APPROVED
                return True
        return False

    def reject_update(self, request_id: str) -> bool:
        """拒绝更新请求。

        Args:
            request_id: 请求的 timestamp 作为 ID

        Returns:
            是否成功拒绝
        """
        for request in self._pending_updates:
            if request.timestamp == request_id:
                request.status = ApprovalStatus.REJECTED
                return True
        return False

    def _create_backup(self) -> Path:
        """创建备份文件。

        Returns:
            备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"AGENTS_{timestamp}.md"
        shutil.copy2(self.md_path, backup_path)
        return backup_path

    def _restore_backup(self, backup_path: Path) -> bool:
        """从备份恢复。

        Args:
            backup_path: 备份文件路径

        Returns:
            是否成功恢复
        """
        if backup_path.exists():
            shutil.copy2(backup_path, self.md_path)
            return True
        return False

    def execute_approved_updates(self) -> dict[str, Any]:
        """执行所有已批准的更新。

        Returns:
            执行结果摘要
        """
        if not self.md_path.exists():
            return {"success": False, "error": "MD file not found"}

        # 获取已批准的更新
        approved = [
            r for r in self._pending_updates
            if r.status == ApprovalStatus.AUTO_APPROVED
        ]

        if not approved:
            return {"success": True, "executed": 0, "message": "No updates to execute"}

        # 创建备份
        backup_path = self._create_backup()

        try:
            content = self.md_path.read_text(encoding="utf-8")

            for request in approved:
                content = self._apply_update(content, request)

            # 写入更新后的内容
            self.md_path.write_text(content, encoding="utf-8")

            # 清理已执行的请求
            self._pending_updates = [
                r for r in self._pending_updates
                if r.status != ApprovalStatus.AUTO_APPROVED
            ]

            return {
                "success": True,
                "executed": len(approved),
                "backup_path": str(backup_path),
            }

        except Exception as e:
            # 恢复备份
            self._restore_backup(backup_path)
            return {
                "success": False,
                "error": str(e),
                "backup_restored": True,
            }

    def _apply_update(self, content: str, request: UpdateRequest) -> str:
        """应用单个更新到内容。

        Args:
            content: 当前 MD 内容
            request: 更新请求

        Returns:
            更新后的内容
        """
        if request.action == UpdateAction.ADD_FORBIDDEN_PATTERN:
            return self._add_forbidden_pattern(content, request.value)

        elif request.action == UpdateAction.REMOVE_FORBIDDEN_PATTERN:
            return self._remove_forbidden_pattern(content, request.target)

        elif request.action == UpdateAction.UPDATE_THRESHOLD:
            return self._update_threshold(content, request.target, request.value)

        return content

    def _add_forbidden_pattern(self, content: str, pattern: str) -> str:
        """添加禁止模式到约束边界表格。"""
        # 查找约束边界表格
        table_pattern = r"(##\s*约束边界\s*\n\|.*?\n\|.*?\n)"
        match = re.search(table_pattern, content)

        if match:
            # 在表格后添加新行
            insert_pos = match.end()
            new_row = f"| {pattern} | 自动添加 |\n"
            return content[:insert_pos] + new_row + content[insert_pos:]

        return content

    def _remove_forbidden_pattern(self, content: str, pattern: str) -> str:
        """从约束边界表格移除禁止模式。"""
        # 匹配包含该模式的表格行
        row_pattern = rf"\| {re.escape(pattern)} \|.*\n"
        return re.sub(row_pattern, "", content)

    def _update_threshold(self, content: str, threshold_name: str, value: float) -> str:
        """更新通过阈值。"""
        if threshold_name == "total_threshold":
            return re.sub(
                r"(通过标准[：:]\s*总分\s*≥?\s*)([\d.]+)",
                rf"\g<1>{value}",
                content,
            )
        return content

    def get_update_history(self) -> list[dict[str, Any]]:
        """获取更新历史。"""
        return self._violation_history.copy()


# 全局更新引擎实例
_engine_instance: ConstraintUpdateEngine | None = None


def get_update_engine(
    md_path: str = "AGENTS.md",
    backup_dir: str = ".constraint_backups",
) -> ConstraintUpdateEngine:
    """获取全局更新引擎实例。"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ConstraintUpdateEngine(md_path, backup_dir)
    return _engine_instance
