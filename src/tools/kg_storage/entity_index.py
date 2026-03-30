"""SQLite FTS5 + BM25 实体索引。

设计原则：
===========================================
1. 统一索引：所有实体在一个索引，通过 book/source 区分
2. BM25 排序：全文检索按相关性排序
3. 支持过滤：按书名、来源、类型过滤
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiosqlite

from src.config import settings
from src.tools.kg_storage.models import Entity

logger = logging.getLogger(__name__)


class EntityIndex:
    """SQLite FTS5 + BM25 实体索引。"""

    def __init__(self, db_path: str | None = None) -> None:
        """初始化实体索引。

        Args:
            db_path: SQLite 数据库路径
        """
        self.db_path = db_path or settings.ENTITY_INDEX_PATH
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """建立数据库连接并创建表。"""
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row

        # 创建 FTS5 虚拟表（添加 book, source 字段）
        await self._db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities USING fts5(
                entity_id,
                name,
                book,
                source,
                entity_type,
                description,
                content,
                tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS entity_metadata (
                entity_id TEXT PRIMARY KEY,
                properties TEXT,
                confidence REAL,
                created_at TEXT
            );

            -- 创建索引加速按书名过滤
            CREATE INDEX IF NOT EXISTS idx_entity_book ON entity_metadata(entity_id);
        """)
        await self._db.commit()
        logger.info(f"实体索引连接成功: {self.db_path}")

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("实体索引连接已关闭")

    @property
    def db(self) -> aiosqlite.Connection:
        """获取数据库连接。"""
        if self._db is None:
            raise RuntimeError("实体索引未连接，请先调用 connect()")
        return self._db

    async def index_entity(self, entity: Entity) -> bool:
        """索引单个实体。

        Args:
            entity: 实体对象

        Returns:
            是否成功
        """
        try:
            # 构建全文检索内容
            content = f"{entity.name} {entity.book} {entity.entity_type} {entity.description}"

            # 插入 FTS5 表
            await self.db.execute(
                """
                INSERT OR REPLACE INTO entities
                (entity_id, name, book, source, entity_type, description, content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.entity_id,
                    entity.name,
                    entity.book,
                    entity.source,
                    entity.entity_type,
                    entity.description,
                    content,
                ),
            )

            # 插入元数据表
            await self.db.execute(
                """
                INSERT OR REPLACE INTO entity_metadata
                (entity_id, properties, confidence, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    entity.entity_id,
                    json.dumps(entity.properties, ensure_ascii=False),
                    entity.confidence,
                    entity.created_at.isoformat(),
                ),
            )

            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"索引实体失败 {entity.name}: {e}")
            return False

    async def index_entities_batch(self, entities: list[Entity]) -> int:
        """批量索引实体。

        Args:
            entities: 实体列表

        Returns:
            成功索引的数量
        """
        if not entities:
            return 0

        success_count = 0

        for entity in entities:
            try:
                content = f"{entity.name} {entity.book} {entity.entity_type} {entity.description}"

                await self.db.execute(
                    """
                    INSERT OR REPLACE INTO entities
                    (entity_id, name, book, source, entity_type, description, content)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity.entity_id,
                        entity.name,
                        entity.book,
                        entity.source,
                        entity.entity_type,
                        entity.description,
                        content,
                    ),
                )

                await self.db.execute(
                    """
                    INSERT OR REPLACE INTO entity_metadata
                    (entity_id, properties, confidence, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        entity.entity_id,
                        json.dumps(entity.properties, ensure_ascii=False),
                        entity.confidence,
                        entity.created_at.isoformat(),
                    ),
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"批量索引实体失败 {entity.name}: {e}")

        await self.db.commit()
        return success_count

    async def search(
        self,
        query: str,
        book: str | None = None,
        source: str | None = None,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[tuple[Entity, float]]:
        """搜索实体，使用 BM25 排序。

        Args:
            query: 搜索关键词
            book: 书名过滤
            source: 来源过滤 (material/creative)
            entity_type: 实体类型过滤
            limit: 返回数量限制

        Returns:
            元组列表 (实体, BM25 分数)
        """
        # 构建 FTS5 查询
        fts_query = query.replace("'", "''")

        # 基础查询
        sql = """
            SELECT
                e.entity_id,
                e.name,
                e.book,
                e.source,
                e.entity_type,
                e.description,
                m.properties,
                m.confidence,
                m.created_at,
                bm25(entities) as score
            FROM entities e
            LEFT JOIN entity_metadata m ON e.entity_id = m.entity_id
            WHERE entities MATCH ?
        """
        params: list[Any] = [fts_query]

        # 添加过滤条件（FTS5 不支持 WHERE 子句过滤，需要在应用层过滤）
        # 这里我们使用子查询方式

        sql = """
            SELECT
                e.entity_id,
                e.name,
                e.book,
                e.source,
                e.entity_type,
                e.description,
                m.properties,
                m.confidence,
                m.created_at,
                bm25(entities) as score
            FROM entities e
            LEFT JOIN entity_metadata m ON e.entity_id = m.entity_id
            WHERE e.rowid IN (
                SELECT rowid FROM entities WHERE entities MATCH ?
            )
        """
        params = [fts_query]

        # 添加过滤条件
        conditions = []
        if book:
            conditions.append("e.book = ?")
            params.append(book)
        if source:
            conditions.append("e.source = ?")
            params.append(source)
        if entity_type:
            conditions.append("e.entity_type = ?")
            params.append(entity_type)

        if conditions:
            sql += " AND " + " AND ".join(conditions)

        sql += " ORDER BY bm25(entities) ASC LIMIT ?"
        params.append(limit)

        results: list[tuple[Entity, float]] = []

        async with self.db.execute(sql, params) as cursor:
            async for row in cursor:
                try:
                    entity = Entity(
                        entity_id=row["entity_id"],
                        name=row["name"],
                        book=row["book"],
                        source=row["source"],
                        entity_type=row["entity_type"],
                        description=row["description"] or "",
                        properties=json.loads(row["properties"] or "{}"),
                        confidence=row["confidence"] or 1.0,
                        created_at=row["created_at"],
                    )
                    score = abs(float(row["score"]))
                    results.append((entity, score))
                except Exception as e:
                    logger.warning(f"解析搜索结果失败: {e}")

        return results

    async def search_by_name(
        self,
        name_prefix: str,
        book: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """按名称前缀搜索（自动补全）。

        Args:
            name_prefix: 名称前缀
            book: 书名过滤
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        sql = """
            SELECT
                e.entity_id,
                e.name,
                e.book,
                e.source,
                e.entity_type,
                e.description,
                m.properties,
                m.confidence,
                m.created_at
            FROM entities e
            LEFT JOIN entity_metadata m ON e.entity_id = m.entity_id
            WHERE e.name LIKE ? || '%'
        """
        params: list[Any] = [name_prefix]

        if book:
            sql += " AND e.book = ?"
            params.append(book)

        sql += " ORDER BY m.confidence DESC LIMIT ?"
        params.append(limit)

        results: list[Entity] = []

        async with self.db.execute(sql, params) as cursor:
            async for row in cursor:
                try:
                    entity = Entity(
                        entity_id=row["entity_id"],
                        name=row["name"],
                        book=row["book"],
                        source=row["source"],
                        entity_type=row["entity_type"],
                        description=row["description"] or "",
                        properties=json.loads(row["properties"] or "{}"),
                        confidence=row["confidence"] or 1.0,
                        created_at=row["created_at"],
                    )
                    results.append(entity)
                except Exception as e:
                    logger.warning(f"解析名称搜索结果失败: {e}")

        return results

    async def get_entity(self, entity_id: str) -> Entity | None:
        """获取指定实体。

        Args:
            entity_id: 实体 ID

        Returns:
            实体对象或 None
        """
        sql = """
            SELECT
                e.entity_id,
                e.name,
                e.book,
                e.source,
                e.entity_type,
                e.description,
                m.properties,
                m.confidence,
                m.created_at
            FROM entities e
            LEFT JOIN entity_metadata m ON e.entity_id = m.entity_id
            WHERE e.entity_id = ?
        """

        async with self.db.execute(sql, [entity_id]) as cursor:
            row = await cursor.fetchone()
            if row:
                return Entity(
                    entity_id=row["entity_id"],
                    name=row["name"],
                    book=row["book"],
                    source=row["source"],
                    entity_type=row["entity_type"],
                    description=row["description"] or "",
                    properties=json.loads(row["properties"] or "{}"),
                    confidence=row["confidence"] or 1.0,
                    created_at=row["created_at"],
                )
            return None

    async def delete_entity(self, entity_id: str) -> bool:
        """删除实体索引。

        Args:
            entity_id: 实体 ID

        Returns:
            是否成功
        """
        try:
            await self.db.execute(
                "DELETE FROM entities WHERE entity_id = ?",
                [entity_id],
            )
            await self.db.execute(
                "DELETE FROM entity_metadata WHERE entity_id = ?",
                [entity_id],
            )
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"删除实体索引失败 {entity_id}: {e}")
            return False

    async def delete_book(self, book: str) -> int:
        """删除指定书籍的所有实体索引。

        Args:
            book: 书名

        Returns:
            删除数量
        """
        try:
            # FTS5 不支持直接 DELETE，需要获取 ID 后逐个删除
            cursor = await self.db.execute(
                "SELECT entity_id FROM entities WHERE book = ?",
                [book],
            )
            rows = await cursor.fetchall()
            row_list = list(rows)

            for row in row_list:
                entity_id = row["entity_id"]
                await self.db.execute(
                    "DELETE FROM entities WHERE entity_id = ?",
                    [entity_id],
                )
                await self.db.execute(
                    "DELETE FROM entity_metadata WHERE entity_id = ?",
                    [entity_id],
                )

            await self.db.commit()
            return len(row_list)
        except Exception as e:
            logger.error(f"删除书籍索引失败 {book}: {e}")
            return 0

    async def get_stats(self) -> dict[str, Any]:
        """获取索引统计信息。"""
        async with self.db.execute("SELECT COUNT(*) as count FROM entities") as cursor:
            row = await cursor.fetchone()
            entity_count = row["count"] if row else 0

        async with self.db.execute(
            "SELECT book, COUNT(*) as count FROM entities GROUP BY book"
        ) as cursor:
            book_counts = {row["book"]: row["count"] async for row in cursor}

        async with self.db.execute(
            "SELECT source, COUNT(*) as count FROM entities GROUP BY source"
        ) as cursor:
            source_counts = {row["source"]: row["count"] async for row in cursor}

        async with self.db.execute(
            "SELECT entity_type, COUNT(*) as count FROM entities GROUP BY entity_type"
        ) as cursor:
            type_counts = {row["entity_type"]: row["count"] async for row in cursor}

        return {
            "total_entities": entity_count,
            "by_book": book_counts,
            "by_source": source_counts,
            "by_type": type_counts,
        }

    async def clear_all(self) -> int:
        """清空所有索引数据。"""
        await self.db.execute("DELETE FROM entities")
        await self.db.execute("DELETE FROM entity_metadata")
        await self.db.commit()

        result = await self.db.execute("SELECT COUNT(*) FROM entities")
        row = await result.fetchone()
        return row[0] if row else 0


# 全局索引实例
_entity_index: EntityIndex | None = None


def get_entity_index() -> EntityIndex:
    """获取全局实体索引实例。"""
    global _entity_index
    if _entity_index is None:
        _entity_index = EntityIndex()
    return _entity_index
