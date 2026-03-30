"""文档解析器。

将文档内容分块处理，为后续的实体提取和关系抽取做准备。
"""

from __future__ import annotations

import logging
import re
from uuid import uuid4

from src.harness.retry import LLM_RETRY, retry
from src.tools.kg_storage.models import DocumentChunk

logger = logging.getLogger(__name__)


def _split_into_chunks(
    content: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[tuple[int, int, str]]:
    """将文本按字符数分块。"""
    if not content:
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0
    content_len = len(content)

    while start < content_len:
        end = min(start + chunk_size, content_len)

        if end < content_len:
            last_period = content.rfind("。", start, end)
            last_newline = content.rfind("\n", start, end)
            last_exclaim = content.rfind("！", start, end)
            last_question = content.rfind("？", start, end)

            boundaries = [last_period, last_newline, last_exclaim, last_question]
            best_boundary = max(b for b in boundaries if b > start)

            if best_boundary > start:
                end = best_boundary + 1

        chunk_content = content[start:end].strip()
        if chunk_content:
            chunks.append((start, end, chunk_content))

        start = end - overlap if end < content_len else end

    return chunks


@retry(config=LLM_RETRY)
async def parse_document(
    content: str,
    doc_id: str,
    book: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[DocumentChunk]:
    """解析文档内容，返回分块列表。

    Args:
        content: 文档内容
        doc_id: 文档 ID
        book: 所属书籍
        chunk_size: 每块最大字符数
        overlap: 块之间的重叠字符数

    Returns:
        文档分块列表
    """
    if not content or not content.strip():
        logger.warning(f"文档 {doc_id} 内容为空")
        return []

    cleaned_content = re.sub(r"\n{3,}", "\n\n", content.strip())
    raw_chunks = _split_into_chunks(cleaned_content, chunk_size, overlap)

    chunks: list[DocumentChunk] = []
    for chunk_index, (start_char, end_char, chunk_content) in enumerate(raw_chunks):
        chunk = DocumentChunk(
            chunk_id=f"{doc_id}_chunk_{chunk_index}_{str(uuid4())[:8]}",
            content=chunk_content,
            doc_id=doc_id,
            book=book,
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
        )
        chunks.append(chunk)

    logger.info(f"文档 {doc_id} 解析完成，共 {len(chunks)} 个分块")
    return chunks
