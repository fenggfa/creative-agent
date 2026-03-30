#!/usr/bin/env python
"""
NLU 服务 - RexUniNLU 模型 HTTP 服务

提供通用自然语言理解能力:
- 命名实体识别 (NER)
- 关系抽取
- 文本分类
- 情感分析
- 事件抽取

启动方式:
    python nlu_server.py

环境变量:
    NLU_MODEL_PATH - 模型路径
    NLU_HOST - 服务地址，默认 0.0.0.0
    NLU_PORT - 服务端口，默认 8200
"""

import os
import sys
import time
import json
from typing import Any
from collections import defaultdict

# 环境优化
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ============== 配置 ==============

NLU_MODEL_PATH = os.getenv(
    "NLU_MODEL_PATH",
    "/Users/fenggf/Documents/models/LLM/nlp_deberta_rex-uninlu_chinese-base"
)
NLU_MODEL_NAME = "rex-uninlu"
HOST = os.getenv("NLU_HOST", "0.0.0.0")
PORT = int(os.getenv("NLU_PORT", "8200"))

# 模型参数
MAX_LEN = 512
STRIDE_LEN = 32
HINT_MAX_LEN = 256
PREFIX_STRING_MAX_LEN = 125
INFO_TYPE_MAX_LEN = 125

# ============== 模型加载 ==============

# 从模型目录导入模块
sys.path.insert(0, NLU_MODEL_PATH)

from transformers import AutoTokenizer, AutoConfig

# 模型组件
model: Any = None
tokenizer: Any = None
device: Any = None


def load_model() -> tuple[Any, Any]:
    """加载 NLU 模型和 tokenizer"""
    global model, tokenizer, device

    if model is not None:
        return model, tokenizer

    print(f"\n{'='*60}")
    print(f"正在加载 NLU 模型: {NLU_MODEL_PATH}")
    print("="*60 + "\n")

    # 设置设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"设备: {device}")

    # 加载 tokenizer
    tokenizer = AutoTokenizer.from_pretrained(NLU_MODEL_PATH)
    tokenizer.add_special_tokens({
        "additional_special_tokens": ["[PREFIX]", "[TYPE]", "[CLASSIFY]", "[MULTICLASSIFY]"]
    })

    # 加载模型配置
    config = AutoConfig.from_pretrained(NLU_MODEL_PATH)

    # 创建模型参数
    from dataclasses import dataclass, field

    @dataclass
    class TrainingArgs:
        bert_model_dir: str = NLU_MODEL_PATH
        load_checkpoint: str = NLU_MODEL_PATH
        no_cuda: bool = not torch.cuda.is_available()

    @dataclass
    class ModelArgs:
        hidden_size: int = 768
        num_attention_heads: int = 1
        attention_probs_dropout_prob: float = 0.3
        hidden_dropout_prob: float = 0.3

    training_args = TrainingArgs()
    model_args = ModelArgs()

    # 导入并创建模型
    from rex.model.model import RexModel

    model = RexModel(config, training_args, model_args)

    # 加载权重
    model_path = os.path.join(NLU_MODEL_PATH, "pytorch_model.bin")
    if device.type == "cpu":
        model.load_state_dict(
            torch.load(model_path, map_location=torch.device("cpu")),
            strict=False
        )
    else:
        model.load_state_dict(torch.load(model_path), strict=False)
        model = model.to(device)

    model.eval()
    print("✅ 模型加载完成\n")

    return model, tokenizer


# ============== 推理逻辑 ==============


