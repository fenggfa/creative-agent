"""知识图谱数据模型。

设计原则：
===========================================
1. 统一图谱：所有数据存放在一个图谱，通过 book/source 区分
2. 实体唯一键：(name, book) 联合唯一
3. 类型自由：entity_type 为字符串，支持任意类型扩展
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class RelationType(str, Enum):
    """关系类型枚举（保持枚举，关系类型相对固定）。"""

    LOCATED_AT = "located_at"
    KNOWS = "knows"
    OWNS = "owns"
    PARTICIPATES_IN = "participates_in"
    RELATED_TO = "related_to"
    PARENT_OF = "parent_of"
    FRIEND_OF = "friend_of"
    ENEMY_OF = "enemy_of"
    MEMBER_OF = "member_of"
    LEADER_OF = "leader_of"
    CREATOR_OF = "creator_of"
    USES = "uses"
    MENTIONED_IN = "mentioned_in"


class SourceType(str, Enum):
    """数据来源类型。"""

    MATERIAL = "material"   # 素材（原作设定）
    CREATIVE = "creative"   # 创作（二创内容）


# 推荐的实体类型（提示 LLM 优先使用，但不限制）
RECOMMENDED_ENTITY_TYPES = [
    "character",      # 人物
    "location",       # 地点
    "item",           # 物品/法宝
    "event",          # 事件
    "concept",        # 概念
    "creature",       # 生物/妖怪
    "ability",        # 能力/神通
    "organization",   # 组织/门派
]


@dataclass
class Entity:
    """实体数据结构。

    唯一键：(name, book) 联合唯一
    """

    # 核心字段
    name: str                    # 实体名称
    book: str                    # 所属书籍（如：西游记）
    entity_type: str             # 类型（自由字符串，如：character, 法宝, 境界...）
    source: str = "material"     # 来源：material/creative

    # 描述字段
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)  # 扩展属性

    # 元数据
    entity_id: str = field(default_factory=lambda: str(uuid4()))
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_neo4j_dict(self) -> dict[str, Any]:
        """转换为 Neo4j 存储格式。"""
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "book": self.book,
            "entity_type": self.entity_type,
            "source": self.source,
            "description": self.description,
            "properties": self.properties,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, data: dict[str, Any]) -> "Entity":
        """从 Neo4j 数据创建实体。"""
        return cls(
            entity_id=data.get("entity_id", str(uuid4())),
            name=data.get("name", ""),
            book=data.get("book", ""),
            entity_type=data.get("entity_type", "concept"),
            source=data.get("source", "material"),
            description=data.get("description", ""),
            properties=data.get("properties", {}),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )


@dataclass
class Relation:
    """关系数据结构。

    唯一键：(source_entity_name, target_entity_name, relation_type, book)
    """

    source_entity_name: str      # 源实体名称
    target_entity_name: str      # 目标实体名称
    relation_type: str           # 关系类型
    book: str                    # 所属书籍
    source: str = "material"     # 来源

    # 描述字段
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    # 元数据
    relation_id: str = field(default_factory=lambda: str(uuid4()))
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_neo4j_dict(self) -> dict[str, Any]:
        """转换为 Neo4j 存储格式。"""
        return {
            "relation_id": self.relation_id,
            "source_entity_name": self.source_entity_name,
            "target_entity_name": self.target_entity_name,
            "relation_type": self.relation_type,
            "book": self.book,
            "source": self.source,
            "description": self.description,
            "properties": self.properties,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_neo4j(cls, data: dict[str, Any]) -> "Relation":
        """从 Neo4j 数据创建关系。"""
        return cls(
            relation_id=data.get("relation_id", str(uuid4())),
            source_entity_name=data.get("source_entity_name", ""),
            target_entity_name=data.get("target_entity_name", ""),
            relation_type=data.get("relation_type", "related_to"),
            book=data.get("book", ""),
            source=data.get("source", "material"),
            description=data.get("description", ""),
            properties=data.get("properties", {}),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
        )


@dataclass
class DocumentChunk:
    """文档分块。"""

    chunk_id: str
    content: str
    doc_id: str
    book: str              # 所属书籍
    chunk_index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphBuildResult:
    """图谱构建结果。"""

    doc_id: str
    book: str              # 所属书籍
    source: str            # material/creative
    entities: list[Entity]
    relations: list[Relation]
    chunks_processed: int
    success: bool = True
    error_message: str = ""
    build_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return {
            "doc_id": self.doc_id,
            "book": self.book,
            "source": self.source,
            "entities_count": len(self.entities),
            "relations_count": len(self.relations),
            "chunks_processed": self.chunks_processed,
            "success": self.success,
            "error_message": self.error_message,
            "build_time_seconds": self.build_time_seconds,
        }
