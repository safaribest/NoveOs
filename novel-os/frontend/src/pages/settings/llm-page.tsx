import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ProviderForm } from "@/components/llm/provider-form";
import { ProviderList } from "@/components/llm/provider-list";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getLLMSettings, updateLLMSettings, testLLMConnection, getAgentProviders, updateAgentProviders } from "@/api/settings";
import type { LLMProvider, LLMSettings, TestConnectionResult } from "@/types";
import { PlusCircle, Save, Zap, Shield, ScrollText, AlertCircle, Pencil } from "lucide-react";
import { toast } from "@/lib/toast";

export function LLMPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<LLMProvider | undefined>();
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestConnectionResult>>({});
  const [deleteConfirmName, setDeleteConfirmName] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"providers" | "agents">("providers");
  const [agentProviders, setAgentProviders] = useState<Record<string, string>>({});
  const [savingAgents, setSavingAgents] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["llm-settings"],
    queryFn: getLLMSettings,
  });

  const updateMutation = useMutation({
    mutationFn: updateLLMSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llm-settings"] });
    },
  });

  const providers = settings
    ? Object.values(settings.providers)
    : [];

  const providerNames = providers.map((p) => p.name);

  const { data: agentData } = useQuery({
    queryKey: ["llm-agent-providers"],
    queryFn: getAgentProviders,
    staleTime: 0,
  });

  const handleSaveAgents = async () => {
    setSavingAgents(true);
    try {
      // 过滤掉 __default__ 占位值
      const cleaned: Record<string, string> = {};
      for (const [k, v] of Object.entries(agentProviders)) {
        if (v && v !== "__default__") cleaned[k] = v;
      }
      await updateAgentProviders(cleaned);
      queryClient.invalidateQueries({ queryKey: ["llm-agent-providers"] });
      toast.success("Agent 分配已保存");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSavingAgents(false);
    }
  };

  // 同步 agent providers（首次加载 + 外部变更）
  const agentInitRef = useRef(false);
  useEffect(() => {
    if (agentData && !agentInitRef.current) {
      setAgentProviders(agentData);
      agentInitRef.current = true;
    }
  }, [agentData]);

  const handleAdd = (provider: LLMProvider) => {
    const newProviders = { ...(settings?.providers || {}) };
    newProviders[provider.name] = provider;

    const payload: LLMSettings = {
      default_provider: settings?.default_provider || provider.name,
      providers: newProviders,
    };

    updateMutation.mutate(payload, {
      onSuccess: () => {
        setShowForm(false);
        setEditingProvider(undefined);
      },
    });
  };

  const handleSetDefault = (name: string) => {
    if (!settings) return;
    updateMutation.mutate({
      ...settings,
      default_provider: name,
    });
  };

  const handleDelete = (name: string) => {
    setDeleteConfirmName(name);
  };

  const confirmDelete = () => {
    if (!settings || !deleteConfirmName) return;

    const newProviders = { ...settings.providers };
    delete newProviders[deleteConfirmName];

    updateMutation.mutate({
      default_provider: settings.default_provider === deleteConfirmName ? "" : settings.default_provider,
      providers: newProviders,
    });
    setDeleteConfirmName(null);
  };

  const handleEdit = (provider: LLMProvider) => {
    setEditingProvider(provider);
    setShowForm(true);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingProvider(undefined);
  };

  const handleTest = async (name: string) => {
    setTestingProvider(name);
    try {
      const result = await testLLMConnection(name);
      setTestResults((prev) => ({ ...prev, [name]: result }));
    } catch (error) {
      setTestResults((prev) => ({
        ...prev,
        [name]: {
          success: false,
          message: error instanceof Error ? error.message : "测试失败",
        },
      }));
    } finally {
      setTestingProvider(null);
    }
  };

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">LLM 配置</h1>
        <p className="text-sm text-muted-foreground">管理你的大语言模型 Provider，洞察和写作都需要调用它们</p>
      </div>
        {/* Tab 切换 */}
        <div className="mb-6 flex gap-1 rounded-lg bg-muted/50 p-1 w-fit">
          <button
            onClick={() => setActiveTab("providers")}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              activeTab === "providers" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Provider 列表
          </button>
          <button
            onClick={() => setActiveTab("agents")}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              activeTab === "agents" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            Agent 分配
          </button>
        </div>

        {activeTab === "providers" && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Provider 列表</CardTitle>
              </div>
              {!showForm && (
                <Button onClick={() => setShowForm(true)}>
                  <PlusCircle className="size-4" />
                  添加 Provider
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {showForm && (
              <div className="mb-8 rounded-lg border border-border bg-card p-6">
                <h3 className="mb-4 text-lg font-semibold">
                  {editingProvider ? "编辑 Provider" : "添加 Provider"}
                </h3>
                <ProviderForm
                  initialData={editingProvider}
                  existingNames={providers.map((p) => p.name)}
                  onSubmit={handleAdd}
                  onCancel={handleCancel}
                />
              </div>
            )}

            {isLoading ? (
              <div className="space-y-3">
                <div className="h-32 animate-pulse rounded-lg bg-muted/30" />
                <div className="h-32 animate-pulse rounded-lg bg-muted/30" />
              </div>
            ) : (
              <ProviderList
                providers={providers}
                defaultProvider={settings?.default_provider || ""}
                onSetDefault={handleSetDefault}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onTest={handleTest}
                testingProvider={testingProvider}
                testResults={testResults}
              />
            )}
          </CardContent>
        </Card>

        )}

        {activeTab === "agents" && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Agent 模型分配</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                为每个写作 Agent 分配独立的 LLM Provider。未分配的 Agent 将使用默认 Provider。
              </p>
              {[
                { key: "planner", label: "规划师", desc: "分析章节大纲，生成写作计划", icon: Zap },
                { key: "writer", label: "写手", desc: "根据计划撰写正文内容", icon: ScrollText },
                { key: "reviewer", label: "审核", desc: "检查内容质量、逻辑一致性", icon: Shield },
                { key: "polisher", label: "润色", desc: "优化文笔、修正语法", icon: Pencil },
                { key: "spot_fix", label: "质检", desc: "针对性修复具体问题", icon: AlertCircle },
              ].map((agent) => (
                <div key={agent.key} className="flex items-center gap-4 rounded-lg border border-border p-3">
                  <agent.icon className="size-5 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{agent.label}</div>
                    <div className="text-xs text-muted-foreground">{agent.desc}</div>
                  </div>
                  <div className="w-40">
                    <Select
                      value={agentProviders[agent.key] || ""}
                      onValueChange={(value) =>
                        setAgentProviders((prev) => ({ ...prev, [agent.key]: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="默认" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__default__">默认 Provider</SelectItem>
                        {providerNames.map((name) => (
                          <SelectItem key={name} value={name}>
                            {name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ))}
              <div className="flex justify-end">
                <Button onClick={handleSaveAgents} disabled={savingAgents}>
                  {savingAgents ? "保存中..." : "保存分配"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {settings?.default_provider && (
          <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-primary">
            <Save className="size-4" />
            当前默认 Provider：{settings.default_provider}
          </div>
        )}

      <Dialog open={!!deleteConfirmName} onOpenChange={(open) => { if (!open) setDeleteConfirmName(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除 Provider</DialogTitle>
            <DialogDescription>
              确定要删除 Provider <span className="font-semibold text-foreground">{deleteConfirmName}</span> 吗？
              删除后无法恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmName(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
