#!/usr/bin/env python3
"""本地代理：让 Claude Code 走 DeepSeek API。"""

import json
import logging
import os
import socket
import sys
import uuid
from urllib.parse import urljoin

import requests
from flask import Flask, Response, request


# ==================== 配置 ====================
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# Anthropic 模型 ID -> DeepSeek 模型 ID
# ID 保持 claude-* 格式以兼容 Claude Code 插件的模型校验，
# display_name 则显示为直观的 DeepSeek 模型名。
MODEL_MAP = {
    "claude-sonnet-4-0": "deepseek-chat",
    "claude-3-5-haiku-20241022": "deepseek-chat",
}

# /v1/models 里暴露的 Anthropic 格式模型列表
ANTHROPIC_MODELS = [
    {
        "type": "model",
        "id": "claude-sonnet-4-0",
        "display_name": "DeepSeek Chat (Sonnet proxy)",
        "created_at": "2024-01-01T00:00:00Z",
    },
    {
        "type": "model",
        "id": "claude-3-5-haiku-20241022",
        "display_name": "DeepSeek Chat (Haiku proxy)",
        "created_at": "2024-01-01T00:00:00Z",
    },
]


app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("deepseek_proxy")


def get_free_port(start=8964):
    """找一个可用端口。"""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port found")


def map_model(anthropic_model: str) -> str:
    """把 Anthropic 模型 ID 映射为 DeepSeek 模型 ID。"""
    if anthropic_model in MODEL_MAP:
        return MODEL_MAP[anthropic_model]
    if anthropic_model.startswith("deepseek-"):
        return anthropic_model
    logger.warning("Unknown model '%s', fallback to deepseek-chat", anthropic_model)
    return "deepseek-chat"


def forward_headers(incoming_headers):
    """挑选需要转发给上游的 header。"""
    out = {}
    for key, value in incoming_headers.items():
        lower = key.lower()
        if lower in ("host", "content-length", "connection", "accept-encoding"):
            continue
        out[key] = value
    if "Authorization" not in out and "authorization" not in {k.lower() for k in out} and DEEPSEEK_API_KEY:
        out["Authorization"] = f"Bearer {DEEPSEEK_API_KEY}"
    return out



