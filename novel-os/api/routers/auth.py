"""本地单用户认证（基于标准库实现 JWT，无需额外依赖）。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

router = APIRouter()

# 凭证与密钥优先从环境变量读取，未配置时使用本地开发默认值
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

_USERNAME = os.environ.get("NOVEL_OS_USERNAME", DEFAULT_USERNAME)
_PASSWORD = os.environ.get("NOVEL_OS_PASSWORD", DEFAULT_PASSWORD)
_SECRET_KEY = os.environ.get("NOVEL_OS_SECRET_KEY", "novel-os-local-dev-secret-key")

_TOKEN_LIFETIME_SECONDS = 7 * 24 * 3600  # 7 天

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    username: str


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _create_token(username: str) -> str:
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    now = int(time.time())
    payload = _base64url_encode(
        json.dumps(
            {"sub": username, "iat": now, "exp": now + _TOKEN_LIFETIME_SECONDS},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("utf-8")
    signature = hmac.new(_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def _verify_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()

    try:
        actual_sig = _base64url_decode(signature_b64)
    except Exception as exc:
        raise ValueError("Invalid signature encoding") from exc

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid signature")

    payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")

    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = _verify_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    username = payload.get("sub")
    if not isinstance(username, str) or username != _USERNAME:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    return CurrentUser(username=username)


@router.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "") or _USERNAME
    # 本地开发模式：不校验密码，任意输入均可登录
    _ = body.get("password", "")

    return {
        "code": 200,
        "data": {
            "access_token": _create_token(username),
            "token_type": "bearer",
            "username": username,
        },
    }


@router.get("/auth/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return {"code": 200, "data": {"username": current_user.username}}
