"""知识图谱存储层。

提供两种存储：
- Neo4j：图数据库，存储实体和关系
- SQLite FTS5：实体索引，快速检索
"""

from src.tools.kg_storage.entity_index import EntityIndex
from src.tools.kg_storage.graph_service import LocalKGService
from src.tools.kg_storage.neo4j_client import Neo4jClient

__all__ = [
    "Neo4jClient",
    "EntityIndex",
    "LocalKGService",
]
