from __future__ import annotations

import json
import secrets
from collections import defaultdict

from .clock import LEVEL_LABEL, at_hour, iso, now, today_bounds
from .db import db, fetchall, fetchone, hydrate_kp, many, one
from .errors import AppError
from .llm import complete_json, llm_enabled
from .scoring import blend_score, level_for, review_interval_days, score_answer

MASTERED = {"mastered", "fluent"}


def _new_id(prefix: str) -> str:
    return prefix + secrets.token_hex(4)


def _mastery_map(conn, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = many(conn, f"SELECT * FROM mastery WHERE knowledge_id IN ({marks})", ids)
    return {row["knowledge_id"]: row for row in rows}


def _points_for_project(conn, project_id: str) -> list[dict]:
    rows = many(
        conn,
        """
        SELECT kp.* FROM knowledge_points kp
        JOIN project_knowledge pk ON pk.knowledge_id = kp.id
        WHERE pk.project_id = ?
        ORDER BY kp.title
        """,
        (project_id,),
    )
    return [hydrate_kp(row) for row in rows]


def _due(mastery: dict | None) -> bool:
    if not mastery or not mastery.get("next_review_at"):
        return False
    _start, end = today_bounds()
    return mastery["next_review_at"] < end


def _sort_key(point: dict, mastery: dict[str, dict]):
    record = mastery.get(point["id"])
    if record and _due(record) and record["level"] not in MASTERED:
        return (0, record["score"], point["title"])
    if not record:
        return (1, 0, point["title"])
    return (2, record["score"], point["title"])


def _reason(point: dict, mastery: dict[str, dict]) -> str:
    record = mastery.get(point["id"])
    if not record:
        return "还没练过"
    if _due(record) and record["level"] not in MASTERED:
        return "到了复习时间"
    if record["level"] == "weak":
        return "掌握度偏低"
    return "继续巩固"


def _brief(point: dict, mastery: dict[str, dict]) -> dict:
    record = mastery.get(point["id"])
    return {
        "id": point["id"],
        "title": point["title"],
        "reason": _reason(point, mastery),
        "level": record["level"] if record else None,
        "score": record["score"] if record else None,
    }


def build_plan(project_id: str, knowledge_ids: list[str] | None = None, mode: str = "mock") -> dict:
    with db() as conn:
        project = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
        if not project:
            raise AppError(404, "项目不存在")
        points = _points_for_project(conn, project_id)
        if knowledge_ids:
            by_id = {point["id"]: point for point in points}
            missing = [item for item in knowledge_ids if item not in by_id]
            if missing:
                raise AppError(400, "这些知识点不在该项目里：" + "、".join(missing))
            points = [by_id[item] for item in knowledge_ids]
        mastery = _mastery_map(conn, [point["id"] for point in points])
    skipped = []
    chosen = points
    if mode == "mock":
        chosen = []
        for point in points:
            record = mastery.get(point["id"])
            if record and record["level"] in MASTERED:
                skipped.append(point)
            else:
                chosen.append(point)
        chosen.sort(key=lambda point: _sort_key(point, mastery))
        if not knowledge_ids:
            chosen = chosen[:3]
    return {
        "points": [_brief(point, mastery) for point in chosen],
        "skipped_mastered": [_brief(point, mastery) for point in skipped],
        "notice": "已掌握或熟练的知识点不会在别的项目里重复开考，只在到期复习时出现。" if skipped else "",
    }


def _question(point: dict, index: int = 0) -> str:
    questions = point.get("questions") or []
    if index < len(questions):
        return questions[index]
    return f"请解释「{point['title']}」的机制，补上边界，并举一个你会怎么用的例子。"


def _opening(style: str, project_name: str, question: str) -> str:
    if style == "strict":
        lead = (
            f"我是今天的面试官，我们按「{project_name}」的要求来。"
            "请讲机制、边界和你自己的取舍，不要背定义。"
        )
    else:
        lead = (
            f"我们按「{project_name}」做一轮模拟面试。"
            "你按真实经历讲就好，我说完会根据你的回答追问一层。"
        )
    return f"{lead}\n\n{question}"


def _bridge(style: str, question: str) -> str:
    if style == "strict":
        return f"下一题。仍然要讲清楚机制。\n\n{question}"
    return f"我们换一个点。\n\n{question}"


def _closing(style: str) -> str:
    if style == "strict":
        return (
            "提问到这里。结束本轮后我会按相关性、正确性、完整度、推理四项给分，"
            "并写入这个知识点的全局掌握度。薄弱项会在一两天内回到复习表；"
            "已经掌握的点，其他项目的模拟面试不再重复出题。"
        )
    return (
        "这一轮可以收了。结束后你会看到四项分数、漏掉的要点，以及下一次复习时间。"
        "掌握度记在知识点上，不按项目各记一份。"
    )


def _scripted_followup(style: str, point: dict, preview: dict) -> str:
    missing = preview.get("missing_keywords") or []
    if missing and preview.get("coverage", 1) < 0.45:
        keyword = missing[0]
        if style == "strict":
            return (
                f"先停在这里。你还没说明「{keyword}」。"
                "请只补这一处：它在流程里由谁产生、谁消费，什么情况下会失败？"
            )
        return f"方向有了。把「{keyword}」说具体一点，最好带一个你自己的例子。"
    deeper = _question(point, 1)
    if style == "strict":
        return f"基本机制你说到了。我要一个更紧的追问：\n\n{deeper}"
    return f"这部分清楚了。我想再往下挖一层：\n\n{deeper}"


def _llm_followup(style: str, point: dict, answer: str) -> str | None:
    persona = "严格、短、追问缺口" if style == "strict" else "宽松、具体、鼓励后追问一层"
    data = complete_json(
        "你是中文面试官。只输出 JSON：{\"text\": \"一句到三句追问\"}。不要给标准答案，不要寒暄。",
        (
            f"风格：{persona}\n知识点：{point['title']}\n提纲：{point.get('outline') or ''}\n"
            f"关键词：{'、'.join(point.get('keywords') or [])}\n候选人回答：{answer}"
        ),
    )
    if not data:
        return None
    text = str(data.get("text") or "").strip()
    return text or None


def _llm_score(answer: str, point: dict) -> dict | None:
    data = complete_json(
        (
            "你是面试评分员。只输出 JSON，字段 relevance, correctness, completeness, reasoning "
            "为 0 到 100 的数字，wrong、missing、better 为简短中文。"
            "wrong 只写明确说错的地方，没有就留空。不要客套。"
        ),
        (
            f"知识点：{point['title']}\n关键词：{'、'.join(point.get('keywords') or [])}\n"
            f"参考提纲：{point.get('outline') or ''}\n候选人回答：{answer}"
        ),
    )
    if not data:
        return None
    try:
        dims = {key: round(max(0.0, min(100.0, float(data[key]))), 1) for key in (
            "relevance", "correctness", "completeness", "reasoning"
        )}
    except (KeyError, TypeError, ValueError):
        return None
    overall = round(sum(dims.values()) / 4, 1)
    return {
        **dims,
        "overall": overall,
        "wrong": str(data.get("wrong") or "")[:400],
        "missing": str(data.get("missing") or "")[:400],
        "better": str(data.get("better") or point.get("outline") or "")[:800],
    }


def _score(answer: str, point: dict) -> dict:
    base = score_answer(answer, point)
    if not llm_enabled():
        return base
    judged = _llm_score(answer, point)
    if not judged:
        return base
    judged["missing_keywords"] = base["missing_keywords"]
    judged["coverage"] = base["coverage"]
    if not judged["better"]:
        judged["better"] = base["better"]
    return judged


def _insert_message(conn, session_id: str, role: str, content: str, knowledge_id: str | None, kind: str, modality: str = "text") -> dict:
    message_id = _new_id("msg_")
    conn.execute(
        """
        INSERT INTO messages(id, session_id, role, content, knowledge_id, kind, modality, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, session_id, role, content, knowledge_id, kind, modality, iso(now())),
    )
    return one(conn, "SELECT * FROM messages WHERE id = ?", (message_id,))


def _load_point(conn, knowledge_id: str | None) -> dict | None:
    if not knowledge_id:
        return None
    return hydrate_kp(one(conn, "SELECT * FROM knowledge_points WHERE id = ?", (knowledge_id,)))


def start_session(project_id: str, style: str, mode: str, knowledge_ids: list[str] | None) -> str:
    ids = list(knowledge_ids or [])
    if mode == "review" and not ids:
        _start, end = today_bounds()
        rows = fetchall(
            """
            SELECT m.knowledge_id FROM mastery m
            JOIN project_knowledge pk ON pk.knowledge_id = m.knowledge_id
            WHERE pk.project_id = ? AND m.next_review_at IS NOT NULL AND m.next_review_at < ?
            ORDER BY m.next_review_at
            """,
            (project_id, end),
        )
        ids = [row["knowledge_id"] for row in rows][:4]
        if not ids:
            raise AppError(400, "这个项目今天没有到期的复习。")
    plan = build_plan(project_id, ids or None, mode)
    if not plan["points"]:
        if mode == "mock" and ids:
            raise AppError(400, "这些知识点已经掌握，模拟面试不会重复出题。请到今日复习，到期后再练。")
        if mode == "mock":
            raise AppError(400, "这个项目里还没有可考察的未掌握知识点。已掌握的内容会在到期后出现在今日复习。")
        raise AppError(400, "没有可复习的知识点。")
    queue = [point["id"] for point in plan["points"]]
    session_id = _new_id("ses_")
    with db() as conn:
        project = one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
        first = _load_point(conn, queue[0])
        conn.execute(
            """
            INSERT INTO sessions(
              id, project_id, style, mode, status, queue_json, cursor_idx,
              followup_stage, current_knowledge_id, created_at, finished_at
            ) VALUES (?, ?, ?, ?, 'active', ?, 0, 0, ?, ?, NULL)
            """,
            (session_id, project_id, style, mode, json.dumps(queue), queue[0], iso(now())),
        )
        _insert_message(
            conn,
            session_id,
            "interviewer",
            _opening(style, project["name"], _question(first)),
            queue[0],
            "question",
        )
    return session_id


def submit_turn(session_id: str, content: str, modality: str) -> None:
    content = content.strip()
    if not content:
        raise AppError(400, "先写一点回答，再发送。")
    if len(content) > 8000:
        raise AppError(400, "回答太长了，请压到 8000 字以内。")
    if modality not in ("text", "voice"):
        raise AppError(400, "modality 只能是 text 或 voice")
    with db() as conn:
        session = one(conn, "SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not session:
            raise AppError(404, "这场面试不存在")
        if session["status"] == "finished":
            raise AppError(400, "本轮已经结束，可以回看板看分数。")
        if session["status"] == "ready":
            raise AppError(400, "问题已经问完。请结束并评分。")
        point = _load_point(conn, session["current_knowledge_id"])
        if not point:
            raise AppError(400, "当前题目丢失了，请重新开始一场面试。")
        _insert_message(conn, session_id, "candidate", content, point["id"], "answer", modality)
        queue = json.loads(session["queue_json"])
        if session["followup_stage"] == 0:
            preview = score_answer(content, point)
            follow = _llm_followup(session["style"], point, content) or _scripted_followup(session["style"], point, preview)
            conn.execute("UPDATE sessions SET followup_stage = 1 WHERE id = ?", (session_id,))
            _insert_message(conn, session_id, "interviewer", follow, point["id"], "followup")
            return
        cursor = session["cursor_idx"] + 1
        if cursor >= len(queue):
            conn.execute(
                """
                UPDATE sessions
                SET followup_stage = 0, cursor_idx = ?, status = 'ready'
                WHERE id = ?
                """,
                (cursor, session_id),
            )
            _insert_message(conn, session_id, "interviewer", _closing(session["style"]), None, "closing")
            return
        nxt = _load_point(conn, queue[cursor])
        conn.execute(
            """
            UPDATE sessions
            SET followup_stage = 0, cursor_idx = ?, current_knowledge_id = ?
            WHERE id = ?
            """,
            (cursor, nxt["id"], session_id),
        )
        _insert_message(
            conn,
            session_id,
            "interviewer",
            _bridge(session["style"], _question(nxt)),
            nxt["id"],
            "question",
        )


def _refresh_reminders(conn, point: dict, project_id: str | None, mastery: dict, missing: str) -> None:
    conn.execute(
        "DELETE FROM reminders WHERE knowledge_id = ? AND dismissed_at IS NULL",
        (point["id"],),
    )
    label = LEVEL_LABEL.get(mastery["level"], mastery["level"])
    when = mastery["next_review_at"][:10]
    conn.execute(
        """
        INSERT INTO reminders(id, knowledge_id, project_id, kind, message, due_at, created_at, dismissed_at)
        VALUES (?, ?, ?, 'schedule', ?, ?, ?, NULL)
        """,
        (
            _new_id("rem_"),
            point["id"],
            project_id,
            f"「{point['title']}」计划在 {when} 复习。当前是{label}（{mastery['score']}）。用一个例子把机制讲完整。",
            mastery["next_review_at"],
            iso(now()),
        ),
    )
    if missing:
        conn.execute(
            """
            INSERT INTO reminders(id, knowledge_id, project_id, kind, message, due_at, created_at, dismissed_at)
            VALUES (?, ?, ?, 'gap', ?, ?, ?, NULL)
            """,
            (
                _new_id("rem_"),
                point["id"],
                project_id,
                f"关于「{point['title']}」，{missing}下一答先补这几处。",
                at_hour(0, 9),
                iso(now()),
            ),
        )


def finish_session(session_id: str) -> None:
    with db() as conn:
        session = one(conn, "SELECT * FROM sessions WHERE id = ?", (session_id,))
        if not session:
            raise AppError(404, "这场面试不存在")
        if session["status"] == "finished":
            return
        messages = many(
            conn,
            "SELECT * FROM messages WHERE session_id = ? ORDER BY seq",
            (session_id,),
        )
        prompt = ""
        grouped: dict[str, list[float]] = defaultdict(list)
        missing_by_point: dict[str, list[str]] = defaultdict(list)
        for message in messages:
            if message["role"] == "interviewer":
                prompt = message["content"]
                continue
            if message["role"] != "candidate" or not message["knowledge_id"]:
                continue
            point = _load_point(conn, message["knowledge_id"])
            if not point:
                continue
            judged = _score(message["content"], point)
            conn.execute(
                """
                INSERT INTO answer_scores(
                  id, session_id, message_id, knowledge_id, prompt, relevance, correctness,
                  completeness, reasoning, overall, wrong, missing, better, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id("sco_"),
                    session_id,
                    message["id"],
                    point["id"],
                    prompt[:500],
                    judged["relevance"],
                    judged["correctness"],
                    judged["completeness"],
                    judged["reasoning"],
                    judged["overall"],
                    judged["wrong"],
                    judged["missing"],
                    judged["better"],
                    iso(now()),
                ),
            )
            grouped[point["id"]].append(judged["overall"])
            if judged["missing"]:
                missing_by_point[point["id"]].append(judged["missing"])
        for knowledge_id, scores in grouped.items():
            point = _load_point(conn, knowledge_id)
            session_score = round(sum(scores) / len(scores), 1)
            previous = one(conn, "SELECT * FROM mastery WHERE knowledge_id = ?", (knowledge_id,))
            score = blend_score(previous["score"] if previous else None, session_score)
            level = level_for(score)
            count = (previous["review_count"] if previous else 0) + 1
            review_at = at_hour(review_interval_days(score), 9)
            practiced = iso(now())
            if previous:
                conn.execute(
                    """
                    UPDATE mastery
                    SET score = ?, level = ?, review_count = ?, last_practiced_at = ?,
                        next_review_at = ?, last_session_id = ?
                    WHERE knowledge_id = ?
                    """,
                    (score, level, count, practiced, review_at, session_id, knowledge_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO mastery(
                      knowledge_id, score, level, review_count, last_practiced_at, next_review_at, last_session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (knowledge_id, score, level, count, practiced, review_at, session_id),
                )
            mastery = {
                "score": score,
                "level": level,
                "next_review_at": review_at,
            }
            missing = " ".join(dict.fromkeys(missing_by_point.get(knowledge_id, [])))
            _refresh_reminders(conn, point, session["project_id"], mastery, missing)
        conn.execute(
            "UPDATE sessions SET status = 'finished', finished_at = ? WHERE id = ?",
            (iso(now()), session_id),
        )


def _mean(rows: list[dict], key: str) -> float:
    return round(sum(row[key] for row in rows) / len(rows), 1)


def build_report(session_id: str) -> dict | None:
    scores = fetchall(
        """
        SELECT s.*, kp.title, m.content AS answer
        FROM answer_scores s
        JOIN knowledge_points kp ON kp.id = s.knowledge_id
        JOIN messages m ON m.id = s.message_id
        WHERE s.session_id = ?
        ORDER BY s.created_at
        """,
        (session_id,),
    )
    if not scores:
        return {"averages": None, "answers": [], "by_point": []}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in scores:
        grouped[row["knowledge_id"]].append(row)
    by_point = []
    for knowledge_id, rows in grouped.items():
        mastery = fetchone("SELECT * FROM mastery WHERE knowledge_id = ?", (knowledge_id,))
        wrongs = [row["wrong"] for row in rows if row["wrong"]]
        missings = [row["missing"] for row in rows if row["missing"]]
        by_point.append(
            {
                "knowledge_id": knowledge_id,
                "title": rows[0]["title"],
                "relevance": _mean(rows, "relevance"),
                "correctness": _mean(rows, "correctness"),
                "completeness": _mean(rows, "completeness"),
                "reasoning": _mean(rows, "reasoning"),
                "overall": _mean(rows, "overall"),
                "wrong": " ".join(dict.fromkeys(wrongs)),
                "missing": " ".join(dict.fromkeys(missings)),
                "better": rows[-1]["better"],
                "mastery": mastery,
            }
        )
    return {
        "averages": {
            "relevance": _mean(scores, "relevance"),
            "correctness": _mean(scores, "correctness"),
            "completeness": _mean(scores, "completeness"),
            "reasoning": _mean(scores, "reasoning"),
            "overall": _mean(scores, "overall"),
        },
        "answers": [
            {
                "id": row["id"],
                "knowledge_id": row["knowledge_id"],
                "title": row["title"],
                "prompt": row["prompt"],
                "answer": row["answer"],
                "relevance": row["relevance"],
                "correctness": row["correctness"],
                "completeness": row["completeness"],
                "reasoning": row["reasoning"],
                "overall": row["overall"],
                "wrong": row["wrong"],
                "missing": row["missing"],
                "better": row["better"],
            }
            for row in scores
        ],
        "by_point": by_point,
    }


def present_session(session_id: str) -> dict:
    session = fetchone("SELECT * FROM sessions WHERE id = ?", (session_id,))
    if not session:
        raise AppError(404, "这场面试不存在")
    project = fetchone("SELECT id, name FROM projects WHERE id = ?", (session["project_id"],))
    messages = fetchall(
        "SELECT id, role, content, knowledge_id, kind, modality, created_at FROM messages WHERE session_id = ? ORDER BY seq",
        (session_id,),
    )
    current = hydrate_kp(fetchone("SELECT * FROM knowledge_points WHERE id = ?", (session["current_knowledge_id"],)))
    queue_ids = json.loads(session["queue_json"])
    queue = []
    for knowledge_id in queue_ids:
        row = fetchone("SELECT id, title FROM knowledge_points WHERE id = ?", (knowledge_id,))
        queue.append({"id": knowledge_id, "title": row["title"] if row else knowledge_id})
    report = None
    if session["status"] == "finished" or fetchone(
        "SELECT 1 AS ok FROM answer_scores WHERE session_id = ? LIMIT 1", (session_id,)
    ):
        report = build_report(session_id)
    current_public = None
    if current:
        current_public = {
            "id": current["id"],
            "title": current["title"],
            "outline": current["outline"],
            "aliases": current["aliases"],
        }
    return {
        "id": session["id"],
        "project": project,
        "style": session["style"],
        "mode": session["mode"],
        "status": session["status"],
        "queue": queue,
        "cursor_idx": session["cursor_idx"],
        "followup_stage": session["followup_stage"],
        "current_point": current_public,
        "messages": messages,
        "report": report,
        "created_at": session["created_at"],
        "finished_at": session["finished_at"],
        "llm": llm_enabled(),
    }
