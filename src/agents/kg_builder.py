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

from src.config import settings
from src.harness import OutcomeType, TaskCategory, get_agent_memory, learn_from_failure
from src.harness.provider import get_constraint_provider
from src.harness.retry import LLM_RETRY, retry
from src.tools.kg_extractor import (
    clear_trace_logger,
    extract_entities,
    extract_relations,
    get_trace_logger,
    init_trace_logger,
    parse_document,
)
from src.tools.kg_extractor.embed_client import EmbedClient, get_embed_client
from src.tools.kg_storage import EntityIndex, Neo4jClient
from src.tools.kg_storage.models import DocumentChunk, GraphBuildResult

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


async def _vectorize_data(
    embed_client: EmbedClient,
    entities: list[Any],
    relations: list[Any],
    chunks: list[DocumentChunk],
) -> None:
    """向量化实体、关系和文本块。

    Args:
        embed_client: 嵌入服务客户端
        entities: 实体列表
        relations: 关系列表
        chunks: 文本块列表
    """
    # 向量化实体名称
    if entities:
        entity_names = [e.name for e in entities]
        name_embeddings = await embed_client.embed_batch(entity_names)
        for entity, embedding in zip(entities, name_embeddings, strict=False):
            entity.name_embedding = embedding

        # 向量化实体描述
        entity_descs = [e.description for e in entities if e.description]
        if entity_descs:
            desc_embeddings = await embed_client.embed_batch(entity_descs)
            desc_idx = 0
            for entity in entities:
                if entity.description:
                    entity.desc_embedding = desc_embeddings[desc_idx]
                    desc_idx += 1

    # 向量化关系描述
    if relations:
        relation_descs = [r.description for r in relations if r.description]
        if relation_descs:
            desc_embeddings = await embed_client.embed_batch(relation_descs)
            desc_idx = 0
            for relation in relations:
                if relation.description:
                    relation.desc_embedding = desc_embeddings[desc_idx]
                    desc_idx += 1

    # 向量化文本块内容
    if chunks:
        chunk_contents = [c.content for c in chunks]
        content_embeddings = await embed_client.embed_batch(chunk_contents)
        for chunk, embedding in zip(chunks, content_embeddings, strict=False):
            chunk.content_embedding = embedding

    logger.info(
        f"向量化完成: {len(entities)} 实体, {len(relations)} 关系, {len(chunks)} 文本块"
    )


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
    enable_embedding: bool = True,
    debug_mode: bool | None = None,
) -> GraphBuildResult:
    """构建知识图谱。

    完整流程：
    1. 文档解析 → 分块
    2. 实体提取 → 识别实体
    3. 关系抽取 → 发现关系
    4. 向量化 → 生成向量 (可选)
    5. 存储入库 → Neo4j + SQLite

    Args:
        document: 文档内容
        book: 所属书籍
        source: 来源 (material/creative)
        doc_id: 文档 ID（可选）
        neo4j_client: Neo4j 客户端（可选）
        entity_index: 实体索引（可选）
        enable_embedding: 是否启用向量化（默认 True）
        debug_mode: 是否启用调试模式（None 时使用配置）

    Returns:
        图谱构建结果
    """
    start_time = time.time()
    doc_id = doc_id or str(uuid4())[:8]

    # 确定调试模式
    is_debug = debug_mode if debug_mode is not None else settings.KG_DEBUG_MODE

    # 初始化追踪日志器
    if is_debug:
        init_trace_logger(
            doc_id=doc_id,
            book=book,
            output_dir=settings.KG_TRACE_OUTPUT_DIR,
            max_content_length=settings.KG_TRACE_MAX_CONTENT_LENGTH,
        )
        logger.info(f"调试模式已启用，追踪输出目录: {settings.KG_TRACE_OUTPUT_DIR}")

    try:
        # 1. 文档解析
        step_start = time.time()
        logger.info(f"开始解析文档: {book}/{doc_id}")
        chunks = await parse_document(document, doc_id, book)
        step_duration = (time.time() - step_start) * 1000

        if is_debug:
            tracer = get_trace_logger()
            if tracer:
                tracer.log_parse_document(chunks, step_duration)

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
        step_start = time.time()
        logger.info(f"开始提取实体: {book}/{doc_id}")
        entities = await extract_entities(chunks, book, source)
        step_duration = (time.time() - step_start) * 1000

        if is_debug:
            tracer = get_trace_logger()
            if tracer:
                tracer.log_extract_entities(entities, step_duration)

        if not entities:
            logger.warning(f"文档 {book}/{doc_id} 未提取到任何实体")

        # 3. 关系抽取
        step_start = time.time()
        logger.info(f"开始抽取关系: {book}/{doc_id}")
        relations = await extract_relations(chunks, entities, book, source)
        step_duration = (time.time() - step_start) * 1000

        if is_debug:
            tracer = get_trace_logger()
            if tracer:
                tracer.log_extract_relations(relations, step_duration)

        # 4. 向量化 (可选)
        embed_client: EmbedClient | None = None
        if enable_embedding:
            try:
                embed_client = get_embed_client()
                await embed_client.connect()

                if await embed_client.health_check():
                    step_start = time.time()
                    logger.info(f"开始向量化: {book}/{doc_id}")
                    await _vectorize_data(embed_client, entities, relations, chunks)
                    step_duration = (time.time() - step_start) * 1000

                    if is_debug:
                        tracer = get_trace_logger()
                        if tracer:
                            tracer.log_vectorize(
                                entities_count=len(entities),
                                relations_count=len(relations),
                                chunks_count=len(chunks),
                                vector_dim=settings.EMBED_DIMENSION,
                                duration_ms=step_duration,
                            )
                else:
                    logger.warning("嵌入服务不可用，跳过向量化")
                    embed_client = None
            except Exception as e:
                logger.warning(f"向量化失败，跳过: {e}")
                embed_client = None

        # 5. 存储入库
        step_start = time.time()
        entities_stored = 0
        relations_stored = 0
        chunks_stored = 0

        if neo4j_client and entities:
            logger.info(f"存储实体到 Neo4j: {book}/{doc_id}")
            await neo4j_client.create_entities_batch(entities)
            entities_stored = len(entities)

            if relations:
                logger.info(f"存储关系到 Neo4j: {book}/{doc_id}")
                await neo4j_client.create_relations_batch(relations)
                relations_stored = len(relations)

            # 存储文本块
            if chunks:
                logger.info(f"存储文本块到 Neo4j: {book}/{doc_id}")
                await neo4j_client.create_chunks_batch(chunks)
                chunks_stored = len(chunks)

        if entity_index and entities:
            logger.info(f"索引实体: {book}/{doc_id}")
            await entity_index.index_entities_batch(entities)

            # 索引文本块
            if chunks:
                logger.info(f"索引文本块: {book}/{doc_id}")
                await entity_index.index_chunks_batch(chunks)

        step_duration = (time.time() - step_start) * 1000

        if is_debug:
            tracer = get_trace_logger()
            if tracer:
                tracer.log_storage(
                    entities_stored=entities_stored,
                    relations_stored=relations_stored,
                    chunks_stored=chunks_stored,
                    duration_ms=step_duration,
                )

        # 关闭嵌入客户端
        if embed_client:
            await embed_client.close()

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

        # 保存追踪报告
        if is_debug:
            tracer = get_trace_logger()
            if tracer:
                json_path, md_path = tracer.finalize()
                logger.info(f"调试报告已保存: {md_path}")

        logger.info(
            f"知识图谱构建完成: {book}/{doc_id} - "
            f"{len(entities)} 实体, {len(relations)} 关系, "
            f"{len(chunks)} 文本块, 耗时 {build_time:.2f}s"
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

    finally:
        # 清理追踪器
        if is_debug:
            clear_trace_logger()


# LangGraph 节点函数
async def kg_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    """知识图谱构建师的 LangGraph 节点。"""
    document = state.get("document", "")
    book = state.get("book", "未命名")
    source = state.get("source", "material")
    doc_id = state.get("doc_id", str(uuid4())[:8])
    neo4j_client = state.get("neo4j_client")
    entity_index = state.get("entity_index")
    enable_embedding = state.get("enable_embedding", True)
    debug_mode = state.get("debug_mode")

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
        enable_embedding=enable_embedding,
        debug_mode=debug_mode,
    )

    await _record_kg_builder_outcome(doc_id, book, result, result.success)

    return {
        "kg_build_result": result.to_dict(),
        "entities_count": len(result.entities),
        "relations_count": len(result.relations),
        "chunks_processed": result.chunks_processed,
        "build_success": result.success,
    }
