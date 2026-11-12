from __future__ import annotations

from .clock import at_hour, iso, now
from .db import db

DEMO_PROJECTS = [
    {
        "id": "proj-ai-pm",
        "name": "AI 产品经理",
        "description": "面向知识工作者的智能体功能。重点是任务边界、工具、上下文和评测，而不是把对话轮数做高。",
        "jd_text": (
            "我们在找一位 AI 产品经理，负责面向知识工作者的智能体功能。\n"
            "你要定义 Agent 的任务边界、工具调用方式（包括 MCP）、上下文怎么放进每一轮，以及评测和标注方案。\n"
            "资料会更新，需要检索知识库，而不是把所有文档塞进提示词。\n"
            "成功标准不是聊了多少轮，而是任务是否完成、用户是否信任反馈。请准备产品指标，而不是只报使用次数。\n"
            "你会和工程一起决定哪些步骤自动执行，哪些必须 human-in-the-loop。\n"
            "请准备一个你亲自做过的 AI 功能：需求定义怎么写、失败时长什么样。"
        ),
        "created_at": "2026-11-12T09:00:01+08:00",
    },
    {
        "id": "proj-ai-fe",
        "name": "AI Native 前端",
        "description": "把面试对话做成流式、可取消、工具状态可见的界面，评分写回要幂等。",
        "jd_text": (
            "负责 AI Native 前端。面试对话要做流式渲染，生成过程可以取消，工具调用的状态要对候选人可见。\n"
            "评分写回必须幂等：请求超时后先查询，再决定要不要重试。\n"
            "你会验收空状态、错误态和很长的回答。\n"
            "需要理解 MCP 和工具调用的基本模型，并把 Agent 状态映射成界面，而不是把 JSON 直接甩给用户。"
        ),
        "created_at": "2026-11-12T09:00:00+08:00",
    },
]


def seed_demo_projects() -> None:
    timestamp = iso(now())
    with db() as conn:
        for project in DEMO_PROJECTS:
            conn.execute(
                """
                INSERT OR IGNORE INTO projects(id, name, description, jd_text, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project["id"],
                    project["name"],
                    project["description"],
                    project["jd_text"],
                    project["created_at"],
                    timestamp,
                ),
            )


def seed_demo_progress() -> None:
    """First launch only: a due weak point, a medium point, and one mastered point."""
    with db() as conn:
        existing = conn.execute("SELECT COUNT(*) AS n FROM mastery").fetchone()["n"]
        if existing:
            return
        samples = [
            ("kp-eval", 42, "weak", 1, at_hour(-1, 15), at_hour(0, 9), "proj-ai-pm"),
            ("kp-rag", 70, "medium", 1, at_hour(-1, 11), at_hour(4, 9), "proj-ai-pm"),
            ("kp-streaming-ui", 86, "mastered", 2, at_hour(-6, 16), at_hour(8, 9), "proj-ai-fe"),
        ]
        for knowledge_id, score, level, reviews, last_at, next_at, _project_id in samples:
            if not conn.execute("SELECT 1 FROM knowledge_points WHERE id = ?", (knowledge_id,)).fetchone():
                continue
            conn.execute(
                """
                INSERT INTO mastery(
                  knowledge_id, score, level, review_count, last_practiced_at, next_review_at, last_session_id
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (knowledge_id, score, level, reviews, last_at, next_at),
            )
        if conn.execute("SELECT COUNT(*) AS n FROM reminders").fetchone()["n"]:
            return
        reminders = [
            (
                "rem_seed_eval",
                "kp-eval",
                "proj-ai-pm",
                "gap",
                "「评测与标注」还停在感觉像不像标准答案。今天先把评分维度、锚点例和回归集讲出来。",
                at_hour(0, 9),
            ),
            (
                "rem_seed_rag",
                "kp-rag",
                "proj-ai-pm",
                "schedule",
                f"「RAG 与知识库」计划在 {at_hour(4, 9)[:10]} 复习。上次是熟悉中（70）。请准备一个检索错了怎么办的例子。",
                at_hour(4, 9),
            ),
            (
                "rem_seed_stream",
                "kp-streaming-ui",
                "proj-ai-fe",
                "schedule",
                f"「流式生成界面」已掌握（86）。{at_hour(8, 9)[:10]} 做一次低频率复习，重点讲取消请求和过期响应。",
                at_hour(8, 9),
            ),
        ]
        created = iso(now())
        for reminder_id, knowledge_id, project_id, kind, message, due_at in reminders:
            if not conn.execute("SELECT 1 FROM knowledge_points WHERE id = ?", (knowledge_id,)).fetchone():
                continue
            conn.execute(
                """
                INSERT INTO reminders(id, knowledge_id, project_id, kind, message, due_at, created_at, dismissed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (reminder_id, knowledge_id, project_id, kind, message, due_at, created),
            )
