export interface Category {
  id: string;
  name: string;
  genre?: string;
  tags?: string[];
  children?: Category[];
}

export interface Topic {
  id: string;
  title: string;
  hook: string;
  slap_points: string[];
  target_reader: string;
  risks: string[];
  why_now: string;
}

export interface GenerateTopicsPayload {
  category_id: string;
  platform?: string;
  style?: string;
  chapters_target?: number;
  words_per_chapter?: number;
  extra_notes?: string;
}

export interface Volume {
  index: number;
  title: string;
  range: string;
  theme: string;
  climax: string;
}

export interface OutlineItem {
  chapter: number;
  title: string;
  arc: string;
  core_event: string;
  face_slap_target?: string;
  face_slap_method?: string;
  husband_moment?: string;
  chapter_hook?: string;
  emotion_ratio?: string;
  skill_unlocked?: string;
}

export interface Character {
  name: string;
  role: string;
  brief: string;
  arc: string;
  tags: string[];
}

export interface Debt {
  debt_id: string;
  type: string;
  content: string;
  bury_chapter: number;
  collect_chapter?: number;
}

export interface Skill {
  name: string;
  chapter: number;
  description: string;
}

export interface Outline {
  topic_title?: string;
  topic_hook?: string;
  genre: string;
  platform: string;
  chapters_target: number;
  words_per_chapter: number;
  summary: string;
  volumes: Volume[];
  outline: OutlineItem[];
  characters: Character[];
  debts: Debt[];
  foreshadowing?: Debt[];
  rules: string[];
  skills: Skill[];
}

export interface GenerateOutlinePayload {
  topic: Topic;
  category_id: string;
  platform: string;
  style: string;
  chapters_target: number;
  words_per_chapter: number;
  extra_notes?: string;
}

export interface TaskInfo {
  id: string;
  type: string;
  status: "pending" | "running" | "success" | "failed";
  progress: number;
  result: Topic[] | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface OutlineTaskInfo extends Omit<TaskInfo, "result"> {
  result: Outline | null;
}
