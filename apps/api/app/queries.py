from __future__ import annotations

import secrets

from .clock import days_until, iso, now, review_status, today_bounds
from .db import db, fetchall, fetchone, hydrate_kp, many, one
from .errors import AppError
from .interview import build_plan
from .llm import llm_enabled
from .db import vault_path
from .vault import projects_of, unlink_project

SORTS = {
    "time": "s.created_at",
    "overall": "s.overall",
    "relevance": "s.relevance",
    "correctness": "s.correctness",
    "completeness": "s.completeness",
    "reasoning": "s.reasoning",
}
LEVELS = ("weak", "medium", "mastered", "fluent")


def _distribution(rows: list[dict]) -> dict:
    dist = {level: 0 for level in LEVELS}
    for row in rows:
        level = row.get("level")
        if level in dist:
            dist[level] += 1
    return dist


def _projects_by_knowledge() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in fetchall(
        """
        SELECT pk.knowledge_id, p.id, p.name
        FROM project_knowledge pk
        JOIN projects p ON p.id = pk.project_id
        ORDER BY p.created_at
        """
    ):
        grouped.setdefault(row["knowledge_id"], []).append({"id": row["id"], "name": row["name"]})
    return grouped


def _require_project(project_id: str) -> dict:
    project = fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise AppError(404, "项目不存在")
    return project


def list_projects() -> dict:
    _start, end = today_bounds()
    projects = fetchall("SELECT * FROM projects ORDER BY created_at DESC")
    items = []
    for project in projects:
        counts = fetchone(
            """
            SELECT
              COUNT(pk.knowledge_id) AS knowledge_count,
              COALESCE(SUM(CASE WHEN m.level IN ('mastered', 'fluent') THEN 1 ELSE 0 END), 0) AS mastered_count,
              COALESCE(SUM(CASE WHEN m.next_review_at IS NOT NULL AND m.next_review_at < ? THEN 1 ELSE 0 END), 0) AS due_count
            FROM project_knowledge pk
            LEFT JOIN mastery m ON m.knowledge_id = pk.knowledge_id
            WHERE pk.project_id = ?
            """,
            (end, project["id"]),
        )
        project["knowledge_count"] = int(counts["knowledge_count"] or 0)
        project["mastered_count"] = int(counts["mastered_count"] or 0)
        project["due_count"] = int(counts["due_count"] or 0)
        items.append(project)
    return {"projects": items}


def _chips(knowledge_id: str, edges: list[dict], titles: dict[str, str]) -> list[dict]:
    chips = []
    for edge in edges:
        if edge["from_id"] != knowledge_id and edge["to_id"] != knowledge_id:
            continue
        outgoing = edge["from_id"] == knowledge_id
        other = edge["to_id"] if outgoing else edge["from_id"]
        if other not in titles:
            continue
        relation = edge["relation"]
        if relation == "related":
            label = "相关"
        elif relation == "prerequisite":
            label = "前置" if outgoing else "被依赖"
        else:
            label = "属于" if outgoing else "包含"
        chips.append({"label": label, "id": other, "title": titles[other]})
        if len(chips) >= 6:
            break
    return chips


def project_detail(project_id: str) -> dict:
    project = _require_project(project_id)
    points = [
        hydrate_kp(row)
        for row in fetchall(
            """
            SELECT kp.* FROM knowledge_points kp
            JOIN project_knowledge pk ON pk.knowledge_id = kp.id
            WHERE pk.project_id = ?
            ORDER BY kp.title
            """,
            (project_id,),
        )
    ]
    ids = [point["id"] for point in points]
    mastery = {}
    if ids:
        marks = ",".join("?" * len(ids))
        mastery = {
            row["knowledge_id"]: row
            for row in fetchall(f"SELECT * FROM mastery WHERE knowledge_id IN ({marks})", ids)
        }
    titles = {row["id"]: row["title"] for row in fetchall("SELECT id, title FROM knowledge_points")}
    edges = []
    if ids:
        marks = ",".join("?" * len(ids))
        edges = fetchall(
            f"""
            SELECT from_id, to_id, relation FROM knowledge_edges
            WHERE from_id IN ({marks}) OR to_id IN ({marks})
            """,
            [*ids, *ids],
        )
    knowledge = []
    for point in points:
        record = mastery.get(point["id"])
        knowledge.append(
            {
                "id": point["id"],
                "title": point["title"],
                "aliases": point["aliases"],
                "tags": point["tags"],
                "summary": point["summary"],
                "keywords": point["keywords"],
                "level": record["level"] if record else None,
                "score": record["score"] if record else None,
                "next_review_at": record["next_review_at"] if record else None,
                "last_practiced_at": record["last_practiced_at"] if record else None,
                "chips": _chips(point["id"], edges, titles),
            }
        )
    project["knowledge"] = knowledge
    project["plan"] = build_plan(project_id)
    return project


