"""测试知识图谱服务层和素材收集智能体。"""

import pytest

from src.tools.graph_service import (
    fetch_materials_for_writing,
    save_creative_content,
)


class TestFetchMaterials:
    """测试素材获取功能。"""

    @pytest.mark.asyncio
    async def test_fetch_with_valid_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试有效的任务查询。"""

        class MockClient:
            async def query(self, query: str) -> str:
                return f"查询结果: {query}"

        from src.tools import graph_service

        monkeypatch.setattr(graph_service, "lightrag_client", MockClient())
        monkeypatch.setattr(graph_service, "creative_lightrag_client", MockClient())

        result = await fetch_materials_for_writing("孙悟空的性格")

        assert "素材图谱" in result
        assert "二创图谱" in result

    @pytest.mark.asyncio
    async def test_fetch_with_short_task(self) -> None:
        """测试任务描述太短的情况。"""
        result = await fetch_materials_for_writing("查")
        assert "太短" in result

    @pytest.mark.asyncio
    async def test_fetch_with_empty_task(self) -> None:
        """测试空任务。"""
        result = await fetch_materials_for_writing("")
        assert "太短" in result


class TestSaveCreativeContent:
    """测试内容保存功能。"""

    @pytest.mark.asyncio
    async def test_save_valid_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试保存有效内容。"""

        async def mock_insert(content: str) -> bool:
            return True

        from src.tools import graph_service

        monkeypatch.setattr(
            graph_service.creative_lightrag_client,
            "insert",
            mock_insert,
        )

        result = await save_creative_content(
            content="这是一段测试创作内容，足够长的文本内容。",
            title="测试标题",
        )

        assert result["success"] is True
        assert result["title"] == "测试标题"

    @pytest.mark.asyncio
    async def test_save_short_content(self) -> None:
        """测试内容太短。"""
        result = await save_creative_content(
            content="短",
            title="标题",
        )

        assert result["success"] is False
        assert "太短" in result["error"]

    @pytest.mark.asyncio
    async def test_save_empty_title(self) -> None:
        """测试空标题。"""
        result = await save_creative_content(
            content="这是一段足够长的测试内容文本内容，超过二十个字符。",
            title="",
        )

        assert result["success"] is False
        assert "空" in result["error"]


class TestResearcherNode:
    """测试 Researcher 智能体节点。"""

    @pytest.mark.asyncio
    async def test_researcher_node_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试默认模式（直接调用，不使用工具）。"""

        class MockClient:
            async def query(self, query: str) -> str:
                return f"素材: {query}"

        from src.agents import researcher
        from src.tools import graph_service

        monkeypatch.setattr(graph_service, "lightrag_client", MockClient())
        monkeypatch.setattr(graph_service, "creative_lightrag_client", MockClient())

        result = await researcher.researcher_node({"task": "孙悟空的性格"})

        assert "materials" in result
        assert "素材图谱" in result["materials"]

    @pytest.mark.asyncio
    async def test_researcher_node_with_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """测试工具调用模式。"""

        class MockClient:
            async def query(self, query: str) -> str:
                return f"查询结果: {query}"

        from src.agents import researcher
        from src.tools import graph_service

        monkeypatch.setattr(graph_service, "lightrag_client", MockClient())
        monkeypatch.setattr(graph_service, "creative_lightrag_client", MockClient())

        # 工具调用模式会回退到直接调用（因为没有真实 LLM）
        result = await researcher.researcher_node({
            "task": "孙悟空的性格",
            "use_tools": True,
        })

        assert "materials" in result
