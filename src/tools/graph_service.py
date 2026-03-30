"""知识图谱服务层 - 基于 Neo4j + SQLite FTS5。

设计原则：
===========================================
1. 统一图谱：所有数据在一个图谱，通过 book/source 区分
2. 跨书搜索：创作时搜索所有书籍的素材
3. 按书过滤：支持指定 book 参数

存储架构：
- Neo4j：图数据库，存储实体和关系
- SQLite FTS5：实体索引，快速全文检索（BM25 排序）
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from src.tools.kg_storage.graph_service import LocalKGService, get_local_kg_service

logger = logging.getLogger(__name__)

# 本地图谱服务实例（懒加载）
_local_kg_service: LocalKGService | None = None


async def _get_local_kg() -> LocalKGService:
    """获取本地图谱服务（懒加载）。"""
    global _local_kg_service
    if _local_kg_service is None:
        _local_kg_service = get_local_kg_service()
        await _local_kg_service.connect()
    return _local_kg_service


# ============================================================================
# 第一层：直接编程 API（固定流程，100%可靠）
# ============================================================================


async def fetch_materials_for_writing(
    task: str,
    book: str | None = None,
) -> str:
    """获取创作所需的素材。

    Args:
        task: 创作任务
        book: 书名过滤（可选，不指定则搜索所有书）

    Returns:
        格式化的素材内容
    """
    if not task or len(task.strip()) < 2:
        return "任务描述太短"

    task = task.strip()

    try:
        local_kg = await _get_local_kg()
        # 默认搜索素材（source=material）
        result = await local_kg.query(task, book=book, source="material")
        return result
    except Exception as e:
        logger.error(f"图谱查询失败: {e}")
        return f"查询失败: {e}"


async def save_creative_content(
    content: str,
    title: str,
    book: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """保存创作内容到知识图谱。

    Args:
        content: 创作内容
        title: 标题
        book: 所属书籍
        metadata: 可选元数据

    Returns:
        保存结果
    """
    if not content or len(content.strip()) < 20:
        return {"success": False, "error": "内容太短"}

    if not title or not title.strip():
        return {"success": False, "error": "标题不能为空"}

    if not book or not book.strip():
        return {"success": False, "error": "书名不能为空"}

    try:
        from src.agents.kg_builder import build_knowledge_graph

        enriched = f"""【{title}】
创作时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{f'元数据: {metadata}' if metadata else ''}

{content.strip()}"""

        local_kg = await _get_local_kg()
        result = await build_knowledge_graph(
            document=enriched,
            book=book,
            source="creative",
            neo4j_client=local_kg.neo4j,
            entity_index=local_kg.index,
        )

        return {
            "success": result.success,
            "title": title,
            "book": book,
            "entities_count": len(result.entities),
            "relations_count": len(result.relations),
            "message": "保存成功" if result.success else result.error_message,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def upload_document(
    content: str,
    book: str,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """上传文档构建知识图谱（素材入库）。

    Args:
        content: 文档内容
        book: 所属书籍
        doc_id: 文档 ID（可选）

    Returns:
        构建结果
    """
    if not content or len(content.strip()) < 50:
        return {"success": False, "error": "内容太短"}

    if not book or not book.strip():
        return {"success": False, "error": "书名不能为空"}

    try:
        from src.agents.kg_builder import build_knowledge_graph

        local_kg = await _get_local_kg()
        result = await build_knowledge_graph(
            document=content,
            book=book,
            source="material",
            doc_id=doc_id,
            neo4j_client=local_kg.neo4j,
            entity_index=local_kg.index,
        )

        return {
            "success": result.success,
            "book": book,
            "doc_id": result.doc_id,
            "entities_count": len(result.entities),
            "relations_count": len(result.relations),
            "chunks_processed": result.chunks_processed,
            "build_time": result.build_time_seconds,
            "message": "构建成功" if result.success else result.error_message,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_books() -> list[str]:
    """列出所有书籍。"""
    try:
        local_kg = await _get_local_kg()
        return await local_kg.list_books()
    except Exception as e:
        logger.error(f"获取书籍列表失败: {e}")
        return []


async def get_stats(book: str | None = None) -> dict[str, Any]:
    """获取图谱统计信息。

    Args:
        book: 按书名过滤（可选）
    """
    try:
        local_kg = await _get_local_kg()
        return await local_kg.get_stats(book)
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return {"error": str(e)}


# ============================================================================
# 第二层：工具定义（动态决策场景，LLM 选择）
# ============================================================================


@tool
async def ask_knowledge_graph(
    question: str,
    book: str | None = None,
) -> str:
    """向知识图谱提问。

    适用场景：
    - 用户问"图谱里有什么？"
    - 用户问"查一下孙悟空的关系网络"
    - 用户自由探索图谱

    Args:
        question: 问题
        book: 书名过滤（可选）

    Returns:
        图谱回答
    """
    if not question or len(question.strip()) < 2:
        return "问题太短，请提供更具体的问题"

    return await fetch_materials_for_writing(question, book=book)


# ============================================================================
# 工具导出
# ============================================================================

__all__ = [
    "fetch_materials_for_writing",
    "save_creative_content",
    "upload_document",
    "list_books",
    "get_stats",
    "ask_knowledge_graph",
]

GRAPH_TOOLS = [ask_knowledge_graph]
