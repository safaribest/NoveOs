import { get } from "@/lib/api";

export interface QualityDimension {
  label: string;
  value: number | null;
}

export interface ChapterQualityGate {
  chapter_num: number;
  reader_pull_score: number | null;
  quality_passed: boolean | null;
  gate_level: string | null;
  aggregate_score: number | null;
  dimensions: QualityDimension[];
}

export async function getChapterQualityGate(
  projectId: string,
  chapterNum: number
): Promise<ChapterQualityGate> {
  return get<ChapterQualityGate>(
    `/projects/${encodeURIComponent(projectId)}/chapters/${chapterNum}/quality`
  );
}
