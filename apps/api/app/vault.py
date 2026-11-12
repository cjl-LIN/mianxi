from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import yaml

from .clock import iso, now
from .db import db, hydrate_kp, one

WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
RELATIONS = ("prerequisite", "related", "part_of")
SCAN_FOLDERS = ("points", "inbox", "generated")


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    loaded = yaml.safe_load(match.group(1)) or {}
    if not isinstance(loaded, dict):
        return {}, text
    return loaded, text[match.end() :]


def _norm(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _norm(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_norm(item) for item in value]
    return value


def dump_note(meta: dict, body: str) -> str:
    cleaned = _norm(meta)
    dumped = yaml.safe_dump(cleaned, allow_unicode=True, sort_keys=False, width=100)
    return f"---\n{dumped}---\n\n{body.strip()}\n"


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def as_text(value, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).strip()


def summarize(body: str) -> str:
    parts: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("[["):
            continue
        parts.append(stripped)
        if len("".join(parts)) > 160:
            break
    return " ".join(parts)[:180]


def list_note_files(root: Path | None = None) -> list[Path]:
    from .db import vault_path

    base = root or vault_path()
    found: list[Path] = []
    for folder in SCAN_FOLDERS:
        directory = base / folder
        if directory.exists():
            found.extend(sorted(directory.rglob("*.md")))
    return found


def _pair_exists(conn, left: str, right: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM knowledge_edges
        WHERE (from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)
        LIMIT 1
        """,
        (left, right, right, left),
    ).fetchone()
    return row is not None


def _resolve_id(conn, token: str) -> str | None:
    token = token.strip()
    if not token:
        return None
    row = conn.execute("SELECT id FROM knowledge_points WHERE id = ?", (token,)).fetchone()
    if row:
        return row["id"]
    for candidate in conn.execute("SELECT id, title, aliases FROM knowledge_points"):
        if candidate["title"] == token:
            return candidate["id"]
        aliases = json.loads(candidate["aliases"] or "[]")
        if token in aliases:
            return candidate["id"]
    return None


def upsert_path(conn, path: Path, root: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)
    knowledge_id = as_text(meta.get("id"))
    if not knowledge_id.startswith("kp-"):
        return None
    title = as_text(meta.get("title"), path.stem)
    timestamp = iso(now())
    existing = conn.execute(
        "SELECT created_at FROM knowledge_points WHERE id = ?", (knowledge_id,)
    ).fetchone()
    created_at = existing["created_at"] if existing else timestamp
    created_field = as_text(meta.get("created"), created_at[:10])
    if not existing:
        created_at = f"{created_field}T09:00:00+08:00" if len(created_field) == 10 else timestamp
    rel = path.relative_to(root).as_posix()
    payload = {
        "id": knowledge_id,
        "title": title,
        "aliases": json.dumps([as_text(item) for item in as_list(meta.get("aliases")) if as_text(item)], ensure_ascii=False),
        "tags": json.dumps([as_text(item) for item in as_list(meta.get("tags")) if as_text(item)], ensure_ascii=False),
        "summary": summarize(body),
        "body": body.strip(),
        "body_path": rel,
        "sources": json.dumps([as_text(item) for item in as_list(meta.get("sources")) if as_text(item)], ensure_ascii=False),
        "keywords": json.dumps([as_text(item) for item in as_list(meta.get("keywords")) if as_text(item)], ensure_ascii=False),
        "questions": json.dumps([as_text(item) for item in as_list(meta.get("questions")) if as_text(item)], ensure_ascii=False),
        "outline": as_text(meta.get("outline")),
        "match_terms": json.dumps([as_text(item) for item in as_list(meta.get("match")) if as_text(item)], ensure_ascii=False),
        "fallback": 1 if bool(meta.get("fallback")) else 0,
        "created_at": created_at,
        "updated_at": timestamp,
    }
    conn.execute(
        """
        INSERT INTO knowledge_points (
          id, title, aliases, tags, summary, body, body_path, sources, keywords,
          questions, outline, match_terms, fallback, created_at, updated_at
        ) VALUES (
          :id, :title, :aliases, :tags, :summary, :body, :body_path, :sources, :keywords,
          :questions, :outline, :match_terms, :fallback, :created_at, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
          title = excluded.title,
          aliases = excluded.aliases,
          tags = excluded.tags,
          summary = excluded.summary,
          body = excluded.body,
          body_path = excluded.body_path,
          sources = excluded.sources,
          keywords = excluded.keywords,
          questions = excluded.questions,
          outline = excluded.outline,
          match_terms = excluded.match_terms,
          fallback = excluded.fallback,
          updated_at = excluded.updated_at
        """,
        payload,
    )
    conn.execute("DELETE FROM knowledge_edges WHERE from_id = ?", (knowledge_id,))
    for relation in RELATIONS:
        for target in as_list(meta.get(relation)):
            target_id = as_text(target)
            if target_id and target_id != knowledge_id:
                conn.execute(
                    "INSERT OR IGNORE INTO knowledge_edges(from_id, to_id, relation) VALUES (?, ?, ?)",
                    (knowledge_id, target_id, relation),
                )
    for project_id in as_list(meta.get("projects")):
        project_id = as_text(project_id)
        if not project_id:
            continue
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
            conn.execute(
                """
                INSERT OR IGNORE INTO project_knowledge(project_id, knowledge_id, created_at)
                VALUES (?, ?, ?)
                """,
                (project_id, knowledge_id, timestamp),
            )
    return knowledge_id


def refresh_wiki(conn) -> None:
    rows = conn.execute("SELECT id, body FROM knowledge_points").fetchall()
    for row in rows:
        for token in WIKI.findall(row["body"] or ""):
            target = _resolve_id(conn, token)
            if not target or target == row["id"] or _pair_exists(conn, row["id"], target):
                continue
            conn.execute(
                "INSERT OR IGNORE INTO knowledge_edges(from_id, to_id, relation) VALUES (?, ?, 'related')",
                (row["id"], target),
            )


def sync_vault() -> dict:
    from .db import vault_path

    root = vault_path()
    root.mkdir(parents=True, exist_ok=True)
    count = 0
    with db() as conn:
        for path in list_note_files(root):
            if upsert_path(conn, path, root):
                count += 1
        refresh_wiki(conn)
    return {"notes": count}


def write_knowledge_note(meta: dict, body: str, folder: str = "inbox") -> str:
    from .db import vault_path

    knowledge_id = as_text(meta.get("id"))
    if not knowledge_id.startswith("kp-"):
        raise ValueError("knowledge id must start with kp-")
    root = vault_path()
    existing = None
    with db() as conn:
        existing = one(conn, "SELECT body_path FROM knowledge_points WHERE id = ?", (knowledge_id,))
    destination: Path | None = None
    if existing and existing.get("body_path"):
        candidate = root / existing["body_path"]
        if candidate.exists():
            destination = candidate
    if destination is None:
        directory = root / folder
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{knowledge_id}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dump_note(meta, body), encoding="utf-8")
    with db() as conn:
        upsert_path(conn, destination, root)
        refresh_wiki(conn)
    return knowledge_id


def set_knowledge_projects(knowledge_id: str, project_ids: list[str]) -> None:
    from .db import vault_path

    with db() as conn:
        row = one(conn, "SELECT * FROM knowledge_points WHERE id = ?", (knowledge_id,))
    point = hydrate_kp(row)
    if not point:
        from .errors import AppError

        raise AppError(404, "知识点不存在")
    cleaned: list[str] = []
    for project_id in project_ids:
        if project_id and project_id not in cleaned:
            cleaned.append(project_id)
    path = vault_path() / point["body_path"]
    if path.exists():
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        meta["projects"] = cleaned
        path.write_text(dump_note(meta, body), encoding="utf-8")
    timestamp = iso(now())
    with db() as conn:
        known = []
        for project_id in cleaned:
            if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone():
                known.append(project_id)
        conn.execute("DELETE FROM project_knowledge WHERE knowledge_id = ?", (knowledge_id,))
        for project_id in known:
            conn.execute(
                """
                INSERT INTO project_knowledge(project_id, knowledge_id, created_at)
                VALUES (?, ?, ?)
                """,
                (project_id, knowledge_id, timestamp),
            )


def projects_of(knowledge_id: str) -> list[str]:
    from .db import fetchall

    rows = fetchall(
        "SELECT project_id FROM project_knowledge WHERE knowledge_id = ? ORDER BY created_at",
        (knowledge_id,),
    )
    return [row["project_id"] for row in rows]


def link_project(project_id: str, knowledge_id: str) -> None:
    current = projects_of(knowledge_id)
    if project_id not in current:
        current.append(project_id)
    set_knowledge_projects(knowledge_id, current)


def unlink_project(project_id: str, knowledge_id: str) -> None:
    current = [item for item in projects_of(knowledge_id) if item != project_id]
    set_knowledge_projects(knowledge_id, current)
