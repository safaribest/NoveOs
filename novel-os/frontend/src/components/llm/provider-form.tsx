import { useEffect, useState } from "react";
import { useForm, useWatch, Controller, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getProviderDefaults, providerTypeOptions } from "@/api/settings";
import type { LLMProvider } from "@/types";

const providerSchema = z.object({
  name: z.string().min(1, "名称不能为空"),
  type: z.enum(["deepseek", "openai", "kimi", "custom"]),
  api_key: z.string().min(1, "API Key 不能为空"),
  base_url: z.string().min(1, "Base URL 不能为空").refine(
    (val) => val.startsWith("http://") || val.startsWith("https://"),
    { message: "必须以 http:// 或 https:// 开头" }
  ),
  model: z.string().min(1, "模型名称不能为空"),
  temperature: z.coerce.number().min(0).max(2),
  max_tokens: z.coerce.number().min(1).max(128000),
  timeout: z.coerce.number().min(5).max(600),
});

type ProviderFormData = z.infer<typeof providerSchema>;

interface ProviderFormProps {
  initialData?: LLMProvider;
  existingNames?: string[];
  onSubmit: (data: LLMProvider) => void;
  onCancel: () => void;
}

export function ProviderForm({ initialData, existingNames = [], onSubmit, onCancel }: ProviderFormProps) {
  const isEditing = !!initialData;
  const [duplicateError, setDuplicateError] = useState("");
  const reservedNames = isEditing
    ? existingNames.filter((n) => n !== initialData?.name)
    : existingNames;

  const form = useForm<ProviderFormData>({
    resolver: zodResolver(providerSchema) as Resolver<ProviderFormData>,
    defaultValues: {
      name: "",
      type: "deepseek",
      api_key: "",
      base_url: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      temperature: 0.8,
      max_tokens: 4096,
      timeout: 120,
    },
  });

  useEffect(() => {
    if (initialData) {
      form.reset({
        name: initialData.name,
        type: initialData.type,
        api_key: initialData.api_key,
        base_url: initialData.base_url,
        model: initialData.model,
        temperature: initialData.temperature,
        max_tokens: initialData.max_tokens,
        timeout: initialData.timeout,
      });
    }
  }, [initialData, form]);

  const type = useWatch({ control: form.control, name: "type" });

  useEffect(() => {
    if (!isEditing) {
      const defaults = getProviderDefaults(type);
      if (defaults.base_url) form.setValue("base_url", defaults.base_url);
      if (defaults.model) form.setValue("model", defaults.model);
    }
  }, [type, form, isEditing]);

  const handleFormSubmit = (data: ProviderFormData) => {
    if (reservedNames.includes(data.name)) {
      setDuplicateError("Provider 名称已存在，请更换一个名称");
      return;
    }
    setDuplicateError("");
    onSubmit(data as LLMProvider);
  };

  return (
    <form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="name">名称</Label>
          <Input
            id="name"
            placeholder="例如：deepseek"
            disabled={isEditing}
            {...form.register("name")}
            error={form.formState.errors.name?.message}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="type">Provider 类型</Label>
          <Controller
            name="type"
            control={form.control}
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="type" error={form.formState.errors.type?.message}>
                  <SelectValue placeholder="选择 Provider 类型" />
                </SelectTrigger>
                <SelectContent>
                  {providerTypeOptions().map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
          {form.formState.errors.type && (
            <p className="text-xs text-destructive" role="alert">
              {form.formState.errors.type.message}
            </p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="api_key">API Key</Label>
        <Input
          id="api_key"
          type="password"
          placeholder="sk-..."
          {...form.register("api_key")}
          error={form.formState.errors.api_key?.message}
        />
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="base_url">Base URL</Label>
          <Input
            id="base_url"
            placeholder="https://api.example.com/v1"
            {...form.register("base_url")}
            error={form.formState.errors.base_url?.message}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="model">模型</Label>
          <Input
            id="model"
            placeholder="deepseek-chat"
            {...form.register("model")}
            error={form.formState.errors.model?.message}
          />
        </div>
      </div>

      <div className="grid gap-5 md:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="temperature">Temperature</Label>
          <Input
            id="temperature"
            type="number"
            step="0.1"
            {...form.register("temperature")}
            error={form.formState.errors.temperature?.message}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="max_tokens">Max Tokens</Label>
          <Input
            id="max_tokens"
            type="number"
            {...form.register("max_tokens")}
            error={form.formState.errors.max_tokens?.message}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="timeout">超时（秒）</Label>
          <Input
            id="timeout"
            type="number"
            {...form.register("timeout")}
            error={form.formState.errors.timeout?.message}
          />
        </div>
      </div>

      {duplicateError && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {duplicateError}
        </div>
      )}
      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          取消
        </Button>
        <Button type="submit">
          {isEditing ? "保存修改" : "添加 Provider"}
        </Button>
      </div>
    </form>
  );
}
