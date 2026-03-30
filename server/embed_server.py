#!/usr/bin/env python
"""
嵌入服务 - OpenAI 兼容 API

提供与 OpenAI embeddings API 兼容的接口
支持 SentenceTransformers 本地模型加载

启动方式:
    python embed_server.py

环境变量:
    EMBED_MODEL_PATH - 模型路径
    EMBED_HOST - 服务地址，默认 0.0.0.0
    EMBED_PORT - 服务端口，默认 8100
"""

import os
import time
from typing import Any

# 环境优化
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ============== 配置 ==============

EMBED_MODEL_PATH = os.getenv(
    "EMBED_MODEL_PATH",
    "/Users/fenggf/Documents/models/embeddings/bge-m3"
)
EMBED_MODEL_NAME = "bge-m3"
HOST = os.getenv("EMBED_HOST", "0.0.0.0")
PORT = int(os.getenv("EMBED_PORT", "8100"))

# 量化配置
# - QUANTIZATION: 量化类型，可选 "none"（默认）、"int8"、"float16"
# - int8: 动态量化，适合 CPU 推理，模型缩小约 75%，速度提升 2-3x
# - float16: 半精度，适合 GPU 推理，模型缩小 50%，几乎无损
QUANTIZATION = os.getenv("QUANTIZATION", "int8").lower()

# 模型最大 token 数（根据模型名自动设置）
MODEL_MAX_TOKENS: dict[str, int] = {
    "bge-m3": 8192,
    "bge-large-zh-v1.5": 512,
    "jina-embeddings-v2-base-zh": 8192,
}

# 滑动窗口配置
# - CHUNK_OVERLAP_RATIO: 窗口重叠比例，10% 可保持上下文连贯
# - CHARS_PER_TOKEN_ZH: 中文字符与 token 的实测比例约 0.7
#   （512 tokens ≈ 350 中文字符，8192 tokens ≈ 5700 中文字符）
CHUNK_OVERLAP_RATIO = 0.1
CHARS_PER_TOKEN_ZH = 0.7

# ============== 模型加载 ==============

embed_model: Any = None


def apply_quantization(model: Any, quant_type: str) -> Any:
    """应用量化到模型。

    Args:
        model: SentenceTransformer 模型
        quant_type: 量化类型 ("int8", "float16", "none")

    Returns:
        量化后的模型
    """
    if quant_type == "none":
        return model

    import torch

    if quant_type == "float16":
        # GPU 半精度量化
        if torch.cuda.is_available():
            print("⚡ 应用 float16 量化（GPU 模式）")
            model.half()
        else:
            print("⚠️ CPU 不支持 float16，跳过量化")
        return model

    if quant_type == "int8":
        # CPU 动态量化
        print("⚡ 应用 int8 动态量化（CPU 模式）")

        # 获取底层的 transformer 模型
        try:
            # SentenceTransformer 结构: [0] = Transformer, [1] = Pooling, ...
            transformer_module = model[0]
            if hasattr(transformer_module, 'auto_model'):
                # 量化 transformer 的 Linear 层
                transformer_module.auto_model = torch.quantization.quantize_dynamic(
                    transformer_module.auto_model,
                    {torch.nn.Linear},
                    dtype=torch.qint8
                )
                print("✅ int8 量化完成")
            else:
                print("⚠️ 无法访问 transformer 层，跳过量化")
        except Exception as e:
            print(f"⚠️ 量化失败: {e}")

        return model

    print(f"⚠️ 未知的量化类型: {quant_type}，跳过量化")
    return model


