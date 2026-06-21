import { get, getToken } from "@/lib/api";

export interface RuntimeLog {
  log_id: string;
  level: string;
  agent: string;
  chapter_num: number | null;
  message: string;
  metadata?: string;
  created_at: string;
}

export interface GetLogsOptions {
  limit?: number;
  level?: string;
  agent?: string;
}

export async function getLogs(projectId: string, options: GetLogsOptions = {}): Promise<RuntimeLog[]> {
  const { limit = 100, level, agent } = options;
  const params: Record<string, unknown> = { limit };
  if (level) params.level = level;
  if (agent) params.agent = agent;
  return get<RuntimeLog[]>(`/projects/${encodeURIComponent(projectId)}/logs`, params);
}

export interface StreamLogsOptions {
  maxReconnectDelay?: number;
  onError?: (error: Error) => void;
}

export function streamLogs(
  projectId: string,
  onLog: (log: RuntimeLog) => void,
  options: StreamLogsOptions = {}
): { close: () => void } {
  const { maxReconnectDelay = 30_000, onError } = options;
  const baseURL = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  const token = getToken();
  const url = `${baseURL}/projects/${encodeURIComponent(projectId)}/logs/stream${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  let source: EventSource | null = null;
  let reconnectDelay = 1_000;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const connect = () => {
    if (closed) return;
    source = new EventSource(url);

    source.onopen = () => {
      // 连接成功后重置退避时间
      reconnectDelay = 1_000;
    };

    source.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as RuntimeLog;
        onLog(log);
      } catch {
        // 忽略解析失败的噪音
      }
    };

    source.onerror = () => {
      if (closed) return;
      onError?.(new Error("日志流连接异常，正在重连..."));
      source?.close();
      source = null;
      reconnectTimer = setTimeout(() => {
        reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
        connect();
      }, reconnectDelay);
    };
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      source?.close();
      source = null;
    },
  };
}