def create_project(name: str, description: str, jd_text: str, seed: bool) -> dict:
    name = (name or "").strip()
    description = (description or "").strip()
    jd_text = (jd_text or "").strip()
    if not name:
        raise AppError(400, "先写项目名称。")
    if len(name) > 80:
        raise AppError(400, "项目名称请压到 80 字以内。")
    if len(description) > 4000 or len(jd_text) > 20000:
        raise AppError(400, "描述或 JD 太长了。")
    project_id = "proj_" + secrets.token_hex(4)
    timestamp = iso(now())
    with db() as conn:
        conn.execute(
            """
            INSERT INTO projects(id, name, description, jd_text, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, name, description, jd_text, timestamp, timestamp),
        )
    if seed:
        from .ingest import collect_for_project

        collect_for_project(project_id)
    return project_detail(project_id)


def _remove_generated(knowledge_id: str) -> None:
    point = hydrate_kp(fetchone("SELECT * FROM knowledge_points WHERE id = ?", (knowledge_id,)))
    if not point:
        return
    path = vault_path() / point["body_path"] if point["body_path"] else None
    if path and path.exists() and (path.parts[-2] in {"inbox", "generated"} or point["id"].startswith(("kp-role-", "kp-search-", "kp-up-"))):
        path.unlink()
    with db() as conn:
        conn.execute("DELETE FROM knowledge_edges WHERE from_id = ? OR to_id = ?", (knowledge_id, knowledge_id))
        conn.execute("DELETE FROM project_knowledge WHERE knowledge_id = ?", (knowledge_id,))
        conn.execute("DELETE FROM reminders WHERE knowledge_id = ?", (knowledge_id,))
        conn.execute("DELETE FROM mastery WHERE knowledge_id = ?", (knowledge_id,))
        conn.execute("DELETE FROM knowledge_points WHERE id = ?", (knowledge_id,))


def delete_project(project_id: str) -> None:
    _require_project(project_id)
    linked = [row["knowledge_id"] for row in fetchall(
        "SELECT knowledge_id FROM project_knowledge WHERE project_id = ?", (project_id,)
    )]
    for knowledge_id in linked:
        unlink_project(project_id, knowledge_id)
    for knowledge_id in linked:
        point = fetchone("SELECT id, body_path FROM knowledge_points WHERE id = ?", (knowledge_id,))
        if not point or projects_of(knowledge_id):
            continue
        body_path = point["body_path"] or ""
        removable = body_path.startswith("inbox/") or body_path.startswith("generated/") or knowledge_id.startswith(("kp-role-", "kp-search-", "kp-up-"))
        if removable:
            _remove_generated(knowledge_id)
    with db() as conn:
        sessions = many(conn, "SELECT id FROM sessions WHERE project_id = ?", (project_id,))
        for session in sessions:
            conn.execute("DELETE FROM answer_scores WHERE session_id = ?", (session["id"],))
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session["id"],))
        conn.execute("DELETE FROM sessions WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM reminders WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM project_knowledge WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def search_knowledge(q: str, project_id: str | None, unlinked: bool) -> dict:
    linked: set[str] = set()
    if project_id:
        linked = {
            row["knowledge_id"]
            for row in fetchall(
                "SELECT knowledge_id FROM project_knowledge WHERE project_id = ?", (project_id,)
            )
        }
    needle = (q or "").strip().lower()
    items = []
    for row in fetchall("SELECT * FROM knowledge_points ORDER BY title"):
        point = hydrate_kp(row)
        if unlinked and project_id and point["id"] in linked:
            continue
        if needle:
            blob = " ".join(
                [
                    point["id"],
                    point["title"],
                    point["summary"],
                    " ".join(point["aliases"]),
                    " ".join(point["tags"]),
                    " ".join(point["keywords"]),
                ]
            ).lower()
            if needle not in blob:
                continue
        items.append(
            {
                "id": point["id"],
                "title": point["title"],
                "summary": point["summary"],
                "tags": point["tags"],
                "aliases": point["aliases"],
            }
        )
    return {"items": items}


def knowledge_detail(knowledge_id: str) -> dict:
    point = hydrate_kp(fetchone("SELECT * FROM knowledge_points WHERE id = ?", (knowledge_id,)))
    if not point:
        raise AppError(404, "知识点不存在")
    titles = {row["id"]: row["title"] for row in fetchall("SELECT id, title FROM knowledge_points")}
    relations = {"prerequisite": [], "part_of": [], "related": [], "required_by": [], "has_parts": []}
    edges = fetchall(
        "SELECT from_id, to_id, relation FROM knowledge_edges WHERE from_id = ? OR to_id = ?",
        (knowledge_id, knowledge_id),
    )
    for edge in edges:
        other = edge["to_id"] if edge["from_id"] == knowledge_id else edge["from_id"]
        if other not in titles:
            continue
        item = {"id": other, "title": titles[other]}
        outgoing = edge["from_id"] == knowledge_id
        if edge["relation"] == "related":
            relations["related"].append(item)
        elif edge["relation"] == "prerequisite" and outgoing:
            relations["prerequisite"].append(item)
        elif edge["relation"] == "prerequisite":
            relations["required_by"].append(item)
        elif edge["relation"] == "part_of" and outgoing:
            relations["part_of"].append(item)
        else:
            relations["has_parts"].append(item)
    point["relations"] = relations
    point["projects"] = _projects_by_knowledge().get(knowledge_id, [])
    point["mastery"] = fetchone("SELECT * FROM mastery WHERE knowledge_id = ?", (knowledge_id,))
    return point


def graph(project_id: str | None) -> dict:
    if project_id:
        _require_project(project_id)
        base = fetchall(
            """
            SELECT kp.id, kp.title FROM knowledge_points kp
            JOIN project_knowledge pk ON pk.knowledge_id = kp.id
            WHERE pk.project_id = ?
            """,
            (project_id,),
        )
    else:
        base = fetchall("SELECT id, title FROM knowledge_points")
    titles = {row["id"]: row["title"] for row in fetchall("SELECT id, title FROM knowledge_points")}
    ids = [row["id"] for row in base]
    edges = []
    if ids:
        marks = ",".join("?" * len(ids))
        edges = fetchall(
            f"""
            SELECT from_id, to_id, relation FROM knowledge_edges
            WHERE (from_id IN ({marks}) OR to_id IN ({marks}))
            """,
            [*ids, *ids],
        )
        edges = [edge for edge in edges if edge["from_id"] in titles and edge["to_id"] in titles]
    node_ids = set(ids)
    for edge in edges:
        node_ids.add(edge["from_id"])
        node_ids.add(edge["to_id"])
    mastery = {}
    if node_ids:
        marks = ",".join("?" * len(node_ids))
        mastery = {
            row["knowledge_id"]: row
            for row in fetchall(f"SELECT * FROM mastery WHERE knowledge_id IN ({marks})", list(node_ids))
        }
    in_project = set(ids)
    nodes = []
    for knowledge_id in sorted(node_ids, key=lambda item: titles.get(item, item)):
        record = mastery.get(knowledge_id)
        nodes.append(
            {
                "id": knowledge_id,
                "title": titles.get(knowledge_id, knowledge_id),
                "level": record["level"] if record else None,
                "score": record["score"] if record else None,
                "in_project": knowledge_id in in_project,
            }
        )
    return {"nodes": nodes, "edges": edges}


def _history_query(sort: str, order: str, project_id: str | None, limit: int) -> list[dict]:
    column = SORTS.get(sort, "s.created_at")
    direction = "ASC" if order == "asc" else "DESC"
    sql = f"""
        SELECT s.id, s.session_id, s.knowledge_id, s.prompt, s.relevance, s.correctness,
               s.completeness, s.reasoning, s.overall, s.wrong, s.missing, s.better, s.created_at,
               m.content AS answer, kp.title, se.project_id, se.style, se.mode, p.name AS project_name
        FROM answer_scores s
        JOIN messages m ON m.id = s.message_id
        JOIN knowledge_points kp ON kp.id = s.knowledge_id
        JOIN sessions se ON se.id = s.session_id
        JOIN projects p ON p.id = se.project_id
        WHERE 1 = 1
    """
    params: list = []
    if project_id:
        sql += " AND se.project_id = ?"
        params.append(project_id)
    sql += f" ORDER BY {column} {direction}, s.id {direction} LIMIT ?"
    params.append(max(1, min(limit, 200)))
    rows = fetchall(sql, params)
    projects = _projects_by_knowledge()
    knowledge_ids = list({row["knowledge_id"] for row in rows})
    related: dict[str, list[dict]] = {knowledge_id: [] for knowledge_id in knowledge_ids}
    if knowledge_ids:
        marks = ",".join("?" * len(knowledge_ids))
        edges = fetchall(
            f"""
            SELECT from_id, to_id, relation FROM knowledge_edges
            WHERE from_id IN ({marks}) OR to_id IN ({marks})
            """,
            [*knowledge_ids, *knowledge_ids],
        )
        titles = {row["id"]: row["title"] for row in fetchall("SELECT id, title FROM knowledge_points")}
        for edge in edges:
            for knowledge_id in (edge["from_id"], edge["to_id"]):
                if knowledge_id not in related:
                    continue
                other = edge["to_id"] if edge["from_id"] == knowledge_id else edge["from_id"]
                if other not in titles or len(related[knowledge_id]) >= 5:
                    continue
                related[knowledge_id].append(
                    {"id": other, "title": titles[other], "relation": edge["relation"]}
                )
    items = []
    for row in rows:
        row["projects"] = projects.get(row["knowledge_id"], [])
        row["related"] = related.get(row["knowledge_id"], [])
        items.append(row)
    return items


def dashboard(project_id: str | None) -> dict:
    if project_id:
        _require_project(project_id)
    start, end = today_bounds()
    project_clause = ""
    project_params: list = []
    if project_id:
        project_clause = " AND se.project_id = ?"
        project_params = [project_id]

    sessions = fetchone(
        f"SELECT COUNT(*) AS n FROM sessions se WHERE se.created_at >= ? AND se.created_at < ?{project_clause}",
        (start, end, *project_params),
    )["n"]
    answers = fetchone(
        f"""
        SELECT COUNT(*) AS n FROM messages m
        JOIN sessions se ON se.id = m.session_id
        WHERE m.role = 'candidate' AND m.created_at >= ? AND m.created_at < ?{project_clause}
        """,
        (start, end, *project_params),
    )["n"]
    points_today = fetchone(
        f"""
        SELECT COUNT(DISTINCT s.knowledge_id) AS n
        FROM answer_scores s
        JOIN sessions se ON se.id = s.session_id
        WHERE s.created_at >= ? AND s.created_at < ?{project_clause}
        """,
        (start, end, *project_params),
    )["n"]

    scope = ""
    scope_params: list = []
    if project_id:
        scope = " AND EXISTS (SELECT 1 FROM project_knowledge pk WHERE pk.knowledge_id = kp.id AND pk.project_id = ?)"
        scope_params = [project_id]
    mastered_rows = fetchall(
        f"""
        SELECT m.knowledge_id, m.score, m.level, m.next_review_at, m.last_practiced_at, kp.title, kp.id
        FROM knowledge_points kp
        LEFT JOIN mastery m ON m.knowledge_id = kp.id
        WHERE 1 = 1 {scope}
        ORDER BY m.score IS NULL, m.score DESC, kp.title
        """,
        scope_params,
    )
    projects = _projects_by_knowledge()
    rows = []
    tracked = []
    practiced = []
    unpracticed = 0
    for row in mastered_rows:
        record_level = row["level"]
        practiced_today = bool(row["last_practiced_at"] and start <= row["last_practiced_at"] < end)
        item = {
            "id": row["id"],
            "title": row["title"],
            "score": row["score"],
            "level": record_level,
            "next_review_at": row["next_review_at"],
            "last_practiced_at": row["last_practiced_at"],
            "practiced_today": practiced_today,
            "projects": projects.get(row["id"], []),
        }
        rows.append(item)
        if record_level:
            tracked.append(item)
            if practiced_today:
                practiced.append(item)
        else:
            unpracticed += 1
    average = round(sum(item["score"] for item in tracked) / len(tracked), 1) if tracked else None
    today_average = round(sum(item["score"] for item in practiced) / len(practiced), 1) if practiced else None

    gap_sql = f"""
        SELECT s.id, s.knowledge_id, kp.title, s.missing, s.wrong, s.overall, s.created_at
        FROM answer_scores s
        JOIN knowledge_points kp ON kp.id = s.knowledge_id
        JOIN sessions se ON se.id = s.session_id
        WHERE s.created_at >= ? AND s.created_at < ?
          AND (s.missing != '' OR s.overall < 60)
          {project_clause}
        ORDER BY s.overall ASC
        LIMIT 20
    """
    gaps = fetchall(gap_sql, (start, end, *project_params))
    reminders = list_reminders("due")["items"]
    if project_id:
        reminders = [item for item in reminders if item["project_id"] in (None, project_id) or any(
            project["id"] == project_id for project in projects.get(item["knowledge_id"], [])
        )]
    return {
        "today": now().date().isoformat(),
        "timezone": "Asia/Shanghai",
        "practice": {"sessions": sessions, "answers": answers, "points": points_today},
        "mastery_today": {"average": today_average, "distribution": _distribution(practiced)},
        "mastery_global": {
            "average": average,
            "tracked": len(tracked),
            "unpracticed": unpracticed,
            "distribution": _distribution(tracked),
        },
        "rows": rows,
        "gaps": gaps,
        "history": _history_query("time", "desc", project_id, 8),
        "reminders": reminders,
        "llm": llm_enabled(),
    }


def history(sort: str, order: str, project_id: str | None, limit: int) -> dict:
    if project_id:
        _require_project(project_id)
    return {"items": _history_query(sort, order, project_id, limit)}


def review_items(filter_name: str, project_id: str | None) -> dict:
    if project_id:
        _require_project(project_id)
    projects = _projects_by_knowledge()
    rows = fetchall(
        """
        SELECT kp.id AS knowledge_id, kp.title, m.score, m.level, m.last_practiced_at,
               m.next_review_at, m.review_count
        FROM knowledge_points kp
        LEFT JOIN mastery m ON m.knowledge_id = kp.id
        ORDER BY kp.title
        """
    )
    items = []
    counts = {"due": 0, "overdue": 0, "today": 0, "upcoming": 0, "unscheduled": 0, "all": 0}
    allowed = {"due", "overdue", "today", "upcoming", "unscheduled", "all"}
    if filter_name not in allowed:
        filter_name = "due"
    for row in rows:
        attached = projects.get(row["knowledge_id"], [])
        if not attached:
            continue
        if project_id and all(project["id"] != project_id for project in attached):
            continue
        status = review_status(row["next_review_at"])
        counts["all"] += 1
        if status == "unscheduled":
            counts["unscheduled"] += 1
        elif status == "overdue":
            counts["overdue"] += 1
            counts["due"] += 1
        elif status == "today":
            counts["today"] += 1
            counts["due"] += 1
        else:
            counts["upcoming"] += 1
        if filter_name == "due" and status not in {"overdue", "today"}:
            continue
        if filter_name not in {"due", "all"} and status != filter_name:
            continue
        items.append(
            {
                "knowledge_id": row["knowledge_id"],
                "title": row["title"],
                "score": row["score"],
                "level": row["level"],
                "last_practiced_at": row["last_practiced_at"],
                "next_review_at": row["next_review_at"],
                "review_count": row["review_count"] or 0,
                "status": status,
                "days_until": days_until(row["next_review_at"]),
                "projects": attached,
            }
        )
    items.sort(key=lambda item: (item["next_review_at"] is None, item["next_review_at"] or "", item["title"]))
    return {"items": items, "counts": counts, "filter": filter_name, "today": now().date().isoformat()}


def list_reminders(scope: str) -> dict:
    _start, end = today_bounds()
    sql = """
        SELECT r.id, r.knowledge_id, r.project_id, r.kind, r.message, r.due_at, r.created_at, kp.title
        FROM reminders r
        JOIN knowledge_points kp ON kp.id = r.knowledge_id
        WHERE r.dismissed_at IS NULL
    """
    params: list = []
    if scope != "open":
        sql += " AND r.due_at < ?"
        params.append(end)
    sql += " ORDER BY r.due_at, r.created_at"
    return {"items": fetchall(sql, params)}


def dismiss_reminder(reminder_id: str) -> dict:
    with db() as conn:
        row = one(conn, "SELECT id FROM reminders WHERE id = ?", (reminder_id,))
        if not row:
            raise AppError(404, "这条提醒不存在")
        conn.execute("UPDATE reminders SET dismissed_at = ? WHERE id = ?", (iso(now()), reminder_id))
    return {"ok": True}
