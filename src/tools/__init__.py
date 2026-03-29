"""外部服务集成工具包。"""

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
from src.tools.lightrag import (
    GraphType,
    LightRAGClient,
    creative_lightrag_client,
    lightrag_client,
)

__all__ = [
    # Graph Service
    "ask_knowledge_graph",
    "fetch_materials_for_writing",
    "save_creative_content",
    # LightRAG Client
    "GraphType",
    "LightRAGClient",
    "creative_lightrag_client",
    "lightrag_client",
    # Continuity Tools
    "CharacterStateTracker",
    "ChapterSummarizer",
    "ConflictDetector",
    "ForeshadowingTracker",
    "PlotThreadTracker",
]
