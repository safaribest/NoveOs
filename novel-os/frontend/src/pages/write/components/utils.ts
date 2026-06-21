import type { ChapterMeta } from "@/api/projects";
import type { VolumeGroup } from "./types";

export function parseLogMetadata(metadata: string | undefined | null): Record<string, unknown> | null {
  if (!metadata) return null;
  try {
    return JSON.parse(metadata) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function isWritingEvent(eventType: string): boolean {
  return [
    "chapter_start",
    "agent_call_start",
    "agent_call_complete",
    "chapter_complete",
    "chapter_error",
  ].includes(eventType);
}

export function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

export function groupChaptersByVolume(
  chapters: ChapterMeta[],
  totalChapters: number
): VolumeGroup[] {
  const VOLUME_SIZE = 50;
  const maxNum = chapters.reduce((max, ch) => Math.max(max, ch.chapter_num), 0) || totalChapters || 0;
  const volumeCount = Math.max(1, Math.ceil(maxNum / VOLUME_SIZE));
  const groups: VolumeGroup[] = [];

  for (let i = 0; i < volumeCount; i++) {
    const start = i * VOLUME_SIZE + 1;
    const end = (i + 1) * VOLUME_SIZE;
    const inGroup = chapters.filter((ch) => ch.chapter_num >= start && ch.chapter_num <= end);
    if (inGroup.length > 0) {
      groups.push({ title: `卷${i + 1}`, chapters: inGroup });
    }
  }

  if (groups.length === 0 && chapters.length > 0) {
    groups.push({ title: "卷1", chapters });
  }

  return groups;
}
