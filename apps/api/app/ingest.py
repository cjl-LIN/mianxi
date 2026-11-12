from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from .clock import iso, now
from .db import fetchall, fetchone, hydrate_kp
from .errors import AppError
from .llm import search_enabled, tavily_search
from .vault import as_text, link_project, projects_of, split_frontmatter, write_knowledge_note

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
TERMS = [
    "用户", "场景", "指标", "边界", "工具", "评测", "模型", "状态", "失败",
    "权限", "检索", "上下文", "需求", "验收", "停止", "循环", "幂等", "流式",
    "职责", "能力", "取舍",
]


def keywords_from(text: str) -> list[str]:
    found: list[str] = []
    for term in TERMS:
        if term in text and term not in found:
            found.append(term)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped[:1] in "-*":
            phrase = stripped.lstrip("-* ").strip()
            if 2 <= len(phrase) <= 18 and phrase not in found:
                found.append(phrase)
    for extra in ("要点", "例子", "边界"):
        if len(found) >= 3:
            break
        if extra not in found:
            found.append(extra)
    return found[:8]


def _split_sections(text: str) -> list[tuple[str, str]]:
    title = None
    buffer: list[str] = []
    chunks: list[tuple[str, str]] = []

    def flush() -> None:
        if title:
            chunks.append((title.strip()[:80], "\n".join(buffer).strip()))

    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            flush()
            title = match.group(2)
            buffer = []
        else:
            buffer.append(line)
    flush()
    usable = [(item_title, body) for item_title, body in chunks if item_title]
    if usable:
        return usable[:30]
    stripped = text.strip()
    if not stripped:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
    if len(paragraphs) <= 1 or len(stripped) < 900:
        first = stripped.splitlines()[0].lstrip("#").strip()[:40] or "导入笔记"
        return [(first, stripped)]
    plain: list[tuple[str, str]] = []
    for index, paragraph in enumerate(paragraphs[:30], start=1):
        heading = paragraph.splitlines()[0].strip()[:40] or f"片段 {index}"
        plain.append((heading, paragraph))
    return plain


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise AppError(400, "这份 PDF 解析失败。可以先导出成 txt 或 md。") from exc


def _note_meta(knowledge_id: str, title: str, body: str, filename: str, project_id: str, extra: dict | None = None) -> dict:
    prior = projects_of(knowledge_id)
    projects = list(dict.fromkeys([*prior, project_id]))
    base = {
        "id": knowledge_id,
        "title": title,
        "aliases": [],
        "tags": ["导入"],
        "projects": projects,
        "sources": [f"upload:{filename}"],
        "created": now().date().isoformat(),
        "prerequisite": [],
        "related": [],
        "part_of": [],
        "keywords": keywords_from(body),
        "questions": [
            f"请解释「{title}」，并举一个你会在面试里怎么讲的例子。",
            "如果面试官追问边界和失败情况，你怎么答？",
        ],
        "outline": " ".join(body.split())[:180] or f"用机制、边界和例子讲清楚「{title}」。",
        "match": [],
        "fallback": False,
    }
    if extra:
        for key, value in extra.items():
            if key == "projects":
                continue
            base[key] = value
        base["projects"] = list(dict.fromkeys([*as_list_text(extra.get("projects")), *projects]))
    return base