def build_position_ids_attn_mask(
    token_id_list: list[int],
    token_type_ids: list[int],
    attention_mask: list[int]
) -> tuple[list[int], list[list[int]]]:
    """构建 position_ids 和 2D attention_mask"""
    TYPE_ID = tokenizer.convert_tokens_to_ids("[TYPE]")
    PREFIX_ID = tokenizer.convert_tokens_to_ids("[PREFIX]")

    segs: dict[str, list] = {"text": [], "prefix": [], "cls": [0]}
    assert token_id_list[0] == tokenizer.cls_token_id and token_id_list[1] == PREFIX_ID

    pre_special_id = tokenizer.cls_token_id
    for i, t in enumerate(token_id_list):
        if i == 0:
            continue
        if t == PREFIX_ID:
            new_prefix_seg: dict[str, Any] = {"span": [i], "type": []}
            segs["prefix"].append(new_prefix_seg)
            pre_special_id = t
        elif t == TYPE_ID:
            new_type_seg = {"span": [i]}
            segs["prefix"][-1]["type"].append(new_type_seg)
            pre_special_id = t
        elif t == tokenizer.sep_token_id:
            segs["text"].append(i)
            pre_special_id = t
        else:
            if pre_special_id == PREFIX_ID:
                segs["prefix"][-1]["span"].append(i)
            elif pre_special_id == TYPE_ID:
                segs["prefix"][-1]["type"][-1]["span"].append(i)
            else:
                assert pre_special_id == tokenizer.sep_token_id
                segs["text"].append(i)

    all_len = len(token_id_list)

    # position ids
    position_ids = [i for i in segs["cls"]]
    cls_len = len(position_ids)
    for prefix_seg in segs["prefix"]:
        prefix_len = len(prefix_seg["span"])
        position_ids += [i for i in range(cls_len, cls_len + prefix_len)]
        for type_seg in prefix_seg["type"]:
            type_len = len(type_seg["span"])
            position_ids += [i for i in range(cls_len + prefix_len, cls_len + prefix_len + type_len)]

    pre_max_position_id = max(position_ids)
    position_ids += [i for i in range(pre_max_position_id + 1, pre_max_position_id + 1 + len(segs["text"]))]
    assert len(position_ids) == all_len

    # attention mask (2D)
    import numpy as np
    attention_mask_2d = np.reshape(np.array(attention_mask), (all_len, 1)) * np.reshape(np.array(attention_mask), (1, all_len))

    # prefix to prefix attention mask
    for i in range(len(segs["prefix"])):
        for j in range(len(segs["prefix"])):
            if i != j:
                si, sj = segs["prefix"][i]["span"][0], segs["prefix"][j]["span"][0]
                ei, ej = segs["prefix"][i]["type"][-1]["span"][-1], segs["prefix"][j]["type"][-1]["span"][-1]
                attention_mask_2d[si: ei + 1, sj: ej + 1] = 0

    # type to type attention mask
    for i in range(len(segs["prefix"])):
        for j in range(len(segs["prefix"][i]["type"])):
            for k in range(len(segs["prefix"][i]["type"])):
                if j != k:
                    sj, sk = segs["prefix"][i]["type"][j]["span"][0], segs["prefix"][i]["type"][k]["span"][0]
                    ej, ek = segs["prefix"][i]["type"][j]["span"][-1], segs["prefix"][i]["type"][k]["span"][-1]
                    attention_mask_2d[sj: ej + 1, sk: ek + 1] = 0

    return position_ids, attention_mask_2d.tolist()


def split_hint_by_level(level_hint_map: dict) -> tuple[dict, list[str]]:
    """将 level_hint_map 分割为多个 hint"""
    prefix_tuples = list(level_hint_map.keys())

    level_hint_char_map: dict[int, dict] = defaultdict(dict)
    level_hints: list[str] = []
    level_hint = ""
    len_token_level_hint = 2

    for prefix_tuple in prefix_tuples:
        ent_types = list(level_hint_map[prefix_tuple].keys())
        ent_types = sorted(ent_types)

        prefix_string = ",".join([f"{x[0]}: {x[1]}" for x in prefix_tuple]) if prefix_tuple else ""
        len_token_prefix_string = len(tokenizer(prefix_string)["input_ids"]) - 1 if prefix_string else 0

        if len_token_prefix_string > PREFIX_STRING_MAX_LEN:
            continue

        is_first_ent_type = True
        for ent_type in ent_types:
            len_token_ent_type = len(tokenizer(ent_type)["input_ids"]) - 1
            if len_token_ent_type > INFO_TYPE_MAX_LEN:
                continue

            if (is_first_ent_type and len_token_level_hint + len_token_prefix_string + len_token_ent_type > HINT_MAX_LEN) \
                    or (not is_first_ent_type and len_token_level_hint + len_token_ent_type > HINT_MAX_LEN):
                if len(level_hint) > 0:
                    level_hints.append(level_hint)
                level_hint = "[PREFIX]" + prefix_string
                level_hint_char_map[len(level_hints)][(prefix_tuple, ent_type)] = len(level_hint)
                level_hint += f"[TYPE]{ent_type}"
                len_token_level_hint = 2 + len_token_prefix_string + len_token_ent_type
            else:
                if is_first_ent_type:
                    level_hint += "[PREFIX]" + prefix_string
                    level_hint_char_map[len(level_hints)][(prefix_tuple, ent_type)] = len(level_hint)
                    level_hint += f"[TYPE]{ent_type}"
                    len_token_level_hint += len_token_prefix_string + len_token_ent_type
                else:
                    level_hint_char_map[len(level_hints)][(prefix_tuple, ent_type)] = len(level_hint)
                    level_hint += f"[TYPE]{ent_type}"
                    len_token_level_hint += len_token_ent_type
            is_first_ent_type = False

    if len(level_hint) > 0:
        level_hints.append(level_hint)

    return level_hint_char_map, level_hints


