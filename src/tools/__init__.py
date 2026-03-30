"""知识图谱工具包。

存储架构：
- Neo4j：图数据库，存储实体和关系
- SQLite FTS5：实体索引，快速全文检索
"""

from src.tools.continuity import (
    ChapterSummarizer,
    CharacterStateTracker,
    ConflictDetector,
    ForeshadowingTracker,
    PlotThreadTracker,
)
from src.tools.graph_service import (
    ask_knowledge_graph,
    fetch_materials_for_writing,
    save_creative_content,
)
from src.tools.kg_extractor import (
    extract_entities,
    extract_relations,
    parse_document,
)
from src.tools.kg_storage import (
    EntityIndex,
    LocalKGService,
    Neo4jClient,
)

__all__ = [
    # Graph Service
    "ask_knowledge_graph",
    "fetch_materials_for_writing",
    "save_creative_content",
    # Continuity Tools
    "CharacterStateTracker",
    "ChapterSummarizer",
    "ConflictDetector",
    "ForeshadowingTracker",
    "PlotThreadTracker",
    # Knowledge Graph Storage
    "Neo4jClient",
    "EntityIndex",
    "LocalKGService",
    # Knowledge Graph Extraction
    "parse_document",
    "extract_entities",
    "extract_relations",
]
