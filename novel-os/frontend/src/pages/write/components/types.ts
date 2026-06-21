import type { ChapterMeta, ProjectStatus } from "@/api/projects";

export interface ProjectSummary extends ProjectStatus {
  total_words?: number;
}

export interface ChapterAgentInfo {
  agent: string;
  ts: number;
}

export interface VolumeGroup {
  title: string;
  chapters: ChapterMeta[];
}
