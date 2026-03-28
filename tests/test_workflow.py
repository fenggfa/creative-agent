"""创作智能体工作流基础测试。"""

import pytest

from src.config import Settings
from src.workflow.orchestrator import create_workflow
from src.workflow.state import AgentState


class TestConfig:
    """测试配置加载。"""

    def test_default_settings(self):
        """测试默认配置是否正确加载。"""
        settings = Settings()
        assert settings.LLM_BASE_URL == "https://api.minimax.chat/v1"
        assert settings.LLM_MODEL == "MiniMax-M2.7"
        assert settings.MAX_REVISIONS == 2


class TestWorkflow:
    """测试工作流图结构。"""

    def test_workflow_creation(self):
        """测试工作流图是否正确创建。"""
        workflow = create_workflow()
        assert workflow is not None

        # 检查节点是否存在
        nodes = workflow.nodes
        assert "researcher" in nodes
        assert "writer" in nodes
        assert "reviewer" in nodes

    def test_workflow_state_structure(self):
        """测试状态是否包含必需字段。"""
        # 通过 TypedDict 进行类型检查
        state: AgentState = {
            "task": "test task",
            "materials": "",
            "draft": "",
            "review_feedback": "",
            "approved": False,
            "revision_count": 0,
            "final_output": "",
        }
        assert "task" in state
        assert "materials" in state
        assert "draft" in state


@pytest.mark.asyncio
class TestLightRAGClient:
    """测试 LightRAG 客户端。"""

    async def test_client_initialization(self):
        """测试客户端能否正确初始化。"""
        from src.tools.lightrag import LightRAGClient

        client = LightRAGClient(base_url="http://localhost:9621")
        assert client.base_url == "http://localhost:9621"

    async def test_health_check_offline(self):
        """测试服务离线时的健康检查。"""
        from src.tools.lightrag import LightRAGClient

        client = LightRAGClient(base_url="http://localhost:9999")
        result = await client.health_check()
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
