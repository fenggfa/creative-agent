"""配置管理模块，使用 pydantic-settings 加载环境变量。"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量加载。"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # MiniMax 大模型配置（从环境变量加载）
    LLM_BASE_URL: str = "https://api.minimax.chat/v1"
    LLM_API_KEY: str = ""  # 必须从 .env 文件加载
    LLM_MODEL: str = "MiniMax-M2.7"

    # LightRAG 配置
    LIGHTRAG_URL: str = "http://localhost:9621"
    LIGHTRAG_API_KEY: str = ""

    # 工作流配置
    MAX_REVISIONS: int = 2


# 全局配置实例
settings = Settings()
