#!/usr/bin/env python3
"""
本地代理：让 Claude Code / Claude Code for VSCode 走 Agnes AI。

Claude Code 启动时会调用 /v1/models 校验模型名，但 Agnes 返回的是 OpenAI 格式列表，
Claude Code 无法识别，导致报 "selected model ... may not exist"。

本代理：
1. /v1/models 返回 Anthropic 格式的模型列表（模型名使用 Anthropic ID）。
2. /v1/messages 收到 Claude Code 发来的 Anthropic 格式请求后，把消息和工具定义
   转成 Agnes 能接受的 OpenAI 兼容格式，再转发给 Agnes 的 /v1/messages。
   Agnes 会返回 Anthropic 格式响应，我们原样返回给 Claude Code。
"""

import json
import logging
import os
import socket
import sys
from urllib.parse import urljoin

import requests
from flask import Flask, Response, request

# ==================== 配置 ====================
AGNES_BASE_URL = os.environ.get("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")

# Anthropic 模型 ID -> Agnes 模型 ID
MODEL_MAP = {
    "claude-sonnet-4-6": "agnes-2.0-flash",
    "claude-sonnet-4-5": "agnes-2.0-flash",
    "claude-opus-4-6": "agnes-2.0-flash",
    "claude-opus-4-5": "agnes-2.0-flash",
    "claude-haiku-4": "agnes-2.0-flash",
    "claude-sonnet-4": "agnes-2.0-flash",
    "claude-opus-4": "agnes-2.0-flash",
    "sonnet": "agnes-2.0-flash",
    "opus": "agnes-2.0-flash",
    "haiku": "agnes-2.0-flash",
}

# /v1/models 里暴露的 Anthropic 格式模型列表
ANTHROPIC_MODELS = [
    {
        "type": "model",
        "id": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6 (Agnes)",
        "created_at": "2024-01-01T00:00:00Z",
    },
    {
        "type": "model",
        "id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6 (Agnes)",
        "created_at": "2024-01-01T00:00:00Z",
    },
    {
        "type": "model",
        "id": "claude-haiku-4",
        "display_name": "Claude Haiku 4 (Agnes)",
        "created_at": "2024-01-01T00:00:00Z",
    },
]

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("agnes_proxy")


def get_free_port(start=8964):
    """找一个可用端口。"""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port found")


def map_model(anthropic_model: str) -> str:
    """把 Anthropic 模型 ID 映射为 Agnes 模型 ID。"""
    if anthropic_model in MODEL_MAP:
        return MODEL_MAP[anthropic_model]
    if anthropic_model.startswith("agnes-"):
        return anthropic_model
    logger.warning("Unknown model '%s', fallback to agnes-2.0-flash", anthropic_model)
    return "agnes-2.0-flash"


def forward_headers(incoming_headers):
    """挑选需要转发给上游的 header。"""
    out = {}
    for key, value in incoming_headers.items():
        lower = key.lower()
        if lower in ("host", "content-length", "connection", "accept-encoding"):
            continue
        out[key] = value
    if "Authorization" not in out and "authorization" not in {k.lower() for k in out} and AGNES_API_KEY:
        out["Authorization"] = f"Bearer {AGNES_API_KEY}"
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
                    # 图片暂时用占位符，OpenAI 图片格式不同
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
                # 检查是否全是 tool_result
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
    """把 Claude Code 发来的 Anthropic 请求体转成 Agnes 能接受的格式。"""
    out = dict(data)

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
        out.pop("system", None)

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

    # 删除 Agnes 不认识的字段 / 不支持的参数
    for key in list(out.keys()):
        if key.startswith("anthropic-") or key in (
            "metadata",
            "thinking",
            "context_management",
        ):
            out.pop(key, None)

    return out


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
    """转发 messages 请求，并把 Anthropic 格式转成 Agnes 可接受的 OpenAI 兼容格式。"""
    data = request.get_json(force=True, silent=True) or {}
    original_model = data.get("model", "")

    converted = convert_request_body(data)
    logger.info(
        "POST /v1/messages (anthropic_model=%s, agnes_model=%s, tools=%d)",
        original_model,
        converted.get("model"),
        len(converted.get("tools", [])),
    )

    upstream_url = urljoin(AGNES_BASE_URL, "/v1/messages")
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

    def generate():
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    response_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length", "connection")
    }
    return Response(
        generate(),
        status=resp.status_code,
        headers=response_headers,
        mimetype=resp.headers.get("content-type", "application/json"),
    )


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "proxy": "agnes", "upstream": AGNES_BASE_URL}


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    """其他请求直接透传给 Agnes（保留 method、body、header）。"""
    upstream_url = urljoin(AGNES_BASE_URL, request.path)
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
    port = int(os.environ.get("AGNES_PROXY_PORT", get_free_port()))
    logger.info("Starting Agnes proxy on http://127.0.0.1:%s", port)
    logger.info("Upstream: %s", AGNES_BASE_URL)
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()
