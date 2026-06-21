import { get, post } from "@/lib/api";
import type {
  Category,
  GenerateOutlinePayload,
  GenerateTopicsPayload,
  TaskInfo,
  Topic,
} from "@/types/insight";

export async function getCategories(): Promise<Category[]> {
  const response = await get<{ categories: Category[] }>("/insights/categories");
  return response.categories;
}

export async function generateTopics(payload: GenerateTopicsPayload): Promise<{ task_id: string }> {
  return post<{ task_id: string }>("/insights/topics", payload);
}

export async function generateOutline(payload: GenerateOutlinePayload): Promise<{ task_id: string }> {
  return post<{ task_id: string }>("/insights/outline", payload);
}

export async function getTask(taskId: string): Promise<TaskInfo> {
  return get<TaskInfo>(`/insights/tasks/${taskId}`);
}

export async function getTaskResult(taskId: string): Promise<Topic[]> {
  return get<Topic[]>(`/insights/tasks/${taskId}/result`);
}
