# 参考资料

> 沉淀 API 文档与第三方库指南，仅在需要调用时被精准检索介入。

## MiniMax API

- 兼容 OpenAI 接口格式
- Base URL: `https://api.minimax.chat/v1`
- 默认模型: `MiniMax-M2.7`

## LangGraph

- 文档: https://langchain-ai.github.io/langgraph/
- 核心概念: StateGraph, Node, Edge

## LightRAG

- GitHub: https://github.com/HKUDS/LightRAG
- 默认端口: 9621
- 健康检查: `GET /health`

## pydantic-settings

- 文档: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- 用法: 继承 `BaseSettings`，自动加载 `.env`
