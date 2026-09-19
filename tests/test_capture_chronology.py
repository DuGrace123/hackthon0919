"""Regression for the user's real 0307-0313 cooking project.

4.2.1 incorrectly let guessed food stages override DJI capture timestamps.
"""
from ai_story_planner import enforce_continuity


def analyses():
    names = [
        "DJI_20260825045333_0306_D.MP4",
        "DJI_20260825045608_0307_D.MP4",
        "DJI_20260825045819_0308_D.MP4",
        "DJI_20260825050341_0309_D.MP4",
        "DJI_20260825051714_0310_D.MP4",
        "DJI_20260825052108_0311_D.MP4",
        "DJI_20260825052734_0312_D.MP4",
        "DJI_20260825053053_0313_D.MP4",
    ]
    return [
        {"meta": {"name": name, "capture_order": name[4:18]}, "segments": []}
        for name in names
    ]


REAL_BROKEN_ORDER = [
    (6, 58.5, 63.0, "plate", "OK出锅"),
    (2, 0.0, 4.5, "prep", "切葱姜蒜"),
    (4, 2.0, 3.0, "other", "刚刚离开了一下"),
    (1, 7.75, 11.0, "ingredients", "牛排没解冻"),
    (2, 8.5, 12.6, "prep", "切姜"),
    (1, 20.8, 24.0, "ingredients", "解冻"),
    (1, 49.5, 53.0, "prep", "修整牛排"),
    (2, 16.8, 21.5, "prep", "切配"),
    (2, 24.5, 28.2, "prep", "切配"),
    (2, 38.5, 42.0, "prep", "切开"),
    (3, 0.45, 3.2, "prep", "切洋葱"),
    (3, 11.6, 15.1, "prep", "切洋葱"),
    (4, 27.8, 31.8, "cook", "下油"),
    (4, 33.2, 36.8, "cook", "下葱姜蒜"),
    (4, 110.3, 114.0, "cook", "蛋白质变性"),
    (5, 23.5, 26.0, "cook", "倒酱油"),
    (7, 152.4, 156.4, "taste", "试吃"),
]


def sequence():
    result = []
    for i, (source_index, start, end, stage, caption) in enumerate(REAL_BROKEN_ORDER):
        result.append({
            "source_index": source_index,
            "start": start,
            "end": end,
            "stage": stage,
            "role": "hook" if i == 0 else "development",
            "score": 90,
            "motion": 50,
            "caption": caption,
        })
    return result


for round_no in range(1, 6):
    # Also test a short target: reliable DJI timestamps alone must engage the lock.
    for target in (30, 60, 120):
        fixed = enforce_continuity(sequence(), analyses(), "美食教程 · 按拍摄顺序", target)
        assert fixed[0]["source_index"] == 6 and fixed[0]["role"] == "hook"
        keys = [(x["source_index"], x["start"]) for x in fixed[1:]]
        assert keys == sorted(keys), keys
        assert sum(x.get("role") == "hook" for x in fixed) == 1
    print(f"CAPTURE LOCK ROUND {round_no}/5 PASS", flush=True)

print("REAL DJI CAPTURE-ORDER REGRESSION PASS: 5 rounds")
