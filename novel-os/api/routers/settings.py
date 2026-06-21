"""系统设置 API：LLM Provider 配置管理。"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.llm_settings_client import (
    LLMSettingsClient,
    LLMProviderError,
    load_llm_settings,
    save_llm_settings,
    get_agent_providers,
    save_agent_providers,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class LLMProviderConfig(BaseModel):
    """单个 LLM Provider 配置。"""

    name: str = Field(..., min_length=1, description="Provider 唯一标识")
    type: str = Field(default="custom", description="Provider 类型")
    api_key: str = Field(..., min_length=1, description="API Key")
    base_url: str = Field(..., min_length=1, description="API Base URL")
    model: str = Field(..., min_length=1, description="模型名称")
    temperature: float = Field(default=0.8, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)
    timeout: int = Field(default=120, ge=5, le=600)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")
        return v.rstrip("/")


class LLMSettingsPayload(BaseModel):
    """LLM 设置请求体。"""

    default_provider: str = Field(default="", description="默认 provider 名称")
    providers: dict[str, LLMProviderConfig] = Field(default_factory=dict)


class LLMSettingsResponse(BaseModel):
    """LLM 设置响应。"""

    default_provider: str
    providers: dict[str, dict[str, Any]]


class TestConnectionPayload(BaseModel):
    """测试连接请求体。"""

    provider_name: str = Field(..., description="要测试的 provider 名称")


class TestConnectionResponse(BaseModel):
    """测试连接响应。"""

    success: bool
    message: str
    latency_ms: float | None = None
    model: str | None = None




@router.get("/llm")
async def get_llm_settings() -> dict[str, Any]:
    """获取当前 LLM 配置。"""
    config = load_llm_settings()
    return {
        "code": 200,
        "data": LLMSettingsResponse(
            default_provider=config.get("default_provider", ""),
            providers=config.get("providers", {}),
        ),
    }


@router.put("/llm")
async def update_llm_settings(payload: LLMSettingsPayload) -> dict[str, Any]:
    """更新 LLM 配置。"""
    if payload.default_provider and payload.default_provider not in payload.providers:
        raise HTTPException(
            status_code=400,
            detail=f"默认 provider '{payload.default_provider}' 不在 providers 列表中",
        )

    providers: dict[str, dict[str, Any]] = {}
    for name, provider in payload.providers.items():
        providers[name] = {
            "name": name,
            "type": provider.type,
            "api_key": provider.api_key,
            "base_url": provider.base_url,
            "model": provider.model,
            "temperature": provider.temperature,
            "max_tokens": provider.max_tokens,
            "timeout": provider.timeout,
        }

    config = {
        "default_provider": payload.default_provider,
        "providers": providers,
    }
    save_llm_settings(config)

    # 刷新全局客户端缓存
    LLMSettingsClient().reload()

    return {
        "code": 200,
        "data": LLMSettingsResponse(
            default_provider=payload.default_provider,
            providers=providers,
        ),
    }


@router.post("/llm/test")
async def test_llm_connection(payload: TestConnectionPayload) -> dict[str, Any]:
    """测试指定 provider 的连通性。"""
    try:
        client = LLMSettingsClient()
        result = client.test_connection(payload.provider_name)
        return {"code": 200, "data": TestConnectionResponse(**result)}
    except LLMProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"测试失败: {exc}") from exc


class AgentProviderPayload(BaseModel):
    """Agent → Provider 分配请求体。"""
    agent_providers: dict[str, str] = Field(default_factory=dict)


@router.get("/llm/agents")
async def get_agent_providers_handler() -> dict[str, Any]:
    """获取 Agent → Provider 分配映射。"""
    return {"code": 200, "data": AgentProviderPayload(agent_providers=get_agent_providers())}


@router.put("/llm/agents")
async def update_agent_providers_handler(payload: AgentProviderPayload) -> dict[str, Any]:
    """更新 Agent → Provider 分配映射。"""
    settings = load_llm_settings()
    providers = settings.get("providers", {})
    for agent_name, provider_name in payload.agent_providers.items():
        if provider_name and provider_name not in providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider_name}'（Agent '{agent_name}'）不存在",
            )
    save_agent_providers(payload.agent_providers)
    return {"code": 200, "data": AgentProviderPayload(agent_providers=get_agent_providers())}
