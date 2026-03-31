"""知识图谱构建调试追踪模块。

提供详细的构建过程记录，用于调优和问题定位。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TraceStep:
    """单个步骤的追踪记录。"""

    step: str
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class KGTraceLogger:
    """知识图谱构建追踪日志器。

    调试模式下记录每个步骤的详细输入输出，生成 JSON 和 Markdown 报告。
    """

    def __init__(
        self,
        doc_id: str,
        book: str,
        output_dir: str = "data/traces",
        max_content_length: int = 500,
    ):
        """初始化追踪日志器。

        Args:
            doc_id: 文档 ID
            book: 书名
            output_dir: 输出目录
            max_content_length: 内容截断长度
        """
        self.doc_id = doc_id
        self.book = book
        self.output_dir = Path(output_dir)
        self.max_content_length = max_content_length
        self.steps: list[TraceStep] = []
        self.start_time = time.time()

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _truncate(self, content: str) -> str:
        """截断内容到指定长度。"""
        if len(content) > self.max_content_length:
            return content[: self.max_content_length] + "..."
        return content

    def log_step(
        self,
        step: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        """记录一个步骤。

        Args:
            step: 步骤名称
            input_data: 输入数据
            output_data: 输出数据
            duration_ms: 耗时（毫秒）
        """
        self.steps.append(
            TraceStep(
                step=step,
                input_data=input_data or {},
                output_data=output_data or {},
                duration_ms=duration_ms,
            )
        )

    def log_parse_document(
        self,
        chunks: list[Any],
        duration_ms: float = 0.0,
    ) -> None:
        """记录文档解析步骤。

        Args:
            chunks: 分块列表
            duration_ms: 耗时
        """
        output = {
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "content": self._truncate(c.content),
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
            "total_chunks": len(chunks),
        }
        self.log_step("parse_document", output_data=output, duration_ms=duration_ms)

    def log_extract_entities(
        self,
        entities: list[Any],
        duration_ms: float = 0.0,
    ) -> None:
        """记录实体提取步骤。

        Args:
            entities: 实体列表
            duration_ms: 耗时
        """
        output = {
            "entities": [
                {
                    "name": e.name,
                    "type": e.entity_type,
                    "description": self._truncate(e.description) if e.description else "",
                    "confidence": e.confidence,
                }
                for e in entities
            ],
            "total_entities": len(entities),
        }
        self.log_step("extract_entities", output_data=output, duration_ms=duration_ms)

    def log_extract_relations(
        self,
        relations: list[Any],
        duration_ms: float = 0.0,
    ) -> None:
        """记录关系抽取步骤。

        Args:
            relations: 关系列表
            duration_ms: 耗时
        """
        output = {
            "relations": [
                {
                    "source": r.source_entity_name,
                    "target": r.target_entity_name,
                    "type": r.relation_type,
                    "description": self._truncate(r.description) if r.description else "",
                    "confidence": r.confidence,
                }
                for r in relations
            ],
            "total_relations": len(relations),
        }
        self.log_step("extract_relations", output_data=output, duration_ms=duration_ms)

    def log_vectorize(
        self,
        entities_count: int,
        relations_count: int,
        chunks_count: int,
        vector_dim: int,
        duration_ms: float = 0.0,
    ) -> None:
        """记录向量化步骤。

        Args:
            entities_count: 实体数量
            relations_count: 关系数量
            chunks_count: 文本块数量
            vector_dim: 向量维度
            duration_ms: 耗时
        """
        output = {
            "entities_vectorized": entities_count,
            "relations_vectorized": relations_count,
            "chunks_vectorized": chunks_count,
            "vector_dimension": vector_dim,
        }
        self.log_step("vectorize", output_data=output, duration_ms=duration_ms)

    def log_storage(
        self,
        entities_stored: int,
        relations_stored: int,
        chunks_stored: int,
        duration_ms: float = 0.0,
    ) -> None:
        """记录存储步骤。

        Args:
            entities_stored: 存储的实体数量
            relations_stored: 存储的关系数量
            chunks_stored: 存储的文本块数量
            duration_ms: 耗时
        """
        output = {
            "entities_stored": entities_stored,
            "relations_stored": relations_stored,
            "chunks_stored": chunks_stored,
        }
        self.log_step("storage", output_data=output, duration_ms=duration_ms)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "doc_id": self.doc_id,
            "book": self.book,
            "total_time_ms": (time.time() - self.start_time) * 1000,
            "steps": [
                {
                    "step": s.step,
                    "input": s.input_data,
                    "output": s.output_data,
                    "duration_ms": s.duration_ms,
                    "timestamp": s.timestamp,
                }
                for s in self.steps
            ],
        }

    def save_json(self) -> Path:
        """保存为 JSON 文件。

        Returns:
            文件路径
        """
        json_path = self.output_dir / f"{self.doc_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return json_path

    def save_markdown(self) -> Path:
        """保存为 Markdown 报告。

        Returns:
            文件路径
        """
        md_path = self.output_dir / f"{self.doc_id}.md"
        total_time = (time.time() - self.start_time) * 1000

        lines = [
            "# 知识图谱构建报告",
            "",
            f"**文档**: {self.book} | **ID**: {self.doc_id} | "
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"**总耗时**: {total_time:.0f}ms",
            "",
            "---",
            "",
        ]

        for step in self.steps:
            step_title = {
                "parse_document": "文档解析",
                "extract_entities": "实体提取",
                "extract_relations": "关系抽取",
                "vectorize": "向量化",
                "storage": "存储入库",
            }.get(step.step, step.step)

            lines.append(f"## {step_title} ({step.duration_ms:.0f}ms)")
            lines.append("")

            # 根据步骤类型生成不同表格
            if step.step == "parse_document":
                chunks = step.output_data.get("chunks", [])
                if chunks:
                    lines.append("| 块ID | 索引 | 内容预览 |")
                    lines.append("|------|------|----------|")
                    for c in chunks[:20]:  # 最多显示 20 个
                        content_preview = c['content'][:95]
                        lines.append(
                            f"| {c['chunk_id']} | {c['chunk_index']} | "
                            f"{content_preview}... |"
                        )
                    if len(chunks) > 20:
                        lines.append(f"| ... | ... | (共 {len(chunks)} 块) |")

            elif step.step == "extract_entities":
                entities = step.output_data.get("entities", [])
                if entities:
                    lines.append("| 名称 | 类型 | 描述 | 置信度 |")
                    lines.append("|------|------|------|--------|")
                    for e in entities[:30]:  # 最多显示 30 个
                        desc = e["description"]
                        if len(desc) > 50:
                            desc = desc[:50] + "..."
                        lines.append(
                            f"| {e['name']} | {e['type']} | {desc} | "
                            f"{e['confidence']:.2f} |"
                        )
                    if len(entities) > 30:
                        lines.append(f"| ... | ... | ... | (共 {len(entities)} 实体) |")

            elif step.step == "extract_relations":
                relations = step.output_data.get("relations", [])
                if relations:
                    lines.append("| 源实体 | 关系 | 目标实体 | 置信度 |")
                    lines.append("|--------|------|----------|--------|")
                    for r in relations[:30]:
                        lines.append(
                            f"| {r['source']} | {r['type']} | {r['target']} | "
                            f"{r['confidence']:.2f} |"
                        )
                    if len(relations) > 30:
                        lines.append(f"| ... | ... | ... | (共 {len(relations)} 关系) |")

            elif step.step == "vectorize":
                lines.append("```")
                lines.append(f"实体向量: {step.output_data.get('entities_vectorized', 0)} 个")
                lines.append(f"关系向量: {step.output_data.get('relations_vectorized', 0)} 个")
                lines.append(f"文本块向量: {step.output_data.get('chunks_vectorized', 0)} 个")
                lines.append(f"向量维度: {step.output_data.get('vector_dimension', 0)}")
                lines.append("```")

            elif step.step == "storage":
                lines.append("```")
                lines.append(f"存储实体: {step.output_data.get('entities_stored', 0)} 个")
                lines.append(f"存储关系: {step.output_data.get('relations_stored', 0)} 条")
                lines.append(f"存储文本块: {step.output_data.get('chunks_stored', 0)} 个")
                lines.append("```")

            lines.append("")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return md_path

    def finalize(self) -> tuple[Path, Path]:
        """完成追踪并保存报告。

        Returns:
            (JSON 文件路径, Markdown 文件路径)
        """
        json_path = self.save_json()
        md_path = self.save_markdown()
        return json_path, md_path


# 全局追踪器实例
_trace_logger: KGTraceLogger | None = None


def get_trace_logger() -> KGTraceLogger | None:
    """获取当前追踪器实例。"""
    return _trace_logger


def init_trace_logger(
    doc_id: str,
    book: str,
    output_dir: str = "data/traces",
    max_content_length: int = 500,
) -> KGTraceLogger:
    """初始化追踪器。

    Args:
        doc_id: 文档 ID
        book: 书名
        output_dir: 输出目录
        max_content_length: 内容截断长度

    Returns:
        追踪器实例
    """
    global _trace_logger
    _trace_logger = KGTraceLogger(
        doc_id=doc_id,
        book=book,
        output_dir=output_dir,
        max_content_length=max_content_length,
    )
    return _trace_logger


def clear_trace_logger() -> None:
    """清除追踪器实例。"""
    global _trace_logger
    _trace_logger = None
