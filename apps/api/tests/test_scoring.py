import pytest

from app.scoring import level_for, review_interval_days, score_answer


@pytest.mark.parametrize(
    ("score", "level", "days"),
    [
        (0, "weak", 1),
        (44.9, "weak", 1),
        (45, "weak", 2),
        (54.9, "weak", 2),
        (55, "medium", 3),
        (64.9, "medium", 3),
        (65, "medium", 5),
        (74.9, "medium", 5),
        (75, "mastered", 7),
        (81.9, "mastered", 7),
        (82, "mastered", 14),
        (89.9, "mastered", 14),
        (90, "fluent", 21),
        (94.9, "fluent", 21),
        (95, "fluent", 30),
        (100, "fluent", 30),
    ],
)
def test_schedule_bands(score, level, days):
    assert level_for(score) == level
    assert review_interval_days(score) == days


def test_outline_can_pass_and_give_up_stays_weak():
    point = {
        "title": "Agent Loop（代理循环）",
        "aliases": ["代理循环"],
        "keywords": ["观察", "推理", "行动", "工具", "停止条件", "状态", "循环"],
        "outline": (
            "Agent Loop 是把观察、推理、行动串成循环，行动常常是调用工具，并把新的结果写回状态。"
            "因为没有停止条件，所以循环会一直转。例如步数上限。如果失败，首先保留路径，然后告诉用户。"
        ),
    }
    rich = score_answer(point["outline"], point)
    assert rich["overall"] >= 75
    weak = score_answer("不知道", point)
    assert weak["overall"] < 55
    assert weak["wrong"]
