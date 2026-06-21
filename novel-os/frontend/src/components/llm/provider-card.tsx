import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { maskString } from "@/lib/utils";
import { Check, Edit2, Trash2, AlertCircle } from "lucide-react";
import type { LLMProvider } from "@/types";

interface ProviderCardProps {
  provider: LLMProvider;
  isDefault: boolean;
  onSetDefault: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
  isTesting: boolean;
  testResult?: { success: boolean; message: string; latency_ms?: number } | null;
}

export function ProviderCard({
  provider,
  isDefault,
  onSetDefault,
  onEdit,
  onDelete,
  onTest,
  isTesting,
  testResult,
}: ProviderCardProps) {
  return (
    <Card className={isDefault ? "border-primary/60 ring-1 ring-primary/30" : ""}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">{provider.name}</CardTitle>
              {isDefault && (
                <Badge variant="success">
                  <Check className="mr-1 size-3" />
                  默认
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{provider.model}</p>
          </div>
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" onClick={onEdit}>
              <Edit2 className="size-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={onDelete}>
              <Trash2 className="size-4 text-destructive" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-muted-foreground">类型</span>
            <p className="font-medium uppercase">{provider.type}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Base URL</span>
            <p className="font-medium truncate">{provider.base_url}</p>
          </div>
          <div>
            <span className="text-muted-foreground">API Key</span>
            <p className="font-medium">{maskString(provider.api_key)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Temperature</span>
            <p className="font-medium">{provider.temperature}</p>
          </div>
        </div>

        {testResult && (
          <div
            className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${
              testResult.success
                ? "bg-success/10 text-success"
                : "bg-destructive/10 text-destructive"
            }`}
          >
            {testResult.success ? (
              <Check className="size-4" />
            ) : (
              <AlertCircle className="size-4" />
            )}
            <span>
              {testResult.message}
              {testResult.latency_ms && ` (${testResult.latency_ms}ms)`}
            </span>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onTest}
            disabled={isTesting}
            className="flex-1"
          >
            {isTesting ? "测试中..." : "测试连接"}
          </Button>
          {!isDefault && (
            <Button variant="secondary" size="sm" onClick={onSetDefault} className="flex-1">
              设为默认
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
