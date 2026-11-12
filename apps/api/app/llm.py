from __future__ import annotations

import json
import logging
import os
import re
import urllib.request

log = logging.getLogger("interview_agent")


def load_dotenv() -> None:
    from .db import repo_root

    path = repo_root() / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_key() -> str:
    return os.getenv("OPENAI_API_KEY") or os.getenv("INTERVIEW_LLM_API_KEY") or ""


def llm_enabled() -> bool:
    if os.getenv("INTERVIEW_AGENT_DISABLE_LLM") == "1":
        return False
    return bool(api_key())


def search_enabled() -> bool:
    if os.getenv("INTERVIEW_AGENT_DISABLE_SEARCH") == "1":
        return False
    return bool(os.getenv("TAVILY_API_KEY"))


def _parse_json(content: str) -> dict | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def complete_json(system: str, user: str) -> dict | None:
    if not llm_enabled():
        return None
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return _parse_json(content)
    except Exception as exc:  # network, auth, or a non-JSON reply
        log.warning("LLM call failed, using the scripted interviewer: %s", exc)
        return None


def tavily_search(query: str) -> list[dict] | None:
    """None means search is not configured. An empty list means it ran and found nothing."""
    if not search_enabled():
        return None
    key = os.getenv("TAVILY_API_KEY", "")
    payload = {
        "api_key": key,
        "query": query[:400],
        "search_depth": "basic",
        "max_results": 3,
    }
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        log.warning("Tavily search failed: %s", exc)
        return []
    found = []
    for item in data.get("results") or []:
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if title or content:
            found.append({"title": title, "url": item.get("url") or "", "content": content})
    return found
