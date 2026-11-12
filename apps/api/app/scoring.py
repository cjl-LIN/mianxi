from __future__ import annotations


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def level_for(score: float) -> str:
    if score < 55:
        return "weak"
    if score < 75:
        return "medium"
    if score < 90:
        return "mastered"
    return "fluent"


def review_interval_days(score: float) -> int:
    """Weak 1–2 days, medium 3–5, mastered 7–14, fluent 21–30."""
    level = level_for(score)
    if level == "weak":
        return 1 if score < 45 else 2
    if level == "medium":
        return 3 if score < 65 else 5
    if level == "mastered":
        return 7 if score < 82 else 14
    return 21 if score < 95 else 30


def blend_score(old_score: float | None, session_score: float) -> float:
    if old_score is None:
        return round(session_score, 1)
    return round(old_score * 0.45 + session_score * 0.55, 1)


def score_answer(answer: str, kp: dict) -> dict:
    text = (answer or "").strip()
    folded = text.lower()
    keywords = [str(item).strip() for item in (kp.get("keywords") or []) if str(item).strip()]
    hits = [item for item in keywords if item.lower() in folded]
    missing_keywords = [item for item in keywords if item not in hits]
    if keywords:
        coverage = len(hits) / len(keywords)
    else:
        coverage = 0.6 if len(text) >= 40 else 0.25

    names = [kp.get("title") or "", *(kp.get("aliases") or [])]
    title_hit = any(name and str(name).lower() in folded for name in names)
    give_up = any(phrase in text for phrase in ("不知道", "不清楚", "没想过", "不会答", "没准备"))

    relevance = 35 + coverage * 55 + (8 if title_hit else 0)
    correctness = 30 + coverage * 65
    if len(text) < 20:
        length_bonus = 0
    elif len(text) < 70:
        length_bonus = 0.35
    elif len(text) < 160:
        length_bonus = 0.7
    else:
        length_bonus = 1
    completeness = 20 + coverage * 55 + length_bonus * 25
    markers = ("因为", "所以", "如果", "例如", "比如", "首先", "然后", "边界", "取舍", "否则", "一旦", "步骤")
    marker_hits = sum(1 for marker in markers if marker in text)
    reasoning = 25 + min(marker_hits, 4) * 14 + (8 if len(text) >= 80 else 0)

    if len(text) < 12:
        relevance = min(relevance, 25)
        correctness = min(correctness, 25)
        completeness = min(completeness, 20)
        reasoning = min(reasoning, 20)
    if give_up:
        correctness = min(correctness, 35)
        relevance = min(relevance, 40)

    relevance = round(clamp(relevance), 1)
    correctness = round(clamp(correctness), 1)
    completeness = round(clamp(completeness), 1)
    reasoning = round(clamp(reasoning), 1)
    overall = round((relevance + correctness + completeness + reasoning) / 4, 1)

    if give_up:
        wrong = "回答停在「不知道 / 不清楚」，没有给出可以继续追问的机制。"
    elif keywords and coverage < 0.25 and len(text) >= 30:
        wrong = "这段内容和该知识点的关键机制重合很少，像是答到了旁边的话题。"
    else:
        wrong = ""

    missing = ("还没覆盖：" + "、".join(missing_keywords[:5]) + "。") if missing_keywords else ""
    better = (kp.get("outline") or "").strip() or "用「机制 → 边界 → 例子」三步重答一次。"
    return {
        "relevance": relevance,
        "correctness": correctness,
        "completeness": completeness,
        "reasoning": reasoning,
        "overall": overall,
        "wrong": wrong,
        "missing": missing,
        "better": better,
        "missing_keywords": missing_keywords,
        "coverage": coverage,
    }
