from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .db import fetchone
from .errors import AppError
from .interview import finish_session, present_session, start_session, submit_turn
from .ingest import collect_for_project, ingest_file
from .llm import llm_enabled, load_dotenv, search_enabled
from .queries import (
    create_project,
    dashboard,
    delete_project,
    dismiss_reminder,
    graph,
    history,
    knowledge_detail,
    list_projects,
    list_reminders,
    project_detail,
    review_items,
    search_knowledge,
)
from .seed import seed_demo_progress, seed_demo_projects
from .vault import link_project, sync_vault, unlink_project

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("interview_agent")


def bootstrap() -> None:
    load_dotenv()
    from .db import init_db

    init_db()
    seed_demo_projects()
    synced = sync_vault()
    seed_demo_progress()
    log.info("vault synced: %s notes", synced["notes"])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bootstrap()
    yield


app = FastAPI(title="面习", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def handle_app_error(_request, exc: AppError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.detail})


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    jd_text: str = ""
    seed: bool = True


class LinkIn(BaseModel):
    knowledge_id: str


class SessionIn(BaseModel):
    project_id: str
    style: str = "loose"
    mode: str = "mock"
    knowledge_ids: list[str] = Field(default_factory=list)


class TurnIn(BaseModel):
    content: str
    modality: str = "text"


@app.get("/")
def root():
    return {"app": "面习", "health": "/api/health", "docs": "/docs"}


@app.get("/api/health")
def health():
    projects = fetchone("SELECT COUNT(*) AS n FROM projects")["n"]
    knowledge = fetchone("SELECT COUNT(*) AS n FROM knowledge_points")["n"]
    from .clock import iso, now

    return {
        "ok": True,
        "app": "面习",
        "time": iso(now()),
        "timezone": "Asia/Shanghai",
        "llm": llm_enabled(),
        "search": search_enabled(),
        "projects": projects,
        "knowledge": knowledge,
    }


@app.get("/api/projects")
def get_projects():
    return list_projects()


@app.post("/api/projects")
def post_project(body: ProjectIn):
    return create_project(body.name, body.description, body.jd_text, body.seed)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    return project_detail(project_id)


@app.delete("/api/projects/{project_id}")
def remove_project(project_id: str):
    delete_project(project_id)
    return {"ok": True}


@app.post("/api/projects/{project_id}/collect")
def post_collect(project_id: str):
    return collect_for_project(project_id)


@app.post("/api/projects/{project_id}/link")
def post_link(project_id: str, body: LinkIn):
    if not fetchone("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise AppError(404, "项目不存在")
    if not fetchone("SELECT id FROM knowledge_points WHERE id = ?", (body.knowledge_id,)):
        raise AppError(404, "知识点不存在")
    link_project(project_id, body.knowledge_id)
    return {"ok": True, "project_id": project_id, "knowledge_id": body.knowledge_id}


@app.post("/api/projects/{project_id}/unlink")
def post_unlink(project_id: str, body: LinkIn):
    if not fetchone("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise AppError(404, "项目不存在")
    unlink_project(project_id, body.knowledge_id)
    return {"ok": True}


@app.get("/api/knowledge")
def get_knowledge(q: str = "", project_id: str | None = None, unlinked: int = 0):
    return search_knowledge(q, project_id, bool(unlinked))


@app.get("/api/knowledge/{knowledge_id}")
def get_knowledge_detail(knowledge_id: str):
    return knowledge_detail(knowledge_id)


@app.get("/api/graph")
def get_graph(project_id: str | None = None):
    return graph(project_id)


@app.post("/api/ingest")
async def post_ingest(project_id: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    return ingest_file(project_id, file.filename or "upload.md", data)


@app.post("/api/sessions")
def post_session(body: SessionIn):
    if body.style not in {"strict", "loose"}:
        raise AppError(400, "面试风格只能是 strict 或 loose")
    if body.mode not in {"mock", "review"}:
        raise AppError(400, "模式只能是 mock 或 review")
    session_id = start_session(body.project_id, body.style, body.mode, body.knowledge_ids)
    return present_session(session_id)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    return present_session(session_id)


@app.post("/api/sessions/{session_id}/turn")
def post_turn(session_id: str, body: TurnIn):
    submit_turn(session_id, body.content, body.modality)
    return present_session(session_id)


@app.post("/api/sessions/{session_id}/finish")
def post_finish(session_id: str):
    finish_session(session_id)
    return present_session(session_id)


@app.get("/api/dashboard")
def get_dashboard(project_id: str | None = None):
    return dashboard(project_id)


@app.get("/api/reviews")
def get_reviews(filter: str = "due", project_id: str | None = None):
    return review_items(filter, project_id)


@app.get("/api/history")
def get_history(sort: str = "time", order: str = "desc", project_id: str | None = None, limit: int = 100):
    return history(sort, order, project_id, limit)


@app.get("/api/reminders")
def get_reminders(scope: str = "due"):
    return list_reminders(scope)


@app.post("/api/reminders/{reminder_id}/dismiss")
def post_dismiss(reminder_id: str):
    return dismiss_reminder(reminder_id)
