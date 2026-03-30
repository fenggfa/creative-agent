"""关系抽取器。

从文档分块和已提取的实体中抽取实体间的关系。
"""

from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.config import settings
from src.harness.retry import LLM_RETRY, retry
from src.tools.kg_storage.models import DocumentChunk, Entity, Relation

logger = logging.getLogger(__name__)

# 关系抽取系统提示词
RELATION_EXTRACTOR_PROMPT = """你是一个专业的关系抽取专家。你的任务是从文本中识别实体之间的关系。

常见关系类型：
- located_at：位于
- knows：认识
- owns：拥有
- participates_in：参与
- related_to：相关
- parent_of：父母
- friend_of：朋友
- enemy_of：敌人
- member_of：成员
- leader_of：领导
- creator_of：创造者
- uses：使用

抽取原则：
1. 只抽取文本中明确描述的关系
2. 关系必须有明确的语义
3. 描述要简洁说明关系的具体内容
4. 置信度：0.0-1.0

请以 JSON 数组格式返回，每个关系的格式为：
{{"source": "源实体名称", "target": "目标实体名称", "type": "关系类型",
  "description": "描述", "confidence": 0.9}}

如果没有找到关系，返回空数组 []
"""


def _parse_relation_response(
    response_text: str,
    entities: list[Entity],
    book: str,
    source: str,
) -> list[Relation]:
    """解析 LLM 返回的关系 JSON。"""
    relations: list[Relation] = []

    # 构建实体名称集合
    entity_names: set[str] = {e.name for e in entities}

    json_match = re.search(r"\[[\s\S]*\]", response_text)
    if not json_match:
        logger.warning("未找到 JSON 数组")
        return relations

    try:
        data = json.loads(json_match.group())
        if not isinstance(data, list):
            return relations

        for item in data:
            if not isinstance(item, dict):
                continue

            source_name = item.get("source", "").strip()
            target_name = item.get("target", "").strip()

            if not source_name or not target_name:
                continue

            # 验证实体存在
            if source_name not in entity_names or target_name not in entity_names:
                continue

            relation = Relation(
                source_entity_name=source_name,
                target_entity_name=target_name,
                relation_type=item.get("type", "related_to"),
                book=book,
                source=source,
                description=item.get("description", "")[:500],
                confidence=float(item.get("confidence", 1.0)),
            )
            relations.append(relation)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}")

    return relations


@retry(config=LLM_RETRY)
async def extract_relations(
    chunks: list[DocumentChunk],
    entities: list[Entity],
    book: str,
    source: str = "material",
) -> list[Relation]:
    """从文档分块中抽取实体间的关系。

    Args:
        chunks: 文档分块列表
        entities: 已提取的实体列表
        book: 所属书籍
        source: 来源 (material/creative)

    Returns:
        抽取的关系列表（已去重）
    """
    if not chunks or not entities:
        return []

    llm = ChatOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=60.0,
    )

    all_content = "\n\n".join(chunk.content for chunk in chunks[:5])

    entity_list = "\n".join(
        f"- {e.name} ({e.entity_type})"
        for e in entities[:20]
    )

    prompt = f"""已知实体列表：
{entity_list}

请从以下文本中抽取这些实体之间的关系：

{all_content}

请返回 JSON 数组格式的关系列表。"""

    messages = [
        SystemMessage(content=RELATION_EXTRACTOR_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = await llm.ainvoke(messages)
        raw_content = response.content
        response_text = raw_content if isinstance(raw_content, str) else str(raw_content)

        relations = _parse_relation_response(response_text, entities, book, source)

        # 去重
        seen: set[tuple[str, str, str]] = set()
        unique_relations: list[Relation] = []
        for rel in relations:
            key = (rel.source_entity_name, rel.target_entity_name, rel.relation_type)
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)

        logger.info(f"从书籍 {book} 抽取到 {len(unique_relations)} 个关系")
        return unique_relations

    except Exception as e:
        logger.error(f"关系抽取失败: {e}")
        return []
