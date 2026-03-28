"""LightRAG HTTP API 客户端，用于知识图谱查询。"""

from enum import Enum
from typing import Literal

import httpx

from src.config import settings

# LightRAG 支持的查询模式
QueryMode = Literal["local", "global", "hybrid", "mix", "naive"]


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
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def query(
        self,
        query: str,
        mode: QueryMode = "mix",
        stream: bool = False,
    ) -> str:
        """
        查询知识图谱。

        Args:
            query: 查询字符串
            mode: 查询模式 (local/global/hybrid/mix/naive)
            stream: 是否流式返回

        Returns:
            查询结果字符串
        """
        url = f"{self.base_url}/query"
        payload = {
            "query": query,
            "mode": mode,
            "stream": stream,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def insert(self, content: str) -> bool:
        """
        插入内容到知识图谱。

        Args:
            content: 要插入的内容

        Returns:
            是否成功
        """
        url = f"{self.base_url}/documents"
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

    async def health_check(self) -> bool:
        """检查 LightRAG 服务是否健康。"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception:
            return False


# 全局客户端实例
lightrag_client = LightRAGClient(graph_type=GraphType.MATERIAL)
creative_lightrag_client = LightRAGClient(graph_type=GraphType.CREATIVE)