def load_model() -> Any:
    """加载嵌入模型（使用 SentenceTransformers，支持量化）"""
    global embed_model
    if embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers 未安装，请运行: pip install sentence-transformers"
            ) from e

        print(f"\n{'='*60}")
        print(f"正在加载嵌入模型: {EMBED_MODEL_PATH}")
        if QUANTIZATION != "none":
            print(f"量化模式: {QUANTIZATION}")
        print("="*60 + "\n")

        # 加载模型（新版本 SentenceTransformer 自动检测格式）
        embed_model = SentenceTransformer(
            EMBED_MODEL_PATH,
            trust_remote_code=True,
        )

        # 应用量化
        if QUANTIZATION != "none":
            embed_model = apply_quantization(embed_model, QUANTIZATION)

        print("✅ 模型加载完成\n")
    return embed_model


# ============== 滑动窗口工具 ==============


def sliding_window_chunk(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """将长文本切分为滑动窗口块。

    Args:
        text: 输入文本
        max_chars: 每个块的最大字符数
        overlap_chars: 重叠字符数

    Returns:
        文本块列表
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + max_chars

        # 尝试在句子边界切分
        if end < len(text):
            # 向后查找句子结束符
            for sep in ['。', '！', '？', '；', '.', '!', '?', ';', '\n']:
                pos = text.rfind(sep, start, end)
                if pos > start + max_chars // 2:
                    end = pos + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 滑动窗口：向前移动 (块大小 - 重叠)
        start = end - overlap_chars if end < len(text) else len(text)

    return chunks


def merge_embeddings(embeddings: list[np.ndarray], weights: list[float] | None = None) -> np.ndarray:
    """合并多个嵌入向量为单一向量。

    使用加权平均，默认权重为各块的长度。

    Args:
        embeddings: 嵌入向量列表
        weights: 权重列表（可选）

    Returns:
        合并后的归一化嵌入向量
    """
    if len(embeddings) == 1:
        return embeddings[0]

    embeddings_array = np.array(embeddings)

    if weights is None:
        # 均匀权重
        weights = [1.0] * len(embeddings)

    weights_array = np.array(weights) / sum(weights)

    # 加权平均
    merged = np.average(embeddings_array, axis=0, weights=weights_array)

    # 归一化
    norm = np.linalg.norm(merged)
    if norm > 0:
        merged = merged / norm

    return merged


# ============== OpenAI 兼容 API 模型 ==============


class EmbeddingRequest(BaseModel):
    """OpenAI 兼容的嵌入请求"""
    input: list[str] | str = Field(..., description="要嵌入的文本")
    model: str = Field(default=EMBED_MODEL_NAME)
    encoding_format: str | None = Field(default="float")
    use_sliding_window: bool = Field(
        default=False,
        description="对超长文本使用滑动窗口切分（仅用于 512 token 限制的模型）"
    )


class EmbeddingObject(BaseModel):
    """单个嵌入对象"""
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingResponse(BaseModel):
    """OpenAI 兼容的嵌入响应"""
    object: str = "list"
    data: list[EmbeddingObject]
    model: str
    usage: dict[str, int]


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    owned_by: str = "BAAI"  # BGE 系列模型由 BAAI 开发


class ModelList(BaseModel):
    """模型列表"""
    object: str = "list"
    data: list[ModelInfo]


# ============== FastAPI 应用 ==============

app = FastAPI(
    title="Embedding Server (OpenAI Compatible)",
    description="嵌入服务 - OpenAI 兼容 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    """根路径"""
    return {
        "message": "Embedding Server (OpenAI Compatible)",
        "model": EMBED_MODEL_NAME,
        "model_path": EMBED_MODEL_PATH,
        "quantization": QUANTIZATION,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查"""
    return {"status": "ok", "model": EMBED_MODEL_NAME, "quantization": QUANTIZATION}


@app.get("/v1/models", response_model=ModelList)
def list_models() -> ModelList:
    """列出可用模型 - OpenAI 兼容接口"""
    return ModelList(
        object="list",
        data=[
            ModelInfo(id=EMBED_MODEL_NAME, owned_by="BAAI"),
        ]
    )


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """创建嵌入向量 - OpenAI 兼容接口

    支持滑动窗口处理长文本：
    - 当文本超过模型最大 token 限制时，自动切分为多个窗口
    - 对各窗口分别计算嵌入，然后加权平均合并
    - 保留句子边界，避免语义断裂
    """
    model = load_model()

    # 处理输入
    texts = request.input if isinstance(request.input, list) else [request.input]

    if not texts:
        raise HTTPException(status_code=400, detail="input cannot be empty")

    # 动态获取模型最大 token 数
    max_tokens = MODEL_MAX_TOKENS.get(EMBED_MODEL_NAME, 512)
    max_chars = int(max_tokens * CHARS_PER_TOKEN_ZH)
    overlap_chars = int(max_chars * CHUNK_OVERLAP_RATIO)

    # 日志输出
    total_chars = sum(len(t) for t in texts)
    long_texts = [t for t in texts if len(t) > max_chars]

    if long_texts and request.use_sliding_window:
        print(f"[嵌入] 检测到 {len(long_texts)} 个长文本，启用滑动窗口模式")
        print(f"       模型限制: {max_tokens} tokens, 最大块: {max_chars} 字符, 重叠: {overlap_chars} 字符")

    print(f"[嵌入] 开始处理 {len(texts)} 个文本，共 {total_chars} 字符...")

    start_time = time.time()

    # 处理每个文本
    all_embeddings: list[np.ndarray] = []

    for text in texts:
        if len(text) > max_chars and request.use_sliding_window:
            # 滑动窗口切分
            chunks = sliding_window_chunk(text, max_chars, overlap_chars)
            print(f"       切分为 {len(chunks)} 个块")

            # 对每个块计算嵌入
            chunk_embeddings: list[np.ndarray] = []
            chunk_weights: list[float] = []

            for chunk in chunks:
                emb = model.encode(chunk, normalize_embeddings=True)
                chunk_embeddings.append(emb)
                chunk_weights.append(len(chunk))

            # 合并嵌入
            merged = merge_embeddings(chunk_embeddings, chunk_weights)
            all_embeddings.append(merged)
        else:
            # 正常处理
            emb = model.encode(text, normalize_embeddings=True)
            all_embeddings.append(emb)

    embeddings = np.array(all_embeddings)

    elapsed = time.time() - start_time
    print(f"[嵌入] 完成，耗时 {elapsed:.2f}秒，速度 {total_chars/elapsed:.0f} 字符/秒")

    # 构建 OpenAI 格式响应
    data = []
    for i, emb in enumerate(embeddings):
        data.append(EmbeddingObject(
            object="embedding",
            embedding=emb.tolist(),
            index=i,
        ))

    # 计算token数（使用实测比例）
    total_tokens = int(total_chars / CHARS_PER_TOKEN_ZH)

    return EmbeddingResponse(
        object="list",
        data=data,
        model=EMBED_MODEL_NAME,
        usage={
            "prompt_tokens": total_tokens,
            "total_tokens": total_tokens,
        }
    )


def warmup() -> None:
    """预热模型，消除首次请求延迟"""
    print("🔥 预热模型...")
    model = load_model()
    model.encode("预热文本", normalize_embeddings=True)
    print("✅ 预热完成\n")


# ============== 主函数 ==============

def main() -> None:
    print("\n" + "=" * 60)
    print("嵌入服务 (OpenAI Compatible)")
    print("=" * 60)
    print(f"模型: {EMBED_MODEL_NAME}")
    print(f"路径: {EMBED_MODEL_PATH}")
    print(f"量化: {QUANTIZATION}")
    print(f"地址: http://{HOST}:{PORT}")
    print("=" * 60 + "\n")

    # 启动前加载模型并预热
    load_model()
    warmup()
    print(f"🚀 嵌入服务已启动: http://{HOST}:{PORT}")
    print(f"   API: POST http://{HOST}:{PORT}/v1/embeddings\n")

    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