def as_list_text(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [as_text(item) for item in value if as_text(item)]
    return [as_text(value)] if as_text(value) else []


def _stable_id(project_id: str, title: str) -> str:
    digest = hashlib.sha1(f"{project_id}:{title}".encode("utf-8")).hexdigest()[:8]
    return f"kp-up-{digest}"


def ingest_file(project_id: str, filename: str, data: bytes) -> dict:
    if not fetchone("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise AppError(404, "项目不存在")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".md", ".markdown", ".txt", ".pdf"}:
        raise AppError(400, "先支持 txt、md 和带文字层的 pdf。")
    if len(data) > 2_000_000:
        raise AppError(400, "文件超过 2MB。")
    if suffix == ".pdf":
        text = _pdf_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    text = text.replace("\x00", "").strip()
    if not text:
        raise AppError(400, "没有从文件里读到文字。扫描版 PDF 需要文字层。")

    meta, body = split_frontmatter(text)
    created = []
    if as_text(meta.get("id")).startswith("kp-") and as_text(meta.get("title")):
        knowledge_id = as_text(meta.get("id"))
        title = as_text(meta.get("title"))
        note = _note_meta(knowledge_id, title, body, filename, project_id, meta)
        note["sources"] = list(dict.fromkeys([*as_list_text(meta.get("sources")), f"upload:{filename}"]))
        write_knowledge_note(note, body, "inbox")
        created.append({"id": knowledge_id, "title": title})
    else:
        content = body if meta else text
        sections = _split_sections(content)
        if not sections:
            raise AppError(400, "文件里没有可以做成知识点的段落。")
        for title, chunk in sections:
            knowledge_id = _stable_id(project_id, title)
            note = _note_meta(knowledge_id, title, chunk or title, filename, project_id)
            write_knowledge_note(note, f"# {title}\n\n{chunk}\n", "inbox")
            created.append({"id": knowledge_id, "title": title})
    return {"created": created, "count": len(created)}


def ensure_role_note(project: dict) -> str:
    knowledge_id = f"kp-role-{project['id']}"
    if fetchone("SELECT id FROM knowledge_points WHERE id = ?", (knowledge_id,)):
        link_project(project["id"], knowledge_id)
        return knowledge_id
    source = f"{project['name']}\n{project['description']}\n{project['jd_text']}"
    keywords = keywords_from(source)
    title = f"岗位理解：{project['name']}"
    outline = (
        f"先概括{project['name']}要交付的结果，再讲两周内准备的三件事。"
        "因为岗位原文比通用套话重要，所以取舍要说出来。例如你会放弃哪一块，以及怎么验收。"
        + ("需要覆盖：" + "、".join(keywords) + "。" if keywords else "")
    )
    jd = project["jd_text"].strip() or "（创建时没有粘贴 JD，只用项目名称建立了这个点。）"
    body = f"# {title}\n\n{project['description']}\n\n## 岗位原文\n\n{jd}\n"
    meta = {
        "id": knowledge_id,
        "title": title,
        "aliases": [],
        "tags": ["岗位"],
        "projects": [project["id"]],
        "sources": ["project:jd"],
        "created": now().date().isoformat(),
        "prerequisite": [],
        "related": [],
        "part_of": [],
        "keywords": keywords,
        "questions": [
            f"请用一两分钟说明「{project['name']}」最看重的能力，以及你准备怎么证明。",
            "如果只能在两周里准备三件事，你会排哪三件？依据是什么，你会放弃什么？",
        ],
        "outline": outline,
        "match": [],
        "fallback": False,
    }
    write_knowledge_note(meta, body, "generated")
    return knowledge_id


def _search_note(project: dict, item: dict) -> dict:
    url = item.get("url") or item.get("title") or iso(now())
    knowledge_id = "kp-search-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    title = (item.get("title") or "检索摘录").strip()[:80]
    content = (item.get("content") or "").strip()
    keywords = keywords_from(f"{title}\n{content}")
    body = f"# {title}\n\n{content}\n\n来源：{url}\n"
    meta = {
        "id": knowledge_id,
        "title": title,
        "aliases": [],
        "tags": ["检索"],
        "projects": list(dict.fromkeys([*projects_of(knowledge_id), project["id"]])),
        "sources": [f"tavily:{url}"],
        "created": now().date().isoformat(),
        "prerequisite": [],
        "related": [],
        "part_of": [],
        "keywords": keywords,
        "questions": [
            f"「{title}」里哪一点你会写进面试回答，哪一点你不采信？",
            "如果这段资料和你的项目经验冲突，你以谁为准？为什么？",
        ],
        "outline": " ".join(content.split())[:180] or title,
        "match": [],
        "fallback": False,
    }
    write_knowledge_note(meta, body, "generated")
    return {"id": knowledge_id, "title": title}


def collect_for_project(project_id: str) -> dict:
    project = fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not project:
        raise AppError(404, "项目不存在")
    haystack = "\n".join([project["name"], project["description"], project["jd_text"]]).lower()
    points = [hydrate_kp(row) for row in fetchall("SELECT * FROM knowledge_points")]
    linked = []
    for point in points:
        if point["fallback"] or point["id"].startswith("kp-role-") or point["id"].startswith("kp-search-"):
            continue
        matched = [term for term in point["match_terms"] if term and term.lower() in haystack]
        if matched:
            link_project(project_id, point["id"])
            linked.append({"id": point["id"], "title": point["title"], "matched": matched})
    role_id = ensure_role_note(project)
    search_added = []
    if search_enabled():
        found = tavily_search(haystack[:300])
        status = "ok" if found else "empty"
        for item in (found or [])[:3]:
            search_added.append(_search_note(project, item))
        message = "已用 Tavily 检索补充材料。" if found else "检索没有返回结果，已保留本地匹配。"
    else:
        status = "skipped"
        message = "未配置 TAVILY_API_KEY，已用本地知识点库。"
    count = fetchone("SELECT COUNT(*) AS n FROM project_knowledge WHERE project_id = ?", (project_id,))["n"]
    fallbacks = []
    if count < 3:
        for point in points:
            if not point["fallback"]:
                continue
            link_project(project_id, point["id"])
            fallbacks.append({"id": point["id"], "title": point["title"]})
            count += 1
            if count >= 3:
                break
    return {
        "linked": linked,
        "role_id": role_id,
        "search": status,
        "search_added": search_added,
        "fallbacks": fallbacks,
        "message": message,
    }
