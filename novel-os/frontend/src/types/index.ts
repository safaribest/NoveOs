export type ProviderType = "deepseek" | "openai" | "kimi" | "custom";

export interface LLMProvider {
  name: string;
  type: ProviderType;
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout: number;
}

export interface LLMSettings {
  default_provider: string;
  providers: Record<string, LLMProvider>;
}

export interface TestConnectionResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface Project {
  project_id: string;
  name: string;
  genre: string;
  platform: string;
  status: string;
  current_chapter: number;
  total_chapters: number;
  created_at: string;
}

export interface NavItem {
  label: string;
  href: string;
  icon: string;
}