def flatten_content(content) -> str:
    """把 Anthropic 的 content blocks 拼成字符串。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "image":
                    parts.append("[image]")
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return ""


def convert_tool(tool: dict) -> dict:
    """Anthropic 工具定义 -> OpenAI 工具定义。"""
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        },
    }


def convert_tool_choice(tool_choice):
    """Anthropic tool_choice -> OpenAI tool_choice。"""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        if tool_choice in ("auto", "none", "required"):
            return tool_choice
        return "auto"
    if isinstance(tool_choice, dict):
        t = tool_choice.get("type")
        name = tool_choice.get("name")
        if t == "tool" and name:
            return {"type": "function", "function": {"name": name}}
        if t == "auto":
            return "auto"
        if t == "any":
            return "required"
        if t == "none":
            return "none"
    return "auto"


def convert_messages(messages: list, system_text: str = None) -> list:
    """Anthropic 消息列表 -> OpenAI 消息列表。"""
    openai_messages = []

    if system_text:
        openai_messages.append({"role": "system", "content": system_text})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            if isinstance(content, list):
                tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                if len(tool_results) == len(content) and tool_results:
                    for block in tool_results:
                        openai_messages.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": flatten_content(block.get("content", "")),
                        })
                    continue
            openai_messages.append({"role": "user", "content": flatten_content(content)})

        elif role == "assistant":
            if isinstance(content, list):
                tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                if tool_uses:
                    openai_messages.append({
                        "role": "assistant",
                        "content": "\n".join(text_parts) if text_parts else "",
                        "tool_calls": [
                            {
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(block.get("input", {})),
                                },
                            }
                            for block in tool_uses
                        ],
                    })
                    continue
            openai_messages.append({"role": "assistant", "content": flatten_content(content)})

        elif role == "system":
            openai_messages.append({"role": "system", "content": flatten_content(content)})

        else:
            openai_messages.append(msg)

    return openai_messages



def convert_request_body(data: dict) -> dict:
    """把 Claude Code 发来的 Anthropic 请求体转成 DeepSeek 可接受的 OpenAI 格式。"""
    out = {}

    # model 映射
    out["model"] = map_model(data.get("model", ""))

    # system 字段转到 messages 前面
    system_text = None
    system = data.get("system")
    if system:
        if isinstance(system, str):
            system_text = system
        elif isinstance(system, list):
            system_text = "\n".join(b.get("text", "") for b in system if isinstance(b, dict) and b.get("type") == "text")

    # 转换消息
    messages = data.get("messages", [])
    out["messages"] = convert_messages(messages, system_text)

    # 转换工具
    tools = data.get("tools")
    if tools:
        out["tools"] = [convert_tool(t) for t in tools]

    # 转换 tool_choice
    tool_choice = data.get("tool_choice")
    converted_tc = convert_tool_choice(tool_choice)
    if converted_tc is not None:
        out["tool_choice"] = converted_tc

    # 其他 Anthropic 参数映射
    if "max_tokens" in data:
        out["max_tokens"] = data["max_tokens"]
    if "temperature" in data:
        out["temperature"] = data["temperature"]
    if "top_p" in data:
        out["top_p"] = data["top_p"]
    if "stop_sequences" in data:
        out["stop"] = data["stop_sequences"]
    if "stream" in data:
        out["stream"] = data["stream"]

    return out



def make_anthropic_id() -> str:
    return "msg_" + uuid.uuid4().hex[:24]


def convert_non_streaming_response(openai_resp: dict, anthropic_model: str) -> dict:
    """把 DeepSeek 非流式 OpenAI 响应转成 Anthropic message 响应。"""
    choice = openai_resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    content_blocks = []

    text = message.get("content") or ""
    if text:
        content_blocks.append({"type": "text", "text": text})

    tool_calls = message.get("tool_calls") or []
    for tc in tool_calls:
        fn = tc.get("function", {})
        try:
            input_json = json.loads(fn.get("arguments", "{}"))
        except Exception:
            input_json = {}
        content_blocks.append({
            "type": "tool_use",
            "id": tc.get("id", "toolu_" + uuid.uuid4().hex[:24]),
            "name": fn.get("name", ""),
            "input": input_json,
        })

    finish_reason = choice.get("finish_reason")
    if finish_reason == "tool_calls" or tool_calls:
        stop_reason = "tool_use"
    elif finish_reason == "stop":
        stop_reason = "end_turn"
    else:
        stop_reason = None

    usage = openai_resp.get("usage", {})
    return {
        "id": openai_resp.get("id", make_anthropic_id()),
        "type": "message",
        "role": "assistant",
        "model": anthropic_model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }



def convert_streaming_response(openai_stream_iter, anthropic_model: str):
    """
    把 DeepSeek 的 OpenAI SSE 流转成 Anthropic SSE 流。
    这是一个 generator，yield 形如 (event, data_dict) 的元组。
    """
    message_id = make_anthropic_id()
    current_tool_index = None
    current_tool_id = None
    current_tool_name = None
    current_tool_args = ""
    text_block_started = False
    text_content = ""
    output_tokens = 0

    # message_start
    yield "message_start", {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "model": anthropic_model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    }

    for raw_line in openai_stream_iter:
        if not raw_line:
            continue
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        line = line.strip()
        if line.startswith("data: "):
            data_str = line[len("data: "):]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choice = chunk.get("choices", [{}])[0]
            delta = choice.get("delta", {})

            # 文本增量
            delta_text = delta.get("content") or ""
            if delta_text:
                if not text_block_started:
                    text_block_started = True
                    yield "content_block_start", {
                        "type": "content_block_start",
                        "index": 0,
                        "content_block": {"type": "text", "text": ""},
                    }
                text_content += delta_text
                output_tokens += 1
                yield "content_block_delta", {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": delta_text},
                }

            # tool_calls 增量
            delta_tool_calls = delta.get("tool_calls") or []
            for tc in delta_tool_calls:
                idx = tc.get("index", 0)
                fn = tc.get("function", {})

                if current_tool_index is None or idx != current_tool_index:
                    # 结束上一个 tool 的 arguments 收集
                    if current_tool_id is not None:
                        try:
                            input_json = json.loads(current_tool_args)
                        except Exception:
                            input_json = {}
                        yield "content_block_stop", {
                            "type": "content_block_stop",
                            "index": current_tool_index + (1 if text_block_started else 0),
                        }

                    current_tool_index = idx
                    current_tool_id = tc.get("id") or ("toolu_" + uuid.uuid4().hex[:24])
                    current_tool_name = fn.get("name", "")
                    current_tool_args = ""

                    block_index = idx + (1 if text_block_started else 0)
                    yield "content_block_start", {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": {
                            "type": "tool_use",
                            "id": current_tool_id,
                            "name": current_tool_name,
                            "input": {},
                        },
                    }

                if fn.get("arguments"):
                    current_tool_args += fn["arguments"]
                    block_index = idx + (1 if text_block_started else 0)
                    output_tokens += 1
                    yield "content_block_delta", {
                        "type": "content_block_delta",
                        "index": block_index,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": fn["arguments"],
                        },
                    }

    # 结束最后一个 tool block
    if current_tool_id is not None:
        yield "content_block_stop", {
            "type": "content_block_stop",
            "index": current_tool_index + (1 if text_block_started else 0),
        }

    # 结束 text block
    if text_block_started:
        yield "content_block_stop", {"type": "content_block_stop", "index": 0}

    stop_reason = "end_turn" if current_tool_id is None else "tool_use"
    yield "message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    }
    yield "message_stop", {"type": "message_stop"}



@app.route("/v1/models", methods=["GET"])
def list_models():
    """返回 Anthropic 格式的模型列表，骗过 Claude Code 的模型校验。"""
    logger.info("GET /v1/models")
    return Response(
        json.dumps({"data": ANTHROPIC_MODELS, "object": "list"}),
        status=200,
        mimetype="application/json",
    )


@app.route("/v1/messages", methods=["POST"])
def create_message():
    """转发 messages 请求，并完成 Anthropic <-> OpenAI 双向转换。"""
    data = request.get_json(force=True, silent=True) or {}
    original_model = data.get("model", "")
    stream = data.get("stream", False)

    converted = convert_request_body(data)
    deepseek_model = converted.get("model")
    logger.info(
        "POST /v1/messages (anthropic_model=%s, deepseek_model=%s, stream=%s, tools=%d)",
        original_model,
        deepseek_model,
        stream,
        len(converted.get("tools", [])),
    )

    upstream_url = urljoin(DEEPSEEK_BASE_URL, "/v1/chat/completions")
    headers = forward_headers(request.headers)

    try:
        resp = requests.post(
            upstream_url,
            headers=headers,
            json=converted,
            stream=True,
            timeout=300,
        )
    except requests.RequestException as e:
        logger.error("Upstream request failed: %s", e)
        return Response(
            json.dumps({"error": {"type": "proxy_error", "message": str(e)}}),
            status=502,
            mimetype="application/json",
        )

    if stream:
        def generate_sse():
            for event, payload in convert_streaming_response(resp.iter_lines(), original_model):
                yield f"event: {event}\ndata: {json.dumps(payload)}\n\n"

        return Response(
            generate_sse(),
            status=resp.status_code,
            mimetype="text/event-stream",
        )
    else:
        try:
            openai_resp = resp.json()
        except Exception as e:
            logger.error("Failed to parse upstream JSON: %s", e)
            return Response(
                json.dumps({"error": {"type": "proxy_error", "message": "invalid upstream response"}}),
                status=502,
                mimetype="application/json",
            )
        anthropic_resp = convert_non_streaming_response(openai_resp, original_model)
        return Response(
            json.dumps(anthropic_resp),
            status=resp.status_code,
            mimetype="application/json",
        )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "proxy": "deepseek", "upstream": DEEPSEEK_BASE_URL}


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    """其他请求直接透传给 DeepSeek（保留 method、body、header）。"""
    upstream_url = urljoin(DEEPSEEK_BASE_URL, request.path)
    if request.query_string:
        upstream_url += "?" + request.query_string.decode("utf-8")

    logger.info("%s %s -> %s", request.method, request.path, upstream_url)

    try:
        resp = requests.request(
            method=request.method,
            url=upstream_url,
            headers=forward_headers(request.headers),
            data=request.get_data(),
            stream=True,
            timeout=300,
        )
    except requests.RequestException as e:
        logger.error("Upstream request failed: %s", e)
        return Response(
            json.dumps({"error": {"type": "proxy_error", "message": str(e)}}),
            status=502,
            mimetype="application/json",
        )

    def generate():
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return Response(
        generate(),
        status=resp.status_code,
        headers={
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in ("content-encoding", "transfer-encoding", "content-length", "connection")
        },
        mimetype=resp.headers.get("content-type", "application/json"),
    )


def main():
    port = int(os.environ.get("DEEPSEEK_PROXY_PORT", "3456"))
    logger.info("Starting DeepSeek proxy on http://127.0.0.1:%s", port)
    logger.info("Upstream: %s", DEEPSEEK_BASE_URL)
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()
