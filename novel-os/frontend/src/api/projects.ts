import { get, post, put, del } from "@/lib/api";

export interface ProjectStatus {
  project_id: string;
  name: string;
  genre: string;
  platform: string;
  status: string;
  current_chapter: number;
  completed_chapters: number;
  total_chapters: number;
  words_per_chapter: number;
  total_words_target: number;
  base_path: string;
  created_at: string;
}

export interface ChapterMeta {
  chapter_num: number;
  title: string | null;
  summary: string | null;
  word_count: number | null;
  mode: string | null;
  created_at: string | null;
  filename: string | null;
}

export interface Volume {
  index?: number;
  title?: string;
  range?: string;
  theme?: string;
  climax?: string;
}

export interface ChapterOutline {
  chapter: number;
  title?: string;
  arc?: string;
  core_event?: string;
  face_slap_target?: string;
  face_slap_method?: string;
  husband_moment?: string;
  chapter_hook?: string;
  emotion_ratio?: string;
  skill_unlocked?: string;
}

export interface OutlineBlock {
  summary?: string;
  volumes?: Volume[];
  chapters?: ChapterOutline[];
}

export interface CharacterState {
  name: string;
  chapter: number;
  location?: string;
  emotional_state?: string;
  known_secrets?: string;
  unknown_secrets?: string;
  abilities_active?: string;
  abilities_locked?: string;
  dialog_fingerprint?: string;
  body_language?: string;
  physical_description?: string;
}

export interface ItemState {
  item_name: string;
  chapter: number;
  location?: string;
  state?: string;
  rule?: string;
  state_history?: string;
}

export interface Skill {
  skill_name: string;
  unlock_chapter?: number;
  description?: string;
  used_chapters?: string;
}

export interface Debt {
  debt_id: string;
  type?: string;
  content: string;
  bury_chapter: number;
  collect_chapter?: number | null;
  status?: string;
}

export interface Foreshadowing {
  fs_id: string;
  content: string;
  bury_chapter: number;
  collect_chapter?: string;
  type?: string;
  status?: string;
}

export interface Term {
  term: string;
  category?: string;
  first_chapter?: number;
  description?: string;
}

export interface DashboardData {
  outline: OutlineBlock;
  characters: CharacterState[];
  items: ItemState[];
  skills: Skill[];
  debts: Debt[];
  foreshadowing: Foreshadowing[];
  terms: Term[];
}

export async function getProject(projectId: string): Promise<ProjectStatus> {
  return get<ProjectStatus>(`/projects/${encodeURIComponent(projectId)}`);
}

export interface UpdateProjectPayload {
  name?: string;
  genre?: string;
  platform?: string;
  chapters_target?: number;
  words_per_chapter?: number;
}

export async function updateProject(
  projectId: string,
  payload: UpdateProjectPayload
): Promise<ProjectStatus> {
  return put<ProjectStatus>(`/projects/${encodeURIComponent(projectId)}`, payload);
}

export async function listProjects(): Promise<ProjectStatus[]> {
  return get<ProjectStatus[]>("/projects");
}

export interface CreateFromOutlinePayload {
  title: string;
  outline: unknown;
  chapters_target?: number;
  words_per_chapter?: number;
}

export async function createFromOutline(payload: CreateFromOutlinePayload): Promise<{ project_id: string; title: string }> {
  return post<{ project_id: string; title: string }>("/projects/from-outline", payload);
}

export async function listChapters(projectId: string): Promise<ChapterMeta[]> {
  return get<ChapterMeta[]>(`/projects/${encodeURIComponent(projectId)}/chapters`);
}

export async function getProjectDashboard(projectId: string): Promise<DashboardData> {
  return get<DashboardData>(`/projects/${encodeURIComponent(projectId)}/dashboard`);
}

export async function getChapterContent(projectId: string, chapterNum: number): Promise<{ content: string }> {
  return get<{ content: string }>(`/projects/${encodeURIComponent(projectId)}/chapters/${chapterNum}/content`);
}

export async function saveChapterContent(
  projectId: string,
  chapterNum: number,
  content: string
): Promise<{ saved: boolean }> {
  return put<{ saved: boolean }>(`/projects/${encodeURIComponent(projectId)}/chapters/${chapterNum}/content`, { content });
}

export async function deleteProject(projectId: string, wipe = false): Promise<void> {
  await del<void>(`/projects/${encodeURIComponent(projectId)}?wipe=${wipe}`);
}
