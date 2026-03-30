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

        class MockKGService:
            async def query(self, query: str, book: str | None = None, source: str | None = None) -> str:
                return f"查询结果: {query}"

            async def connect(self) -> None:
                pass

        from src.tools import graph_service

        mock_service = MockKGService()
        monkeypatch.setattr(graph_service, "_local_kg_service", mock_service)

        result = await fetch_materials_for_writing("孙悟空的性格")

        assert "查询结果" in result

    @pytest.mark.asyncio
    async def test_fetch_with_book_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试按书名过滤查询。"""

        class MockKGService:
            async def query(self, query: str, book: str | None = None, source: str | None = None) -> str:
                return f"查询结果: {query} (book={book})"

            async def connect(self) -> None:
                pass

        from src.tools import graph_service

        mock_service = MockKGService()
        monkeypatch.setattr(graph_service, "_local_kg_service", mock_service)

        result = await fetch_materials_for_writing("孙悟空", book="西游记")

        assert "西游记" in result

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
    async def test_save_short_content(self) -> None:
        """测试内容太短。"""
        result = await save_creative_content(
            content="短",
            title="标题",
            book="西游记",
        )

        assert result["success"] is False
        assert "太短" in result["error"]

    @pytest.mark.asyncio
    async def test_save_empty_title(self) -> None:
        """测试空标题。"""
        result = await save_creative_content(
            content="这是一段足够长的测试内容文本内容，超过二十个字符。",
            title="",
            book="西游记",
        )

        assert result["success"] is False
        assert "空" in result["error"]

    @pytest.mark.asyncio
    async def test_save_empty_book(self) -> None:
        """测试空书名。"""
        result = await save_creative_content(
            content="这是一段足够长的测试内容文本内容，超过二十个字符。",
            title="测试标题",
            book="",
        )

        assert result["success"] is False
        assert "书名" in result["error"]


class TestResearcherNode:
    """测试 Researcher 智能体节点。"""

    @pytest.mark.asyncio
    async def test_researcher_node_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """测试默认模式（直接调用，不使用工具）。"""

        class MockKGService:
            async def query(self, query: str, book: str | None = None, source: str | None = None) -> str:
                return f"素材: {query}"

            async def connect(self) -> None:
                pass

        from src.agents import researcher
        from src.tools import graph_service

        mock_service = MockKGService()
        monkeypatch.setattr(graph_service, "_local_kg_service", mock_service)

        result = await researcher.researcher_node({"task": "孙悟空的性格"})

        assert "materials" in result
        assert "素材" in result["materials"]

    @pytest.mark.asyncio
    async def test_researcher_node_with_tools(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """测试工具调用模式。"""

        class MockKGService:
            async def query(self, query: str, book: str | None = None, source: str | None = None) -> str:
                return f"查询结果: {query}"

            async def connect(self) -> None:
                pass

        from src.agents import researcher
        from src.tools import graph_service

        mock_service = MockKGService()
        monkeypatch.setattr(graph_service, "_local_kg_service", mock_service)

        result = await researcher.researcher_node({
            "task": "孙悟空的性格",
            "use_tools": True,
        })

        assert "materials" in result
