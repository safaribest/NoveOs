#!/usr/bin/env python3
"""验证 Novel-OS DeepSeek API 集成配置。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm_client import LLMClient, LLMConfig

# 测试1: 验证默认配置
cfg = LLMConfig()
print("=== Default Config ===")
print(f"model: {cfg.model}")
print(f"api_base: {cfg.api_base}")
print(f"thinking_enabled: {cfg.thinking_enabled}")
assert cfg.model == "deepseek-v4-pro"
assert cfg.api_base == "https://api.deepseek.com/v1"
assert cfg.thinking_enabled == False

# 测试2: 验证 Agent 策略
print()
print("=== Agent Model Strategy ===")
for agent, strategy in LLMClient.AGENT_MODEL_STRATEGY.items():
    thinking = strategy.get("thinking_enabled", False)
    print(f"{agent:20s} -> model={strategy['model']}, thinking={thinking}")

assert LLMClient.AGENT_MODEL_STRATEGY["scene_writer"]["thinking_enabled"] == True
assert LLMClient.AGENT_MODEL_STRATEGY["hook_engineer"]["thinking_enabled"] == True
assert LLMClient.AGENT_MODEL_STRATEGY["director"]["thinking_enabled"] == False
assert LLMClient.AGENT_MODEL_STRATEGY["beat_planner"]["thinking_enabled"] == False
assert LLMClient.AGENT_MODEL_STRATEGY["dialogue_tuner"]["thinking_enabled"] == False
assert LLMClient.AGENT_MODEL_STRATEGY["polish"]["thinking_enabled"] == False
assert LLMClient.AGENT_MODEL_STRATEGY["auditor"]["thinking_enabled"] == False

# 测试3: 验证环境变量覆盖
# 从环境变量读取 API key（测试时设置）
TEST_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
if not TEST_API_KEY:
    raise EnvironmentError("测试需要设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量")

os.environ["OPENAI_API_KEY"] = TEST_API_KEY
os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com/v1"
os.environ["LLM_MODEL"] = "deepseek-v4-pro"

cfg2 = LLMConfig.from_env()
print()
print("=== Env Config ===")
print(f"api_key: {cfg2.api_key[:10]}...")
print(f"api_base: {cfg2.api_base}")
print(f"model: {cfg2.model}")
assert cfg2.api_key == TEST_API_KEY
assert cfg2.api_base == "https://api.deepseek.com/v1"
assert cfg2.model == "deepseek-v4-pro"

# 测试4: 验证 thinking 参数构造
print()
print("=== Thinking Extra Body Test ===")
client = LLMClient(cfg2)
# 使用内置策略构建 agent_configs
built_in_strategy = LLMClient.AGENT_MODEL_STRATEGY
merged_agent_cfgs = {}
for agent_name, strategy in built_in_strategy.items():
    merged_agent_cfgs[agent_name] = dict(strategy)
    merged_agent_cfgs[agent_name].setdefault("api_key", cfg2.api_key)
    merged_agent_cfgs[agent_name].setdefault("api_base", cfg2.api_base)

client = LLMClient(cfg2, agent_configs=merged_agent_cfgs)

for agent_name in ["scene_writer", "hook_engineer", "director"]:
    agent_cfg = client.agent_configs.get(agent_name)
    if agent_cfg:
        extra_body = None
        if agent_cfg.thinking_enabled and agent_cfg.model.startswith("deepseek-v4"):
            extra_body = {"thinking": {"type": "enabled"}, "reasoning_effort": agent_cfg.reasoning_effort}
        print(f"{agent_name:20s} -> extra_body={extra_body}")
        if agent_name in ("scene_writer", "hook_engineer"):
            assert extra_body is not None
            assert extra_body["thinking"]["type"] == "enabled"
        else:
            assert extra_body is None

print()
print("All tests passed!")
