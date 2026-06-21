import { get, post, put } from "@/lib/api";
import type { LLMProvider, LLMSettings, TestConnectionResult } from "@/types";

export async function getLLMSettings(): Promise<LLMSettings> {
  return get<LLMSettings>("/settings/llm");
}

export async function updateLLMSettings(settings: LLMSettings): Promise<LLMSettings> {
  return put<LLMSettings>("/settings/llm", settings);
}

export async function testLLMConnection(providerName: string): Promise<TestConnectionResult> {
  return post<TestConnectionResult>("/settings/llm/test", { provider_name: providerName });
}

export function providerTypeOptions() {
  return [
    { value: "deepseek", label: "DeepSeek" },
    { value: "openai", label: "OpenAI" },
    { value: "kimi", label: "Moonshot (Kimi)" },
    { value: "custom", label: "自定义 OpenAI-compatible" },
  ];
}

export async function getAgentProviders(): Promise<Record<string, string>> {
  const response = await get<{ agent_providers: Record<string, string> }>("/settings/llm/agents");
  return response.agent_providers;
}

export async function updateAgentProviders(agentProviders: Record<string, string>): Promise<Record<string, string>> {
  const response = await put<{ agent_providers: Record<string, string> }>("/settings/llm/agents", { agent_providers: agentProviders });
  return response.agent_providers;
}

export function getProviderDefaults(type: string): Partial<LLMProvider> {
  switch (type) {
    case "deepseek":
      return {
        base_url: "https://api.deepseek.com/v1",
        model: "deepseek-chat",
      };
    case "openai":
      return {
        base_url: "https://api.openai.com/v1",
        model: "gpt-4o-mini",
      };
    case "kimi":
      return {
        base_url: "https://api.moonshot.cn/v1",
        model: "kimi-latest",
      };
    default:
      return {
        base_url: "",
        model: "",
      };
  }
}
