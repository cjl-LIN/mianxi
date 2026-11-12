export type Level = "weak" | "medium" | "mastered" | "fluent";

export interface ProjectRef {
  id: string;
  name: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  description: string;
  jd_text: string;
  created_at: string;
  knowledge_count: number;
  mastered_count: number;
  due_count: number;
}

export interface Chip {
  label: string;
  id: string;
  title: string;
}

export interface KnowledgeCard {
  id: string;
  title: string;
  aliases: string[];
  tags: string[];
  summary: string;
  keywords: string[];
  level: Level | null;
  score: number | null;
  next_review_at: string | null;
  last_practiced_at: string | null;
  chips: Chip[];
}

export interface PlanPoint {
  id: string;
  title: string;
  reason: string;
  level: Level | null;
  score: number | null;
}

export interface ProjectDetail {
  id: string;
  name: string;
  description: string;
  jd_text: string;
  created_at: string;
  updated_at: string;
  knowledge: KnowledgeCard[];
  plan: {
    points: PlanPoint[];
    skipped_mastered: PlanPoint[];
    notice: string;
  };
}

export interface MasteryRow {
  id: string;
  title: string;
  score: number | null;
  level: Level | null;
  next_review_at: string | null;
  last_practiced_at: string | null;
  practiced_today: boolean;
  projects: ProjectRef[];
}

export interface Distribution {
  weak: number;
  medium: number;
  mastered: number;
  fluent: number;
}

export interface Reminder {
  id: string;
  knowledge_id: string;
  project_id: string | null;
  kind: string;
  message: string;
  due_at: string;
  created_at: string;
  title: string;
}

export interface Gap {
  id: string;
  knowledge_id: string;
  title: string;
  missing: string;
  wrong: string;
  overall: number;
  created_at: string;
}

export interface RelatedPoint {
  id: string;
  title: string;
  relation: string;
}

export interface HistoryItem {
  id: string;
  session_id: string;
  knowledge_id: string;
  prompt: string;
  answer: string;
  title: string;
  relevance: number;
  correctness: number;
  completeness: number;
  reasoning: number;
  overall: number;
  wrong: string;
  missing: string;
  better: string;
  created_at: string;
  project_id: string;
  project_name: string;
  style: string;
  mode: string;
  projects: ProjectRef[];
  related: RelatedPoint[];
}

export interface DashboardData {
  today: string;
  timezone: string;
  practice: { sessions: number; answers: number; points: number };
  mastery_today: { average: number | null; distribution: Distribution };
  mastery_global: {
    average: number | null;
    tracked: number;
    unpracticed: number;
    distribution: Distribution;
  };
  rows: MasteryRow[];
  gaps: Gap[];
  reminders: Reminder[];
  llm: boolean;
}

export interface ScoreBlock {
  relevance: number;
  correctness: number;
  completeness: number;
  reasoning: number;
  overall: number;
}

export interface ReportPoint extends ScoreBlock {
  knowledge_id: string;
  title: string;
  wrong: string;
  missing: string;
  better: string;
  mastery: { score: number; level: Level; next_review_at: string } | null;
}

export interface Report {
  averages: ScoreBlock | null;
  by_point: ReportPoint[];
}

export interface ChatMessage {
  id: string;
  role: string;
  content: string;
  knowledge_id: string | null;
  kind: string;
  modality: string;
  created_at: string;
}

export interface Session {
  id: string;
  project: ProjectRef | null;
  style: "strict" | "loose";
  mode: "mock" | "review";
  status: "active" | "ready" | "finished";
  queue: { id: string; title: string }[];
  cursor_idx: number;
  followup_stage: number;
  current_point: { id: string; title: string; outline: string; aliases: string[] } | null;
  messages: ChatMessage[];
  report: Report | null;
  created_at: string;
  finished_at: string | null;
  llm: boolean;
}

export interface ReviewItem {
  knowledge_id: string;
  title: string;
  score: number | null;
  level: Level | null;
  last_practiced_at: string | null;
  next_review_at: string | null;
  review_count: number;
  status: string;
  days_until: number | null;
  projects: ProjectRef[];
}

export interface GraphNode {
  id: string;
  title: string;
  level: Level | null;
  score: number | null;
  in_project: boolean;
}

export interface GraphEdge {
  from_id: string;
  to_id: string;
  relation: string;
}

export interface Health {
  ok: boolean;
  app: string;
  llm: boolean;
  search: boolean;
  projects: number;
  knowledge: number;
}