def get_legal_output_type_list(schema: dict) -> set:
    """获取合法输出类型列表"""
    def helper(schema, schema_list, prefix):
        if not schema:
            schema_list.append(prefix)
            return
        for k in schema:
            helper(schema[k], schema_list, prefix + [k])

    schema_list: list[list] = []
    helper(schema, schema_list, [])
    return {tuple(x) for x in schema_list}


def infer_info_from_prediction(
    rows: list,
    cols: list,
    input_ids: list,
    token_type_ids: list,
    text: str,
    offset_mapping: list,
    level_split_hint_char_map: dict,
    level_hint_map: dict,
    legal_output_type_list: set
) -> tuple[dict, list]:
    """从预测结果中推断信息"""
    next_level_hint_map: dict = {}
    pred_info_list: list = []

    num_tokens = len(input_ids)
    num_hint_tokens = sum([int(x == 0) for x in token_type_ids])

    # 构建字符索引到 token 索引的映射
    char_index_to_token_index_map: dict[int, int] = {}
    for i in range(num_hint_tokens, num_tokens):
        offset = offset_mapping[i]
        for j in range(offset[0], offset[1]):
            char_index_to_token_index_map[j] = i

    # 构建 hint token 索引映射
    level_split_hint_token_map: dict = {}
    hint_char_index_to_token_index_map: dict[int, int] = {}
    for i in range(num_hint_tokens):
        offset = offset_mapping[i]
        hint_char_index_to_token_index_map[offset[0]] = i

    for x in level_split_hint_char_map:
        level_split_hint_token_map[x] = hint_char_index_to_token_index_map[level_split_hint_char_map[x]]

    token_index_hint_map = {v: k for k, v in level_split_hint_token_map.items()}

    hint_head_map: dict = defaultdict(list)
    hint_tail_map: dict = defaultdict(list)
    spans: list = []

    for j, i in zip(rows, cols):
        if i >= num_hint_tokens and j >= num_hint_tokens and j <= i:
            spans.append((i, j))
        if i < num_hint_tokens and j >= num_hint_tokens:
            if i in token_index_hint_map:
                x = token_index_hint_map[i]
                hint_head_map[x].append(j)
        if i >= num_hint_tokens and j < num_hint_tokens:
            if j in token_index_hint_map:
                x = token_index_hint_map[j]
                hint_tail_map[x].append(i)

    for (i, j) in spans:
        for x in level_split_hint_token_map:
            if j in hint_head_map[x] and i in hint_tail_map[x]:
                try:
                    prefix_tuple, ent_type = x
                    char_head = offset_mapping[j][0]
                    char_tail = offset_mapping[i][1]

                    while char_head < len(text) and text[char_head] == " ":
                        char_head += 1

                    if level_hint_map[prefix_tuple][ent_type]:
                        key = prefix_tuple + ((ent_type, text[char_head: char_tail], tuple([char_head, char_tail])),)
                        next_level_hint_map[key] = level_hint_map[prefix_tuple][ent_type]

                    info = [{"type": tmp[0].strip(), "span": tmp[1], "offset": list(tmp[2])} for tmp in prefix_tuple]
                    info += [
                        {
                            "type": ent_type,
                            "span": text[char_head: char_tail],
                            "offset": [char_head, char_tail]
                        }
                    ]

                    if tuple([tmp["type"] for tmp in info]) in legal_output_type_list:
                        pred_info_list.append(info)
                except Exception:
                    continue

    return next_level_hint_map, pred_info_list


