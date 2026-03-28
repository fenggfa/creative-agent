"""LightRAG HTTP API 客户端，用于知识图谱操作。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

import httpx

from src.config import settings

# LightRAG 支持的查询模式
QueryMode = Literal["local", "global", "hybrid", "mix", "naive", "bypass"]


class GraphType(str, Enum):
    """知识图谱类型。"""

    MATERIAL = "material"  # 素材图谱（原作设定）
    CREATIVE = "creative"  # 二创图谱（创作内容）


class LightRAGClient:
    """LightRAG HTTP API 客户端。"""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
        graph_type: GraphType = GraphType.MATERIAL,
    ):
        self.graph_type = graph_type
        self.timeout = timeout

        # 根据图谱类型选择配置
        if graph_type == GraphType.MATERIAL:
            self.base_url = (base_url or settings.LIGHTRAG_URL).rstrip("/")
            self.api_key = api_key or settings.LIGHTRAG_API_KEY
        else:
            self.base_url = (base_url or settings.LIGHTRAG_CREATIVE_URL).rstrip("/")
            self.api_key = api_key or settings.LIGHTRAG_CREATIVE_API_KEY

    def _get_headers(self) -> dict[str, str]:
        """构建请求头。"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ==================== 查询相关 API ====================

    async def query(
        self,
        query: str,
        mode: QueryMode = "mix",
        stream: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        查询知识图谱。

        Args:
            query: 查询字符串
            mode: 查询模式 (local/global/hybrid/mix/naive/bypass)
            stream: 是否流式返回
            **kwargs: 其他查询参数 (top_k, response_type 等)

        Returns:
            查询结果字符串
        """
        url = f"{self.base_url}/query"
        payload: dict[str, Any] = {
            "query": query,
            "mode": mode,
            "stream": stream,
        }
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return str(data.get("response", ""))

    async def query_data(
        self,
        query: str,
        mode: QueryMode = "mix",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        查询知识图谱，返回原始检索数据（不含 LLM 生成）。

        Args:
            query: 查询字符串
            mode: 查询模式
            **kwargs: 其他查询参数

        Returns:
            包含 entities, relationships, chunks, references 的字典
        """
        url = f"{self.base_url}/query/data"
        payload: dict[str, Any] = {
            "query": query,
            "mode": mode,
        }
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    # ==================== 文档管理 API ====================

    async def insert(self, content: str) -> bool:
        """
        插入文本内容到知识图谱。

        Args:
            content: 要插入的文本内容

        Returns:
            是否成功
        """
        url = f"{self.base_url}/documents/text"
        payload = {"text": content}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return True
        except Exception:
            return False

    async def insert_texts(self, texts: list[str]) -> dict[str, Any]:
        """
        批量插入文本内容。

        Args:
            texts: 文本列表

        Returns:
            响应结果
        """
        url = f"{self.base_url}/documents/texts"
        payload = {"texts": texts}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def get_documents(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取文档列表。

        Args:
            status: 按状态筛选 (PENDING/PROCESSING/PROCESSED/FAILED)

        Returns:
            文档列表
        """
        url = f"{self.base_url}/documents"
        params: dict[str, str] = {}
        if status:
            params["status"] = status

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return list(response.json())

    async def get_documents_paginated(
        self,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> dict[str, Any]:
        """
        分页获取文档列表。

        Args:
            page: 页码
            page_size: 每页数量
            status: 按状态筛选

        Returns:
            分页结果
        """
        url = f"{self.base_url}/documents/paginated"
        payload: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            payload["status"] = status

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def delete_document(
        self,
        doc_ids: list[str],
        delete_file: bool = False,
        delete_llm_cache: bool = False,
    ) -> dict[str, Any]:
        """
        删除指定文档。

        Args:
            doc_ids: 文档 ID 列表
            delete_file: 是否删除源文件
            delete_llm_cache: 是否删除 LLM 缓存

        Returns:
            删除结果
        """
        url = f"{self.base_url}/documents/delete_document"
        payload = {
            "doc_ids": doc_ids,
            "delete_file": delete_file,
            "delete_llm_cache": delete_llm_cache,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # httpx delete 不支持 json 参数，使用 request 方法
            response = await client.request(
                "DELETE",
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def clear_documents(self) -> dict[str, Any]:
        """
        清空所有文档。

        Returns:
            清空结果
        """
        url = f"{self.base_url}/documents"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.delete(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def clear_cache(self) -> dict[str, Any]:
        """
        清除缓存。

        Returns:
            清除结果
        """
        url = f"{self.base_url}/documents/clear_cache"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def get_pipeline_status(self) -> dict[str, Any]:
        """
        获取处理管道状态。

        Returns:
            管道状态
        """
        url = f"{self.base_url}/documents/pipeline_status"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def get_status_counts(self) -> dict[str, int]:
        """
        获取各状态的文档数量。

        Returns:
            状态计数字典
        """
        url = f"{self.base_url}/documents/status_counts"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def scan_documents(self) -> dict[str, Any]:
        """
        扫描新文档。

        Returns:
            扫描结果
        """
        url = f"{self.base_url}/scan"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    # ==================== 实体/关系管理 API ====================

    async def delete_entity(self, entity_name: str) -> dict[str, Any]:
        """
        删除实体。

        Args:
            entity_name: 实体名称

        Returns:
            删除结果
        """
        url = f"{self.base_url}/documents/delete_entity"
        payload = {"entity_name": entity_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                "DELETE",
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def delete_relation(
        self,
        source_entity: str,
        target_entity: str,
    ) -> dict[str, Any]:
        """
        删除关系。

        Args:
            source_entity: 源实体名称
            target_entity: 目标实体名称

        Returns:
            删除结果
        """
        url = f"{self.base_url}/documents/delete_relation"
        payload = {
            "source_entity": source_entity,
            "target_entity": target_entity,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                "DELETE",
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def create_entity(
        self,
        entity_name: str,
        entity_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        创建实体。

        Args:
            entity_name: 实体名称
            entity_data: 实体数据 (description, entity_type 等)

        Returns:
            创建结果
        """
        url = f"{self.base_url}/graph/entity/create"
        payload = {
            "entity_name": entity_name,
            "entity_data": entity_data,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def edit_entity(
        self,
        entity_name: str,
        updated_data: dict[str, Any],
        allow_rename: bool = False,
        allow_merge: bool = False,
    ) -> dict[str, Any]:
        """
        编辑实体。

        Args:
            entity_name: 实体名称
            updated_data: 更新的数据
            allow_rename: 是否允许重命名
            allow_merge: 是否允许合并到已存在的实体

        Returns:
            更新结果
        """
        url = f"{self.base_url}/graph/entity/edit"
        payload = {
            "entity_name": entity_name,
            "updated_data": updated_data,
            "allow_rename": allow_rename,
            "allow_merge": allow_merge,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def merge_entities(
        self,
        entities_to_change: list[str],
        entity_to_change_into: str,
    ) -> dict[str, Any]:
        """
        合并多个实体。

        Args:
            entities_to_change: 要合并的实体列表（将被删除）
            entity_to_change_into: 目标实体名称（保留）

        Returns:
            合并结果
        """
        url = f"{self.base_url}/graph/entities/merge"
        payload = {
            "entities_to_change": entities_to_change,
            "entity_to_change_into": entity_to_change_into,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def create_relation(
        self,
        source_entity: str,
        target_entity: str,
        relation_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        创建关系。

        Args:
            source_entity: 源实体名称
            target_entity: 目标实体名称
            relation_data: 关系数据 (description, keywords, weight 等)

        Returns:
            创建结果
        """
        url = f"{self.base_url}/graph/relation/create"
        payload = {
            "source_entity": source_entity,
            "target_entity": target_entity,
            "relation_data": relation_data,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def edit_relation(
        self,
        source_entity: str,
        target_entity: str,
        updated_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        编辑关系。

        Args:
            source_entity: 源实体名称
            target_entity: 目标实体名称
            updated_data: 更新的数据

        Returns:
            更新结果
        """
        url = f"{self.base_url}/graph/relation/edit"
        payload = {
            "source_id": source_entity,
            "target_id": target_entity,
            "updated_data": updated_data,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    async def entity_exists(self, entity_name: str) -> bool:
        """
        检查实体是否存在。

        Args:
            entity_name: 实体名称

        Returns:
            是否存在
        """
        url = f"{self.base_url}/graph/entity/exists"
        params = {"name": entity_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return bool(data.get("exists", False))

    # ==================== 图谱查询 API ====================

    async def get_graph_labels(self) -> list[str]:
        """
        获取所有图谱标签。

        Returns:
            标签列表
        """
        url = f"{self.base_url}/graph/label/list"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return list(response.json())

    async def get_popular_labels(self, limit: int = 300) -> list[str]:
        """
        获取热门标签（按节点连接度排序）。

        Args:
            limit: 返回数量限制

        Returns:
            热门标签列表
        """
        url = f"{self.base_url}/graph/label/popular"
        params = {"limit": str(limit)}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return list(response.json())

    async def search_labels(
        self,
        query: str,
        limit: int = 50,
    ) -> list[str]:
        """
        模糊搜索标签。

        Args:
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            匹配的标签列表
        """
        url = f"{self.base_url}/graph/label/search"
        params = {"q": query, "limit": str(limit)}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return list(response.json())

    async def get_knowledge_graph(
        self,
        label: str,
        max_depth: int = 3,
        max_nodes: int = 1000,
    ) -> dict[str, Any]:
        """
        获取知识图谱子图。

        Args:
            label: 起始节点标签
            max_depth: 最大深度
            max_nodes: 最大节点数

        Returns:
            图谱数据（nodes, edges）
        """
        url = f"{self.base_url}/graphs"
        params = {
            "label": label,
            "max_depth": str(max_depth),
            "max_nodes": str(max_nodes),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return dict(response.json())

    # ==================== 系统 API ====================

    async def health_check(self) -> bool:
        """检查 LightRAG 服务是否健康。"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False

    async def get_health_info(self) -> dict[str, Any]:
        """
        获取健康检查详细信息。

        Returns:
            健康状态详情
        """
        url = f"{self.base_url}/health"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return dict(response.json())


# 全局客户端实例
lightrag_client = LightRAGClient(graph_type=GraphType.MATERIAL)
creative_lightrag_client = LightRAGClient(graph_type=GraphType.CREATIVE)
