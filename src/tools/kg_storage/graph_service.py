"""统一知识图谱服务。

设计原则：
===========================================
1. 统一图谱：所有数据在一个图谱，通过 book/source 区分
2. 跨书搜索：默认搜索所有书籍的素材
3. 按书过滤：支持指定 book 参数
"""

from __future__ import annotations

import logging
from typing import Any

from src.tools.kg_storage.entity_index import EntityIndex, get_entity_index
from src.tools.kg_storage.models import Entity, GraphBuildResult, Relation
from src.tools.kg_storage.neo4j_client import Neo4jClient, get_neo4j_client

logger = logging.getLogger(__name__)


class LocalKGService:
    """统一知识图谱服务。

    整合 Neo4j + SQLite FTS5，提供：
    - 实体存储与检索
    - 关系存储与查询
    - 跨书搜索
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient | None = None,
        entity_index: EntityIndex | None = None,
    ) -> None:
        """初始化本地图谱服务。

        Args:
            neo4j_client: Neo4j 客户端
            entity_index: 实体索引
        """
        self._neo4j = neo4j_client
        self._index = entity_index
        self._connected = False

    async def connect(self) -> None:
        """连接所有存储后端。"""
        if self._connected:
            return

        if self._neo4j is None:
            self._neo4j = get_neo4j_client()
        if self._index is None:
            self._index = get_entity_index()

        await self._neo4j.connect()
        await self._index.connect()
        self._connected = True
        logger.info("统一知识图谱服务已连接")

    async def close(self) -> None:
        """关闭所有连接。"""
        if self._neo4j:
            await self._neo4j.close()
        if self._index:
            await self._index.close()
        self._connected = False
        logger.info("统一知识图谱服务已关闭")

    @property
    def neo4j(self) -> Neo4jClient:
        """获取 Neo4j 客户端。"""
        if self._neo4j is None:
            raise RuntimeError("服务未初始化，请先调用 connect()")
        return self._neo4j

    @property
    def index(self) -> EntityIndex:
        """获取实体索引。"""
        if self._index is None:
            raise RuntimeError("服务未初始化，请先调用 connect()")
        return self._index

    # ==================== 知识入库 ====================

    async def ingest_entities(self, entities: list[Entity]) -> dict[str, Any]:
        """入库实体到图谱。

        Args:
            entities: 实体列表

        Returns:
            入库结果
        """
        entity_ids = await self.neo4j.create_entities_batch(entities)
        indexed_count = await self.index.index_entities_batch(entities)

        return {
            "total": len(entities),
            "stored_in_neo4j": len(entity_ids),
            "indexed_count": indexed_count,
            "success": len(entity_ids) == len(entities),
        }

    async def ingest_relations(self, relations: list[Relation]) -> dict[str, Any]:
        """入库关系到图谱。

        Args:
            relations: 关系列表

        Returns:
            入库结果
        """
        relation_ids = await self.neo4j.create_relations_batch(relations)

        return {
            "total": len(relations),
            "stored_count": len(relation_ids),
            "success": len(relation_ids) == len(relations),
        }

    async def ingest_graph_result(self, result: GraphBuildResult) -> dict[str, Any]:
        """入库图谱构建结果。

        Args:
            result: 图谱构建结果

        Returns:
            入库结果汇总
        """
        entity_result = await self.ingest_entities(result.entities)
        relation_result = await self.ingest_relations(result.relations)

        return {
            "doc_id": result.doc_id,
            "book": result.book,
            "entities": entity_result,
            "relations": relation_result,
            "success": entity_result["success"] and relation_result["success"],
        }

    # ==================== 知识检索 ====================

    async def search_entities(
        self,
        query: str,
        book: str | None = None,
        source: str | None = None,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[Entity]:
        """搜索实体（使用 BM25 排序）。

        Args:
            query: 搜索关键词
            book: 书名过滤（可选）
            source: 来源过滤 (material/creative)
            entity_type: 实体类型过滤
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        results = await self.index.search(query, book, source, entity_type, limit)
        return [entity for entity, _ in results]

    async def get_entity(self, name: str, book: str) -> Entity | None:
        """按名称和书名获取实体。

        Args:
            name: 实体名称
            book: 书名

        Returns:
            实体对象或 None
        """
        return await self.neo4j.get_entity(name, book)

    async def get_entity_relations(
        self,
        name: str,
        book: str,
    ) -> list[dict[str, Any]]:
        """获取实体的所有关系。

        Args:
            name: 实体名称
            book: 书名

        Returns:
            关系列表
        """
        return await self.neo4j.get_entity_relations(name, book)

    async def query_subgraph(
        self,
        entity_name: str,
        book: str,
        max_depth: int = 2,
        limit: int = 100,
    ) -> dict[str, Any]:
        """查询以实体为中心的子图。

        Args:
            entity_name: 中心实体名称
            book: 书名
            max_depth: 最大遍历深度
            limit: 返回节点数量限制

        Returns:
            子图数据
        """
        return await self.neo4j.query_subgraph(entity_name, book, max_depth, limit)

    async def find_path(
        self,
        source_name: str,
        target_name: str,
        book: str,
        max_depth: int = 4,
    ) -> list[dict[str, Any]]:
        """查找两个实体间的路径。

        Args:
            source_name: 起始实体名称
            target_name: 目标实体名称
            book: 书名
            max_depth: 最大路径长度

        Returns:
            路径列表
        """
        return await self.neo4j.find_path(source_name, target_name, book, max_depth)

    # ==================== 知识问答 ====================

    async def query(
        self,
        question: str,
        book: str | None = None,
        source: str | None = "material",
    ) -> str:
        """查询知识图谱。

        Args:
            question: 问题
            book: 书名过滤（可选，不指定则搜索所有书）
            source: 来源过滤 (默认 material)

        Returns:
            回答文本
        """
        # 1. 搜索相关实体
        entities = await self.search_entities(
            question,
            book=book,
            source=source,
            limit=5,
        )

        if not entities:
            return f"未找到「{question}」相关信息。"

        # 2. 收集相关子图
        all_info: list[str] = []
        seen_entities: set[str] = set()

        for entity in entities[:3]:
            key = f"{entity.name}@{entity.book}"
            if key in seen_entities:
                continue
            seen_entities.add(key)

            # 获取实体信息
            entity_info = f"【{entity.name}】({entity.entity_type})"
            if entity.book:
                entity_info += f" - {entity.book}"
            if entity.description:
                entity_info += f"\n{entity.description}"

            # 获取关系（只在指定书名时查询关系）
            if entity.book:
                relations = await self.get_entity_relations(entity.name, entity.book)
                if relations:
                    rel_info = []
                    for rel in relations[:5]:
                        direction = "→" if rel["direction"] == "outgoing" else "←"
                        rel_info.append(
                            f"  {direction} {rel['relation_type']}: {rel['related_entity']}"
                        )
                    entity_info += "\n关系:\n" + "\n".join(rel_info)

            all_info.append(entity_info)

        return "\n\n".join(all_info)

    # ==================== 书籍管理 ====================

    async def list_books(self) -> list[str]:
        """列出所有书籍。"""
        return await self.neo4j.list_books()

    async def delete_book(self, book: str) -> dict[str, Any]:
        """删除指定书籍的所有数据。

        Args:
            book: 书名

        Returns:
            删除结果
        """
        neo4j_result = await self.neo4j.clear_book(book)
        index_count = await self.index.delete_book(book)

        return {
            "book": book,
            "neo4j_deleted": neo4j_result.get("deleted", 0),
            "index_deleted": index_count,
        }

    # ==================== 统计与维护 ====================

    async def get_stats(self, book: str | None = None) -> dict[str, Any]:
        """获取图谱统计信息。"""
        neo4j_stats = await self.neo4j.get_stats(book)
        index_stats = await self.index.get_stats()

        return {
            "neo4j": neo4j_stats,
            "index": index_stats,
            "connected": self._connected,
        }

    async def health_check(self) -> dict[str, bool]:
        """健康检查。"""
        return {
            "neo4j": await self.neo4j.health_check(),
            "index": self._index is not None,
        }

    async def clear_all(self) -> dict[str, Any]:
        """清空所有数据（慎用）。"""
        neo4j_result = await self.neo4j.clear_all()
        await self.index.clear_all()

        return {
            "neo4j_deleted": neo4j_result.get("deleted", 0),
            "index_cleared": True,
        }


# 全局服务实例
_local_kg_service: LocalKGService | None = None


def get_local_kg_service() -> LocalKGService:
    """获取全局本地图谱服务实例。"""
    global _local_kg_service
    if _local_kg_service is None:
        _local_kg_service = LocalKGService()
    return _local_kg_service
