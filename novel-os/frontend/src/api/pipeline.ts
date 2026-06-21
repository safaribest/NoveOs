import { get, post } from "@/lib/api";

export interface PipelineStatus {
  pipeline_id: string | null;
  status: string;
  current_step_index: number;
  can_start: boolean;
  is_running: boolean;
  audit: {
    quality_passed: boolean;
    sensitive_passed: boolean;
  };
  reader_pull_score: number | null;
}

export async function getPipelineStatus(projectId: string): Promise<PipelineStatus> {
  return get<PipelineStatus>(`/projects/${encodeURIComponent(projectId)}/pipeline`);
}

export async function startPipeline(
  projectId: string,
  chapterRange: string = "1-100",
  resume: boolean = false,
): Promise<{ pipeline_id: string }> {
  return post<{ pipeline_id: string }>(`/projects/${encodeURIComponent(projectId)}/pipeline/start`, {
    chapter_range: chapterRange,
    resume,
  });
}

export async function pausePipeline(projectId: string): Promise<null> {
  return post<null>(`/projects/${encodeURIComponent(projectId)}/pipeline/pause`, {});
}

export async function stopPipeline(projectId: string): Promise<null> {
  return post<null>(`/projects/${encodeURIComponent(projectId)}/pipeline/stop`, {});
}
