import { ProviderCard } from "./provider-card";
import type { LLMProvider } from "@/types";

interface ProviderListProps {
  providers: LLMProvider[];
  defaultProvider: string;
  onSetDefault: (name: string) => void;
  onEdit: (provider: LLMProvider) => void;
  onDelete: (name: string) => void;
  onTest: (name: string) => void;
  testingProvider: string | null;
  testResults: Record<string, { success: boolean; message: string; latency_ms?: number }>;
}

export function ProviderList({
  providers,
  defaultProvider,
  onSetDefault,
  onEdit,
  onDelete,
  onTest,
  testingProvider,
  testResults,
}: ProviderListProps) {
  if (providers.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border bg-card/50 p-12 text-center">
        <p className="text-muted-foreground">还没有配置任何 LLM Provider</p>
        <p className="mt-1 text-sm text-muted-foreground">点击下方按钮添加第一个</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {providers.map((provider) => (
        <ProviderCard
          key={provider.name}
          provider={provider}
          isDefault={defaultProvider === provider.name}
          onSetDefault={() => onSetDefault(provider.name)}
          onEdit={() => onEdit(provider)}
          onDelete={() => onDelete(provider.name)}
          onTest={() => onTest(provider.name)}
          isTesting={testingProvider === provider.name}
          testResult={testResults[provider.name]}
        />
      ))}
    </div>
  );
}
