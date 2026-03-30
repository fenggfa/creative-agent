"""Neo4j 图数据库客户端。

设计原则：
===========================================
1. 统一图谱：所有数据在一个图谱，通过 book/source 区分
2. 实体唯一键：(name, book) 联合唯一
3. MERGE 语义：重复上传时合并描述
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.config import settings
from src.tools.kg_storage.models import Entity, Relation

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j 图数据库客户端。"""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        """初始化 Neo4j 客户端。

        Args:
            uri: Neo4j 连接 URI (如 bolt://localhost:7687)
            user: 用户名
            password: 密码
        """
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD.get_secret_value()
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """建立数据库连接。"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            logger.info(f"Neo4j 连接成功: {self.uri}")

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j 连接已关闭")

    @property
    def driver(self) -> AsyncDriver:
        """获取数据库驱动。"""
        if self._driver is None:
            raise RuntimeError("Neo4j 未连接，请先调用 connect()")
        return self._driver

    # ==================== 实体操作 ====================

    async def create_entity(self, entity: Entity) -> str:
        """创建或更新实体（MERGE 语义）。

        唯一键：(name, book)
        重复时合并描述。

        Args:
            entity: 实体对象

        Returns:
            实体 ID
        """
        query = """
        MERGE (e:Entity {name: $name, book: $book})
        ON CREATE SET
            e.entity_id = $entity_id,
            e.entity_type = $entity_type,
            e.source = $source,
            e.description = $description,
            e.properties = $properties,
            e.confidence = $confidence,
            e.created_at = $created_at
        ON MATCH SET
            e.description = CASE
                WHEN $description <> '' AND NOT $description IN e.description
                THEN e.description + '\n' + $description
                ELSE e.description
            END,
            e.confidence = CASE
                WHEN $confidence > e.confidence THEN $confidence
                ELSE e.confidence
            END
        RETURN e.entity_id as id
        """

        async with self.driver.session() as session:
            result = await session.run(query, **entity.to_neo4j_dict())
            record = await result.single()
            return record["id"] if record else entity.entity_id

    async def create_entities_batch(self, entities: list[Entity]) -> list[str]:
        """批量创建实体。

        Args:
            entities: 实体列表

        Returns:
            实体 ID 列表
        """
        if not entities:
            return []

        query = """
        UNWIND $entities as entity_data
        MERGE (e:Entity {name: entity_data.name, book: entity_data.book})
        ON CREATE SET
            e.entity_id = entity_data.entity_id,
            e.entity_type = entity_data.entity_type,
            e.source = entity_data.source,
            e.description = entity_data.description,
            e.properties = entity_data.properties,
            e.confidence = entity_data.confidence,
            e.created_at = entity_data.created_at
        ON MATCH SET
            e.description = CASE
                WHEN entity_data.description <> ''
                     AND NOT entity_data.description IN e.description
                THEN e.description + '\n' + entity_data.description
                ELSE e.description
            END,
            e.confidence = CASE
                WHEN entity_data.confidence > e.confidence
                THEN entity_data.confidence
                ELSE e.confidence
            END
        RETURN e.entity_id as id
        """

        entities_data = [e.to_neo4j_dict() for e in entities]

        async with self.driver.session() as session:
            result = await session.run(query, entities=entities_data)
            records = await result.data()
            return [r["id"] for r in records]

    async def get_entity(self, name: str, book: str) -> Entity | None:
        """获取实体。

        Args:
            name: 实体名称
            book: 书名

        Returns:
            实体对象或 None
        """
        query = """
        MATCH (e:Entity {name: $name, book: $book})
        RETURN e.entity_id, e.name, e.book, e.entity_type, e.source,
               e.description, e.properties, e.confidence, e.created_at
        """

        async with self.driver.session() as session:
            result = await session.run(query, name=name, book=book)
            record = await result.single()
            if record:
                return Entity.from_neo4j(dict(record))
            return None

    async def search_entities(
        self,
        query: str,
        book: str | None = None,
        source: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> list[Entity]:
        """搜索实体。

        Args:
            query: 搜索关键词
            book: 书名过滤
            source: 来源过滤 (material/creative)
            entity_type: 实体类型过滤
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        cypher = """
        MATCH (e:Entity)
        WHERE e.name CONTAINS $query
        """
        params: dict[str, Any] = {"query": query}

        if book:
            cypher += " AND e.book = $book"
            params["book"] = book
        if source:
            cypher += " AND e.source = $source"
            params["source"] = source
        if entity_type:
            cypher += " AND e.entity_type = $entity_type"
            params["entity_type"] = entity_type

        cypher += """
        RETURN e.entity_id, e.name, e.book, e.entity_type, e.source,
               e.description, e.properties, e.confidence, e.created_at
        LIMIT $limit
        """
        params["limit"] = limit

        async with self.driver.session() as session:
            result = await session.run(cypher, **params)
            records = await result.data()
            return [Entity.from_neo4j(dict(r)) for r in records]

    async def list_books(self) -> list[str]:
        """列出所有书籍。"""
        query = """
        MATCH (e:Entity)
        RETURN DISTINCT e.book as book
        ORDER BY book
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            records = await result.data()
            return [r["book"] for r in records if r.get("book")]

    async def delete_entity(self, name: str, book: str) -> bool:
        """删除实体及其关系。

        Args:
            name: 实体名称
            book: 书名

        Returns:
            是否成功
        """
        query = """
        MATCH (e:Entity {name: $name, book: $book})
        DETACH DELETE e
        RETURN count(e) as deleted
        """

        async with self.driver.session() as session:
            result = await session.run(query, name=name, book=book)
            record = await result.single()
            return record is not None and record["deleted"] > 0

    # ==================== 关系操作 ====================

    async def create_relation(self, relation: Relation) -> str:
        """创建或更新关系（MERGE 语义）。

        唯一键：(source_entity_name, target_entity_name, relation_type, book)

        Args:
            relation: 关系对象

        Returns:
            关系 ID
        """
        query = """
        MATCH (source:Entity {name: $source_entity_name, book: $book})
        MATCH (target:Entity {name: $target_entity_name, book: $book})
        MERGE (source)-[r:RELATES_TO {
            source_name: $source_entity_name,
            target_name: $target_entity_name,
            relation_type: $relation_type,
            book: $book
        }]->(target)
        ON CREATE SET
            r.relation_id = $relation_id,
            r.source = $source,
            r.description = $description,
            r.properties = $properties,
            r.confidence = $confidence,
            r.created_at = $created_at
        ON MATCH SET
            r.description = $description,
            r.confidence = CASE
                WHEN $confidence > r.confidence THEN $confidence
                ELSE r.confidence
            END
        RETURN r.relation_id as id
        """

        async with self.driver.session() as session:
            result = await session.run(query, **relation.to_neo4j_dict())
            record = await result.single()
            return record["id"] if record else relation.relation_id

    async def create_relations_batch(self, relations: list[Relation]) -> list[str]:
        """批量创建关系。

        Args:
            relations: 关系列表

        Returns:
            关系 ID 列表
        """
        if not relations:
            return []

        query = """
        UNWIND $relations as rel_data
        MATCH (source:Entity {name: rel_data.source_entity_name, book: rel_data.book})
        MATCH (target:Entity {name: rel_data.target_entity_name, book: rel_data.book})
        MERGE (source)-[r:RELATES_TO {
            source_name: rel_data.source_entity_name,
            target_name: rel_data.target_entity_name,
            relation_type: rel_data.relation_type,
            book: rel_data.book
        }]->(target)
        ON CREATE SET
            r.relation_id = rel_data.relation_id,
            r.source = rel_data.source,
            r.description = rel_data.description,
            r.properties = rel_data.properties,
            r.confidence = rel_data.confidence,
            r.created_at = rel_data.created_at
        ON MATCH SET
            r.description = rel_data.description,
            r.confidence = CASE
                WHEN rel_data.confidence > r.confidence
                THEN rel_data.confidence
                ELSE r.confidence
            END
        RETURN r.relation_id as id
        """

        relations_data = [r.to_neo4j_dict() for r in relations]

        async with self.driver.session() as session:
            result = await session.run(query, relations=relations_data)
            records = await result.data()
            return [r["id"] for r in records]

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
        query = """
        MATCH (e:Entity {name: $name, book: $book})-[r:RELATES_TO]-(related:Entity)
        RETURN
            r.relation_id as relation_id,
            r.relation_type as relation_type,
            r.description as description,
            r.confidence as confidence,
            CASE WHEN startNode(r) = e THEN 'outgoing' ELSE 'incoming' END as direction,
            related.name as related_entity,
            related.entity_type as related_type
        """

        async with self.driver.session() as session:
            result = await session.run(query, name=name, book=book)
            records = await result.data()
            return records

    # ==================== 图谱查询 ====================

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
            子图数据（nodes, edges）
        """
        query = f"""
        MATCH path = (center:Entity {{name: $name, book: $book}})
                     -[:RELATES_TO*1..{max_depth}]-(related:Entity)
        WITH center, related, relationships(path) as rels
        LIMIT $limit
        WITH collect(DISTINCT center) + collect(DISTINCT related) as nodes,
             collect(DISTINCT rels[0]) as edges
        RETURN
            [n IN nodes | {{
                id: n.entity_id,
                name: n.name,
                type: n.entity_type,
                description: n.description,
                book: n.book
            }}] as nodes,
            [e IN edges | {{
                id: e.relation_id,
                source: e.source_name,
                target: e.target_name,
                type: e.relation_type,
                description: e.description
            }}] as edges
        """

        async with self.driver.session() as session:
            result = await session.run(query, name=entity_name, book=book, limit=limit)
            record = await result.single()
            if record:
                return {
                    "nodes": record.get("nodes", []),
                    "edges": record.get("edges", []),
                }
            return {"nodes": [], "edges": []}

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
            路径列表（每条路径包含节点和边）
        """
        query = f"""
        MATCH path = (source:Entity {{name: $source_name, book: $book}})
                     -[:RELATES_TO*1..{max_depth}]-
                     (target:Entity {{name: $target_name, book: $book}})
        RETURN [n IN nodes(path) | {{name: n.name, type: n.entity_type}}] as nodes,
               [r IN relationships(path) |
                {{type: r.relation_type, description: r.description}}] as edges
        ORDER BY length(path)
        LIMIT 5
        """

        async with self.driver.session() as session:
            result = await session.run(
                query,
                source_name=source_name,
                target_name=target_name,
                book=book,
            )
            records = await result.data()
            return [
                {
                    "nodes": r["nodes"],
                    "edges": r["edges"],
                }
                for r in records
            ]

    # ==================== 统计与健康检查 ====================

    async def get_stats(self, book: str | None = None) -> dict[str, Any]:
        """获取图谱统计信息。

        Args:
            book: 按书名过滤（可选）
        """
        if book:
            query = """
            MATCH (e:Entity {book: $book})
            WITH count(e) as entity_count
            MATCH ()-[r:RELATES_TO {book: $book}]->()
            RETURN entity_count, count(r) as relation_count
            """
            params = {"book": book}
        else:
            query = """
            MATCH (e:Entity)
            WITH count(e) as entity_count
            MATCH ()-[r:RELATES_TO]->()
            RETURN entity_count, count(r) as relation_count
            """
            params = {}

        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            if record:
                return {
                    "entity_count": record["entity_count"],
                    "relation_count": record["relation_count"],
                }
            return {"entity_count": 0, "relation_count": 0}

    async def health_check(self) -> bool:
        """检查数据库连接是否正常。"""
        try:
            async with self.driver.session() as session:
                await session.run("RETURN 1")
                return True
        except Exception as e:
            logger.error(f"Neo4j 健康检查失败: {e}")
            return False

    async def clear_book(self, book: str) -> dict[str, int]:
        """清空指定书籍的数据。

        Args:
            book: 书名

        Returns:
            删除统计
        """
        query = """
        MATCH (n:Entity {book: $book})
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        async with self.driver.session() as session:
            result = await session.run(query, book=book)
            record = await result.single()
            return {"deleted": record["deleted"] if record else 0}

    async def clear_all(self) -> dict[str, int]:
        """清空所有数据（慎用）。"""
        query = """
        MATCH (n)
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            return {"deleted": record["deleted"] if record else 0}


# 全局客户端实例
_neo4j_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """获取全局 Neo4j 客户端实例。"""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client
