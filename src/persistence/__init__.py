"""状态持久化模块 - 解决长任务的"换班失忆"问题。

Harness Engineering 核心要求：
- 每个 Session 都是"纯净脑"，缺乏决策路径的连续性
- 压缩后的上下文彻底丢失了关键的"为什么这么做"
- 需要结构化交接文件传递状态

设计借鉴 Anthropic 的做法：
- 与压缩不同，交接文档是完全重置上下文
- 只保留结构化的关键信息
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SessionStatus(str, Enum):
    """会话状态。"""

    RUNNING = "running"
    PAUSED = "paused"  # 上下文重置暂停
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentCheckpoint:
    """单个 Agent 的检查点。"""

    agent_name: str
    timestamp: str
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    reasoning: str = ""  # 关键：记录"为什么这么做"
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """会话状态 - 用于上下文重置时的状态传递。"""

    session_id: str
    task: str
    status: SessionStatus
    created_at: str
    updated_at: str

    # 工作流进度
    current_step: str = ""
    revision_count: int = 0

    # 累积的知识（关键信息摘要，不是完整内容）
    materials_summary: str = ""  # 素材摘要（非完整素材）
    key_decisions: list[str] = field(default_factory=list)  # 关键决策记录

    # 草稿历史（只保留关键版本）
    latest_draft_summary: str = ""  # 最新草稿摘要
    key_feedback: list[str] = field(default_factory=list)  # 关键反馈

    # 检查点历史
    checkpoints: list[AgentCheckpoint] = field(default_factory=list)

    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        data = asdict(self)
        data["status"] = self.status.value
        data["checkpoints"] = [asdict(cp) for cp in self.checkpoints]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """从字典创建。"""
        data = data.copy()  # 避免修改原始数据
        data["status"] = SessionStatus(data["status"])
        data["checkpoints"] = [
            AgentCheckpoint(**cp) for cp in data.get("checkpoints", [])
        ]
        return cls(**data)


class CheckpointManager:
    """检查点管理器 - Harness 持久化状态核心。"""

    def __init__(self, storage_dir: Path | str = ".claude/sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, task: str) -> SessionState:
        """创建新会话。"""
        now = datetime.now().isoformat()
        return SessionState(
            session_id=str(uuid.uuid4())[:8],
            task=task,
            status=SessionStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )

    def save_checkpoint(
        self,
        session: SessionState,
        agent_name: str,
        input_state: dict[str, Any],
        output_state: dict[str, Any],
        reasoning: str = "",
        metrics: dict[str, Any] | None = None,
    ) -> AgentCheckpoint:
        """保存检查点。

        Args:
            session: 会话状态
            agent_name: Agent 名称
            input_state: 输入状态
            output_state: 输出状态
            reasoning: 关键决策原因（解决"为什么这么做"）
            metrics: 执行指标
        """
        checkpoint = AgentCheckpoint(
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            input_state=self._summarize_state(input_state),
            output_state=self._summarize_state(output_state),
            reasoning=reasoning,
            metrics=metrics or {},
        )

        session.checkpoints.append(checkpoint)
        session.updated_at = datetime.now().isoformat()

        # 持久化到文件
        self._save_session(session)

        return checkpoint

    def _summarize_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """摘要状态，避免存储过多内容。"""
        summarized: dict[str, Any] = {}
        for key, value in state.items():
            if isinstance(value, str) and len(value) > 500:
                # 长文本只保留摘要
                summarized[key] = {
                    "_type": "summary",
                    "length": len(value),
                    "preview": value[:200] + "...",
                }
            elif isinstance(value, dict | list) and len(str(value)) > 1000:
                summarized[key] = {
                    "_type": "truncated",
                    "keys": list(value.keys()) if isinstance(value, dict) else None,
                    "length": len(value),
                }
            else:
                summarized[key] = value
        return summarized

    def _save_session(self, session: SessionState) -> None:
        """保存会话到文件。"""
        file_path = self.storage_dir / f"{session.session_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def load_session(self, session_id: str) -> SessionState | None:
        """加载会话。"""
        file_path = self.storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, encoding="utf-8") as f:
            return SessionState.from_dict(json.load(f))

    def list_sessions(self, status: SessionStatus | None = None) -> list[SessionState]:
        """列出会话。"""
        sessions = []
        for file_path in self.storage_dir.glob("*.json"):
            session = self.load_session(file_path.stem)
            if session and (status is None or session.status == status):
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def create_handoff_document(self, session: SessionState) -> str:
        """创建交接文档 - 用于上下文重置时传递关键信息。

        这是 Harness Engineering 的核心：
        与压缩不同，交接文档是完全重置上下文，
        只保留结构化的关键信息。
        """
        handoff = f"""# 会话交接文档

