"""知识提取层。

将文档转化为结构化知识：
- 文档解析：分块处理
- 实体提取：识别人物、地点、物品、事件、概念
- 关系抽取：发现实体间的语义关系
- Schema 管理：动态配置实体和关系类型
- 调试追踪：记录构建过程详情
"""

from src.tools.kg_extractor.document_parser import parse_document
from src.tools.kg_extractor.entity_extractor import extract_entities
from src.tools.kg_extractor.relation_extractor import extract_relations
from src.tools.kg_extractor.schema_manager import SchemaManager, get_schema_manager
from src.tools.kg_extractor.trace_logger import (
    KGTraceLogger,
    clear_trace_logger,
    get_trace_logger,
    init_trace_logger,
)

__all__ = [
    "parse_document",
    "extract_entities",
    "extract_relations",
    "SchemaManager",
    "get_schema_manager",
    "KGTraceLogger",
    "get_trace_logger",
    "init_trace_logger",
    "clear_trace_logger",
]