def prompt_loop(
    model,
    text: str,
    level_hint_map: dict,
    pred_info_list: list,
    legal_output_type_list: set
) -> None:
    """递归推理循环"""
    level_hint_char_map, level_hints = split_hint_by_level(level_hint_map)
    next_level_hint_map: dict = {}

    for i, level_hint in enumerate(level_hints):
        level_split_hint_char_map = level_hint_char_map[i]

        tokenized_input = tokenizer(
            level_hint,
            text,
            truncation="only_second",
            max_length=MAX_LEN,
            stride=STRIDE_LEN,
            return_overflowing_tokens=True,
            return_token_type_ids=True,
            return_offsets_mapping=True
        )

        for input_ids, token_type_ids, attention_mask, offset_mapping in zip(
            tokenized_input["input_ids"],
            tokenized_input["token_type_ids"],
            tokenized_input["attention_mask"],
            tokenized_input["offset_mapping"]
        ):
            # 重建 token_type_ids（如果需要）
            if sum(token_type_ids) == 0:
                token_type_ids = []
                pre_token_id = -1
                cur_type_id = 0
                for t in input_ids:
                    if pre_token_id == tokenizer.sep_token_id and t != tokenizer.sep_token_id:
                        cur_type_id = 1
                    token_type_ids.append(cur_type_id)
                    pre_token_id = t

            position_ids, attn_mask = build_position_ids_attn_mask(input_ids, token_type_ids, attention_mask)

            # 准备输入
            batch_data = [
                torch.tensor([input_ids], dtype=torch.long, device=device),
                torch.tensor([attn_mask], dtype=torch.long, device=device),
                torch.tensor([token_type_ids], dtype=torch.long, device=device),
                torch.tensor([position_ids], dtype=torch.long, device=device),
            ]

            # 模型推理
            with torch.no_grad():
                output = model(*batch_data)

            _, rows, cols = output["logits"]
            rows = rows.tolist()
            cols = cols.tolist()

            next_level_hint_map_, new_preds = infer_info_from_prediction(
                rows, cols,
                input_ids,
                token_type_ids,
                text,
                offset_mapping,
                level_split_hint_char_map,
                level_hint_map,
                legal_output_type_list
            )

            next_level_hint_map.update(next_level_hint_map_)
            pred_info_list.extend(new_preds)

    # 递归处理下一层级
    if len(next_level_hint_map) == 0:
        return

    prompt_loop(model, text, next_level_hint_map, pred_info_list, legal_output_type_list)


def inference(text: str, schema: dict) -> list:
    """执行 NLU 推理

    Args:
        text: 输入文本
        schema: 结构化 schema，如 {"人物": null, "地理位置": null}
                或嵌套结构 {"人物": {"出生地": null}}

    Returns:
        抽取的信息列表，如 [
            [{"type": "人物", "span": "马云", "offset": [0, 2]}],
            [{"type": "地理位置", "span": "杭州", "offset": [4, 6]}]
        ]
    """
    model, _ = load_model()

    legal_output_type_list = get_legal_output_type_list(schema)
    pred_info_list: list = []

    # 初始化 level_hint_map
    level_hint_map: dict = {(): schema}

    # 执行递归推理
    prompt_loop(model, text, level_hint_map, pred_info_list, legal_output_type_list)

    return pred_info_list


# ============== FastAPI 模型 ==============


class InferenceRequest(BaseModel):
    """推理请求"""
    input: str = Field(..., description="输入文本")
    extraction_schema: dict = Field(..., description="抽取 schema")


class InferenceResponse(BaseModel):
    """推理响应"""
    output: list = Field(..., description="抽取结果")
    model: str
    usage: dict


class NERRequest(BaseModel):
    """NER 请求"""
    text: str = Field(..., description="输入文本")
    entity_types: list[str] = Field(..., description="实体类型列表")


class ClassifyRequest(BaseModel):
    """分类请求"""
    text: str = Field(..., description="输入文本")
    labels: list[str] = Field(..., description="标签列表")


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    object: str = "model"
    owned_by: str = "Alibaba"


class ModelList(BaseModel):
    """模型列表"""
    object: str = "list"
    data: list[ModelInfo]


# ============== FastAPI 应用 ==============