> 此文档用于上下文重置后恢复执行状态。

## 基本信息

| 字段 | 值 |
|------|-----|
| 会话 ID | `{session.session_id}` |
| 任务 | {session.task} |
| 当前步骤 | {session.current_step or '未开始'} |
| 修改次数 | {session.revision_count} |
| 状态 | {session.status.value} |

## 关键决策

记录"为什么这么做"，避免下一轮 Agent 猜测：

{self._format_decisions(session.key_decisions)}

## 素材摘要

{session.materials_summary or '暂无素材摘要'}

## 最新草稿摘要

{session.latest_draft_summary or '暂无草稿'}

## 关键反馈

{self._format_feedback(session.key_feedback)}

## 执行历史

{self._format_checkpoints(session.checkpoints)}

## 下一步行动

{self._determine_next_action(session)}

---
*创建时间: {datetime.now().isoformat()}*
"""
        return handoff

    def _format_decisions(self, decisions: list[str]) -> str:
        """格式化决策记录。"""
        if not decisions:
            return "暂无关键决策记录"
        return "\n".join(f"- {d}" for d in decisions[-10:])  # 最近 10 条

    def _format_feedback(self, feedbacks: list[str]) -> str:
        """格式化反馈记录。"""
        if not feedbacks:
            return "暂无反馈记录"
        return "\n".join(f"- {fb}" for fb in feedbacks[-5:])  # 最近 5 条

    def _format_checkpoints(self, checkpoints: list[AgentCheckpoint]) -> str:
        """格式化检查点历史。"""
        if not checkpoints:
            return "暂无执行记录"

        lines = []
        for i, cp in enumerate(checkpoints[-5:], 1):
            reasoning = f": {cp.reasoning[:50]}..." if cp.reasoning else ""
            lines.append(f"{i}. [{cp.timestamp[:16]}] {cp.agent_name}{reasoning}")
        return "\n".join(lines)

    def _determine_next_action(self, session: SessionState) -> str:
        """确定下一步行动。"""
        if session.status == SessionStatus.COMPLETED:
            return "✅ 任务已完成，无需进一步操作"

        if session.status == SessionStatus.FAILED:
            return "❌ 任务失败，需要人工介入"

        step_actions = {
            "researcher": "下一步：执行 writer 进行内容创作",
            "writer": "下一步：执行 reviewer 进行内容审核",
            "reviewer": "下一步：根据审核结果，决定是否继续修改",
        }

        return step_actions.get(session.current_step, "继续执行工作流")

    def record_decision(self, session: SessionState, decision: str) -> None:
        """记录关键决策（解决"为什么这么做"）。"""
        session.key_decisions.append(f"[{datetime.now().isoformat()[:16]}] {decision}")
        session.updated_at = datetime.now().isoformat()
        self._save_session(session)

    def record_feedback(self, session: SessionState, feedback: str) -> None:
        """记录关键反馈。"""
        session.key_feedback.append(f"[{datetime.now().isoformat()[:16]}] {feedback}")
        session.updated_at = datetime.now().isoformat()
        self._save_session(session)


# 全局检查点管理器实例
checkpoint_manager = CheckpointManager()
