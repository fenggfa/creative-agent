"""检查点管理器 - 实现上下文重置和状态恢复。

借鉴 Anthropic 的设计：
- 解决"上下文焦虑"问题
- 支持长任务的分段执行
- 通过结构化交接文件传递状态
"""

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
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentCheckpoint:
    """单个 Agent 的检查点。"""

    agent_name: str
    timestamp: str
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """会话状态 - 用于上下文重置时的状态传递。"""

    session_id: str
    task: str
    status: SessionStatus
    created_at: str
    updated_at: str

    # 工作流状态
    current_step: str = ""
    revision_count: int = 0

    # 累积的知识
    materials: str = ""
    drafts: list[str] = field(default_factory=list)
    feedbacks: list[str] = field(default_factory=list)

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
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        """从字典创建。"""
        data["status"] = SessionStatus(data["status"])
        data["checkpoints"] = [
            AgentCheckpoint(**cp) for cp in data.get("checkpoints", [])
        ]
        return cls(**data)


class CheckpointManager:
    """检查点管理器。"""

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or Path(".claude/checkpoints")
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
        metrics: dict[str, Any] | None = None,
    ) -> AgentCheckpoint:
        """保存检查点。"""
        checkpoint = AgentCheckpoint(
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            input_state=input_state,
            output_state=output_state,
            metrics=metrics or {},
        )

        session.checkpoints.append(checkpoint)
        session.updated_at = datetime.now().isoformat()

        # 持久化到文件
        self._save_session(session)

        return checkpoint

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

    def create_handoff_document(self, session: SessionState) -> str:
        """创建交接文档 - 用于上下文重置时传递关键信息。

        这是 Anthropic 推荐的方式：
        与压缩不同，交接文档是完全重置上下文，
        只保留结构化的关键信息。
        """
        # 获取最新草稿和反馈
        latest_draft = session.drafts[-1] if session.drafts else ""
        latest_feedback = session.feedbacks[-1] if session.feedbacks else ""

        handoff = f"""# 会话交接文档

## 基本信息
- 会话 ID: {session.session_id}
- 任务: {session.task}
- 当前步骤: {session.current_step}
- 修改次数: {session.revision_count}
- 状态: {session.status.value}

## 执行历史
{self._format_checkpoints(session.checkpoints)}

## 当前状态

### 已收集素材摘要
{self._summarize_materials(session.materials)}

### 最新草稿（关键部分）
{latest_draft[:1000]}...

### 最新反馈
{latest_feedback}

## 下一步行动
{self._determine_next_action(session)}

---
*此交接文档用于上下文重置后恢复执行状态。*
"""
        return handoff

    def _format_checkpoints(self, checkpoints: list[AgentCheckpoint]) -> str:
        """格式化检查点历史。"""
        if not checkpoints:
            return "暂无执行记录"

        lines = []
        for i, cp in enumerate(checkpoints[-5:], 1):  # 最近 5 条
            lines.append(
                f"{i}. [{cp.timestamp}] {cp.agent_name}: "
                f"输入 {len(cp.input_state)} 项, 输出 {len(cp.output_state)} 项"
            )
        return "\n".join(lines)

    def _summarize_materials(self, materials: str) -> str:
        """总结素材。"""
        if not materials:
            return "暂无素材"
        if len(materials) <= 500:
            return materials
        return materials[:500] + "...(已截断)"

    def _determine_next_action(self, session: SessionState) -> str:
        """确定下一步行动。"""
        if session.status == SessionStatus.COMPLETED:
            return "任务已完成，无需进一步操作"

        if session.current_step == "researcher":
            return "下一步：执行 writer 进行内容创作"

        if session.current_step == "writer":
            return "下一步：执行 reviewer 进行内容审核"

        if session.current_step == "reviewer":
            if session.revision_count >= 3:
                return "已达到最大修改次数，输出最终结果"
            return "根据审核反馈，返回 writer 进行修改"

        return "继续执行工作流"


# 全局检查点管理器实例
checkpoint_manager = CheckpointManager()