app = FastAPI(
    title="NLU Server (RexUniNLU)",
    description="通用自然语言理解服务",
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
        "message": "NLU Server (RexUniNLU)",
        "model": NLU_MODEL_NAME,
        "model_path": NLU_MODEL_PATH,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查"""
    return {"status": "ok", "model": NLU_MODEL_NAME}


@app.get("/v1/models", response_model=ModelList)
def list_models() -> ModelList:
    """列出可用模型"""
    return ModelList(
        object="list",
        data=[ModelInfo(id=NLU_MODEL_NAME, owned_by="Alibaba")]
    )


@app.post("/v1/inference", response_model=InferenceResponse)
def do_inference(request: InferenceRequest) -> InferenceResponse:
    """通用推理接口

    支持多种 NLU 任务：
    - NER: schema = {"人物": null, "地理位置": null}
    - 关系抽取: schema = {"人物": {"出生地": null}}
    - 事件抽取: schema = {"事件类型": {"触发词": null, "论元": null}}
    """
    if not request.input:
        raise HTTPException(status_code=400, detail="input cannot be empty")

    if not request.extraction_schema:
        raise HTTPException(status_code=400, detail="schema cannot be empty")

    print(f"[NLU] 推理请求: {request.input[:50]}...")
    start_time = time.time()

    result = inference(request.input, request.extraction_schema)

    elapsed = time.time() - start_time
    print(f"[NLU] 完成，耗时 {elapsed:.2f}s，抽取 {len(result)} 个结果")

    return InferenceResponse(
        output=result,
        model=NLU_MODEL_NAME,
        usage={
            "prompt_tokens": len(request.input),
            "total_tokens": len(request.input),
        }
    )


@app.post("/v1/ner")
def do_ner(request: NERRequest) -> dict:
    """命名实体识别

    便捷接口，自动构建 schema
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    if not request.entity_types:
        raise HTTPException(status_code=400, detail="entity_types cannot be empty")

    # 构建 schema
    schema = {entity_type: None for entity_type in request.entity_types}

    print(f"[NER] 实体识别: {request.text[:50]}...")
    start_time = time.time()

    result = inference(request.text, schema)

    elapsed = time.time() - start_time
    print(f"[NER] 完成，耗时 {elapsed:.2f}s，抽取 {len(result)} 个实体")

    return {
        "text": request.text,
        "entities": result,
        "model": NLU_MODEL_NAME,
    }


@app.post("/v1/classify")
def do_classify(request: ClassifyRequest) -> dict:
    """文本分类

    将文本分类到给定的标签中
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    if not request.labels:
        raise HTTPException(status_code=400, detail="labels cannot be empty")

    # 构建 schema（分类任务使用特殊格式）
    # 使用 [CLASSIFY] token 进行分类
    text_with_cls = "[CLASSIFY]" + request.text
    schema = {label: None for label in request.labels}

    print(f"[Classify] 文本分类: {request.text[:50]}...")
    start_time = time.time()

    result = inference(text_with_cls, schema)

    elapsed = time.time() - start_time
    print(f"[Classify] 完成，耗时 {elapsed:.2f}s")

    # 解析分类结果
    predicted_label = None
    if result:
        # 取置信度最高的
        predicted_label = result[0][0]["type"] if result[0] else None

    return {
        "text": request.text,
        "labels": request.labels,
        "predicted_label": predicted_label,
        "all_predictions": result,
        "model": NLU_MODEL_NAME,
    }


@app.post("/v1/extract")
def do_extract(request: InferenceRequest) -> dict:
    """通用抽取接口

    与 /v1/inference 相同，但返回格式略有不同
    """
    result = inference(request.input, request.extraction_schema)

    return {
        "text": request.input,
        "schema": request.extraction_schema,
        "extractions": result,
        "model": NLU_MODEL_NAME,
    }


def warmup() -> None:
    """预热模型"""
    print("🔥 预热模型...")
    model, _ = load_model()

    # 执行一次简单推理
    inference("测试文本", {"测试": None})
    print("✅ 预热完成\n")


def main() -> None:
    print("\n" + "=" * 60)
    print("NLU 服务 (RexUniNLU)")
    print("=" * 60)
    print(f"模型: {NLU_MODEL_NAME}")
    print(f"路径: {NLU_MODEL_PATH}")
    print(f"地址: http://{HOST}:{PORT}")
    print("=" * 60 + "\n")

    # 启动前加载模型并预热
    load_model()
    warmup()

    print(f"🚀 NLU 服务已启动: http://{HOST}:{PORT}")
    print(f"   API: POST http://{HOST}:{PORT}/v1/inference")
    print(f"   NER: POST http://{HOST}:{PORT}/v1/ner")
    print(f"   分类: POST http://{HOST}:{PORT}/v1/classify\n")

    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
