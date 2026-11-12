-- Bootstrap schema for 面习. Applied with CREATE IF NOT EXISTS on API startup.
-- The runnable database lives at data/app.db and is gitignored.

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  jd_text TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_points (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]',
  tags TEXT NOT NULL DEFAULT '[]',
  summary TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  body_path TEXT NOT NULL DEFAULT '',
  sources TEXT NOT NULL DEFAULT '[]',
  keywords TEXT NOT NULL DEFAULT '[]',
  questions TEXT NOT NULL DEFAULT '[]',
  outline TEXT NOT NULL DEFAULT '',
  match_terms TEXT NOT NULL DEFAULT '[]',
  fallback INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_knowledge (
  project_id TEXT NOT NULL,
  knowledge_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, knowledge_id)
);

-- Edge direction follows the note that declared it:
-- from_id's frontmatter lists to_id under `relation`
-- (prerequisite = to_id is a prerequisite of from_id).
CREATE TABLE IF NOT EXISTS knowledge_edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  relation TEXT NOT NULL CHECK (relation IN ('prerequisite', 'related', 'part_of')),
  UNIQUE (from_id, to_id, relation)
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  style TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  queue_json TEXT NOT NULL,
  cursor_idx INTEGER NOT NULL DEFAULT 0,
  followup_stage INTEGER NOT NULL DEFAULT 0,
  current_knowledge_id TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  knowledge_id TEXT,
  kind TEXT NOT NULL,
  modality TEXT NOT NULL DEFAULT 'text',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answer_scores (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  knowledge_id TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  relevance REAL NOT NULL,
  correctness REAL NOT NULL,
  completeness REAL NOT NULL,
  reasoning REAL NOT NULL,
  overall REAL NOT NULL,
  wrong TEXT NOT NULL DEFAULT '',
  missing TEXT NOT NULL DEFAULT '',
  better TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

-- One row per knowledge point. Projects do not own a second score.
CREATE TABLE IF NOT EXISTS mastery (
  knowledge_id TEXT PRIMARY KEY,
  score REAL NOT NULL,
  level TEXT NOT NULL,
  review_count INTEGER NOT NULL DEFAULT 0,
  last_practiced_at TEXT,
  next_review_at TEXT,
  last_session_id TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  knowledge_id TEXT NOT NULL,
  project_id TEXT,
  kind TEXT NOT NULL,
  message TEXT NOT NULL,
  due_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  dismissed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_pk_project ON project_knowledge(project_id);
CREATE INDEX IF NOT EXISTS idx_pk_knowledge ON project_knowledge(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_edges_from ON knowledge_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON knowledge_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_scores_created ON answer_scores(created_at);
CREATE INDEX IF NOT EXISTS idx_scores_knowledge ON answer_scores(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_mastery_next ON mastery(next_review_at);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(due_at);
