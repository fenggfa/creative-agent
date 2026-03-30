"""知识图谱构建师智能体 - 将文档转化为结构化知识图谱。

设计原则：
===========================================
1. 统一图谱：所有数据在一个图谱，通过 book/source 区分
2. 支持多书：上传不同书构建不同知识库
3. Harness 集成：约束注入、重试机制、学习闭环
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from src.harness import OutcomeType, TaskCategory, get_agent_memory, learn_from_failure
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry
from src.tools.kg_extractor import extract_entities, extract_relations, parse_document
from src.tools.kg_storage import EntityIndex, Neo4jClient
from src.tools.kg_storage.models import GraphBuildResult

logger = logging.getLogger(__name__)

# 知识图谱构建师系统提示词
KG_BUILDER_SYSTEM_PROMPT = """你是知识图谱构建师，负责将文档转化为结构化知识图谱。

你的职责：
1. 从文档中识别实体（人物、地点、物品、事件、概念等）
2. 抽取实体间的语义关系
3. 构建结构化的知识图谱

提取原则：
- 避免过度提取：只提取明确提到的实体
- 名称一致性：使用文本中的原始名称，不做推断
- 关系有明确语义：关系必须在文本中有依据
- 置信度评估：根据文本明确程度评估置信度"""


def _build_system_prompt() -> str:
    """构建带有约束注入的系统提示词。"""
    provider = get_constraint_provider()
    constraint_injection = provider.get_system_prompt_injection("kg_builder")

    if constraint_injection:
        return f"{KG_BUILDER_SYSTEM_PROMPT}\n\n{constraint_injection}"
    return KG_BUILDER_SYSTEM_PROMPT


def _get_lessons_for_kg_builder() -> list[str]:
    """获取知识图谱构建师的历史教训。"""
    try:
        memory = get_agent_memory()
        return memory.get_lessons_learned("kg_builder", OutcomeType.FAILURE)
    except Exception:
        return []


async def _record_kg_builder_outcome(
    doc_id: str,
    book: str,
    result: GraphBuildResult,
    success: bool,
) -> None:
    """记录图谱构建结果，用于学习闭环。"""
    try:
        memory = get_agent_memory()
        if success:
            memory.record_experience(
                agent_type="kg_builder",
                task_category=TaskCategory.ANALYSIS,
                task_description=f"构建知识图谱: {book}/{doc_id}",
                outcome=OutcomeType.SUCCESS,
                result_summary=f"提取 {len(result.entities)} 实体, {len(result.relations)} 关系",
                score=1.0 if result.entities else 0.5,
                reusable_patterns=[f"成功构建图谱: {book}"],
            )
        else:
            await learn_from_failure(
                [{"rule_name": "kg_build_failure", "message": result.error_message}],
                "kg_builder",
                {"doc_id": doc_id, "book": book, "entities": len(result.entities)},
            )
    except Exception as e:
        logging.debug(f"记录图谱构建结果失败: {e}")


@retry(config=LLM_RETRY)
async def build_knowledge_graph(
    document: str,
    book: str,
    source: str = "material",
    doc_id: str | None = None,
    neo4j_client: Neo4jClient | None = None,
    entity_index: EntityIndex | None = None,
) -> GraphBuildResult:
    """构建知识图谱。

    完整流程：
    1. 文档解析 → 分块
    2. 实体提取 → 识别实体
    3. 关系抽取 → 发现关系
    4. 存储入库 → Neo4j + SQLite

    Args:
        document: 文档内容
        book: 所属书籍
        source: 来源 (material/creative)
        doc_id: 文档 ID（可选）
        neo4j_client: Neo4j 客户端（可选）
        entity_index: 实体索引（可选）

    Returns:
        图谱构建结果
    """
    start_time = time.time()
    doc_id = doc_id or str(uuid4())[:8]

    try:
        # 1. 文档解析
        logger.info(f"开始解析文档: {book}/{doc_id}")
        chunks = await parse_document(document, doc_id, book)

        if not chunks:
            return GraphBuildResult(
                doc_id=doc_id,
                book=book,
                source=source,
                entities=[],
                relations=[],
                chunks_processed=0,
                success=False,
                error_message="文档解析失败，未产生任何分块",
            )

        # 2. 实体提取
        logger.info(f"开始提取实体: {book}/{doc_id}")
        entities = await extract_entities(chunks, book, source)

        if not entities:
            logger.warning(f"文档 {book}/{doc_id} 未提取到任何实体")

        # 3. 关系抽取
        logger.info(f"开始抽取关系: {book}/{doc_id}")
        relations = await extract_relations(chunks, entities, book, source)

        # 4. 存储入库
        if neo4j_client and entities:
            logger.info(f"存储实体到 Neo4j: {book}/{doc_id}")
            await neo4j_client.create_entities_batch(entities)

            if relations:
                logger.info(f"存储关系到 Neo4j: {book}/{doc_id}")
                await neo4j_client.create_relations_batch(relations)

        if entity_index and entities:
            logger.info(f"索引实体: {book}/{doc_id}")
            await entity_index.index_entities_batch(entities)

        build_time = time.time() - start_time

        result = GraphBuildResult(
            doc_id=doc_id,
            book=book,
            source=source,
            entities=entities,
            relations=relations,
            chunks_processed=len(chunks),
            success=True,
            build_time_seconds=build_time,
        )

        logger.info(
            f"知识图谱构建完成: {book}/{doc_id} - "
            f"{len(entities)} 实体, {len(relations)} 关系, "
            f"耗时 {build_time:.2f}s"
        )

        return result

    except Exception as e:
        logger.error(f"知识图谱构建失败: {book}/{doc_id} - {e}")
        return GraphBuildResult(
            doc_id=doc_id,
            book=book,
            source=source,
            entities=[],
            relations=[],
            chunks_processed=0,
            success=False,
            error_message=str(e),
        )


# LangGraph 节点函数
async def kg_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    """知识图谱构建师的 LangGraph 节点。"""
    document = state.get("document", "")
    book = state.get("book", "未命名")
    source = state.get("source", "material")
    doc_id = state.get("doc_id", str(uuid4())[:8])
    neo4j_client = state.get("neo4j_client")
    entity_index = state.get("entity_index")

    lessons = _get_lessons_for_kg_builder()
    if lessons:
        logger.info(f"应用历史教训: {len(lessons)} 条")

    result = await build_knowledge_graph(
        document=document,
        book=book,
        source=source,
        doc_id=doc_id,
        neo4j_client=neo4j_client,
        entity_index=entity_index,
    )

    await _record_kg_builder_outcome(doc_id, book, result, result.success)

    return {
        "kg_build_result": result.to_dict(),
        "entities_count": len(result.entities),
        "relations_count": len(result.relations),
        "chunks_processed": result.chunks_processed,
        "build_success": result.success,
    }
