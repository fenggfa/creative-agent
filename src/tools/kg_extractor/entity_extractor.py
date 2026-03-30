"""实体提取器。

从文档分块中提取实体，支持自由类型。
"""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.harness.retry import LLM_RETRY, retry
from src.tools.kg_storage.models import RECOMMENDED_ENTITY_TYPES, DocumentChunk, Entity

logger = logging.getLogger(__name__)

# 实体提取系统提示词
ENTITY_EXTRACTOR_PROMPT = f"""你是一个专业的知识提取专家。你的任务是从文本中识别并提取实体。

推荐的实体类型（优先使用）：
{chr(10).join(f'- {t}' for t in RECOMMENDED_ENTITY_TYPES)}

如有需要，可以自定义类型（如：境界、功法、种族、血脉...）。

提取原则：
1. 只提取明确提到的实体，不要推断或猜测
2. 实体名称要统一，使用文本中的原始名称
3. 描述要简洁，概括实体的核心特征
4. 置信度：0.0-1.0，表示对提取结果的确定程度

请以 JSON 数组格式返回提取结果，每个实体的格式为：
{{"name": "实体名称", "type": "实体类型", "description": "描述", "confidence": 0.9}}

如果没有找到实体，返回空数组 []
"""


def _parse_entity_response(response_text: str, book: str, source: str) -> list[Entity]:
    """解析 LLM 返回的实体 JSON。"""
    entities: list[Entity] = []

    json_match = re.search(r"\[[\s\S]*\]", response_text)
    if not json_match:
        logger.warning("未找到 JSON 数组")
        return entities

    try:
        data = json.loads(json_match.group())
        if not isinstance(data, list):
            return entities

        for item in data:
            if not isinstance(item, dict):
                continue

            name = item.get("name", "").strip()
            if not name:
                continue

            entity = Entity(
                name=name,
                book=book,
                source=source,
                entity_type=item.get("type", "concept"),
                description=item.get("description", "")[:500],
                confidence=float(item.get("confidence", 1.0)),
            )
            entities.append(entity)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}")

    return entities


@retry(config=LLM_RETRY)
async def extract_entities(
    chunks: list[DocumentChunk],
    book: str,
    source: str = "material",
) -> list[Entity]:
    """从文档分块中提取实体。

    Args:
        chunks: 文档分块列表
        book: 所属书籍
        source: 来源 (material/creative)

    Returns:
        提取的实体列表（已去重）
    """
    if not chunks:
        return []

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=60.0,
    )

    all_content = "\n\n".join(chunk.content for chunk in chunks[:5])

    prompt = f"""请从以下文本中提取实体：

{all_content}

请返回 JSON 数组格式的实体列表。"""

    messages = [
        SystemMessage(content=ENTITY_EXTRACTOR_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw_content = response.content
        response_text = raw_content if isinstance(raw_content, str) else str(raw_content)

        entities = _parse_entity_response(response_text, book, source)

        # 去重（按名称）
        seen_names: set[str] = set()
        unique_entities: list[Entity] = []
        for entity in entities:
            if entity.name not in seen_names:
                seen_names.add(entity.name)
                unique_entities.append(entity)

        logger.info(f"从书籍 {book} 提取到 {len(unique_entities)} 个实体")
        return unique_entities

    except Exception as e:
        logger.error(f"实体提取失败: {e}")
        return []
