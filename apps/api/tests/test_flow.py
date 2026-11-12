import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_ROOT))


@pytest.fixture
def client(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    shutil.copytree(REPO_ROOT / "data" / "vault", vault)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VAULT_PATH", str(vault))
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("INTERVIEW_AGENT_DISABLE_LLM", "1")
    monkeypatch.setenv("INTERVIEW_AGENT_DISABLE_SEARCH", "1")
    from app.main import app, bootstrap

    bootstrap()
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_demo_graph(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["llm"] is False
    assert body["knowledge"] >= 15

    projects = client.get("/api/projects").json()["projects"]
    ids = {item["id"] for item in projects}
    assert {"proj-ai-pm", "proj-ai-fe"} <= ids

    graph = client.get("/api/graph", params={"project_id": "proj-ai-pm"}).json()
    edges = {(edge["from_id"], edge["to_id"], edge["relation"]) for edge in graph["edges"]}
    assert ("kp-agent-loop", "kp-context", "prerequisite") in edges
    assert ("kp-skill", "kp-agent-loop", "part_of") in edges

    detail = client.get("/api/knowledge/kp-agent-loop").json()
    assert "kp-context" in {item["id"] for item in detail["relations"]["prerequisite"]}
    assert {item["id"] for item in detail["projects"]} >= {"proj-ai-pm", "proj-ai-fe"}

    reviews = client.get("/api/reviews").json()
    assert "kp-eval" in {item["knowledge_id"] for item in reviews["items"]}
    reminders = client.get("/api/reminders").json()["items"]
    assert any(item["knowledge_id"] == "kp-eval" for item in reminders)

    fe = client.get("/api/projects/proj-ai-fe").json()
    skipped = {item["id"] for item in fe["plan"]["skipped_mastered"]}
    assert "kp-streaming-ui" in skipped


def test_cross_project_mastery_is_global(client, tmp_path):
    outline = client.get("/api/knowledge/kp-agent-loop").json()["outline"]
    started = client.post(
        "/api/sessions",
        json={"project_id": "proj-ai-pm", "style": "strict", "mode": "mock", "knowledge_ids": ["kp-agent-loop"]},
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    turned = client.post(
        f"/api/sessions/{session_id}/turn",
        json={"content": outline, "modality": "voice"},
    )
    assert turned.status_code == 200, turned.text
    assert turned.json()["messages"][-2]["modality"] == "voice"
    finished = client.post(f"/api/sessions/{session_id}/finish")
    assert finished.status_code == 200, finished.text
    again = client.post(f"/api/sessions/{session_id}/finish")
    assert again.status_code == 200

    point = client.get("/api/knowledge/kp-agent-loop").json()
    assert point["mastery"]["level"] in {"mastered", "fluent"}
    assert point["mastery"]["review_count"] == 1

    blocked = client.post(
        "/api/sessions",
        json={"project_id": "proj-ai-fe", "style": "loose", "mode": "mock", "knowledge_ids": ["kp-agent-loop"]},
    )
    assert blocked.status_code == 400

    review = client.post(
        "/api/sessions",
        json={"project_id": "proj-ai-fe", "style": "loose", "mode": "review", "knowledge_ids": ["kp-agent-loop"]},
    )
    assert review.status_code == 200

    fe = client.get("/api/projects/proj-ai-fe").json()
    assert "kp-agent-loop" not in {item["id"] for item in fe["plan"]["points"]}
    assert "kp-agent-loop" in {item["id"] for item in fe["plan"]["skipped_mastered"]}

    import sqlite3

    conn = sqlite3.connect(tmp_path / "app.db")
    count = conn.execute("SELECT COUNT(*) FROM mastery WHERE knowledge_id = 'kp-agent-loop'").fetchone()[0]
    assert count == 1

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["practice"]["answers"] >= 1
    assert dashboard["mastery_today"]["average"] is not None
    assert dashboard["history"]


def test_weak_answer_schedules_soon(client):
    started = client.post(
        "/api/sessions",
        json={"project_id": "proj-ai-pm", "style": "loose", "mode": "mock", "knowledge_ids": ["kp-prd"]},
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    client.post(f"/api/sessions/{session_id}/turn", json={"content": "不知道", "modality": "text"})
    finished = client.post(f"/api/sessions/{session_id}/finish")
    assert finished.status_code == 200
    mastery = client.get("/api/knowledge/kp-prd").json()["mastery"]
    assert mastery["level"] == "weak"
    nxt = datetime.fromisoformat(mastery["next_review_at"])
    assert nxt <= datetime.now(nxt.tzinfo) + timedelta(days=2, hours=2)


def test_create_project_ingest_and_link(client):
    created = client.post(
        "/api/projects",
        json={
            "name": "分布式数据库工程师",
            "description": "负责存储引擎",
            "jd_text": "负责存储引擎的稳定性，处理崩溃恢复。",
            "seed": True,
        },
    )
    assert created.status_code == 200, created.text
    project = created.json()
    assert len(project["knowledge"]) >= 3
    assert any(item["title"].startswith("岗位理解") for item in project["knowledge"])

    upload = client.post(
        "/api/ingest",
        data={"project_id": project["id"]},
        files={"file": ("notes.md", "# 崩溃恢复\n\n先保住已提交的数据，再谈性能。\n\n参见 [[kp-agent-loop]]。\n".encode(), "text/markdown")},
    )
    assert upload.status_code == 200, upload.text
    uploaded_id = upload.json()["created"][0]["id"]
    detail = client.get(f"/api/knowledge/{uploaded_id}").json()
    assert any(item["id"] == "kp-agent-loop" for item in detail["relations"]["related"])

    again = client.post(
        "/api/ingest",
        data={"project_id": project["id"]},
        files={"file": ("notes.md", "# 崩溃恢复\n\n同一标题应更新而不是再造一条。\n".encode(), "text/markdown")},
    )
    assert again.json()["created"][0]["id"] == uploaded_id

    bad_pdf = client.post(
        "/api/ingest",
        data={"project_id": project["id"]},
        files={"file": ("x.pdf", b"%PDF-not-really", "application/pdf")},
    )
    assert bad_pdf.status_code == 400

    linked = client.post(f"/api/projects/{project['id']}/link", json={"knowledge_id": "kp-metrics"})
    assert linked.status_code == 200
    from app.vault import sync_vault

    sync_vault()
    metrics = client.get("/api/knowledge/kp-metrics").json()
    assert project["id"] in {item["id"] for item in metrics["projects"]}
    assert any(item["id"] == "kp-prd" for item in metrics["relations"]["prerequisite"])

    removed = client.delete(f"/api/projects/{project['id']}")
    assert removed.status_code == 200
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert client.get("/api/knowledge/kp-metrics").json()["id"] == "kp-metrics"
