"""Small, transparent preference model learned from user-edited timelines.

This is not foundation-model training.  It stores explainable editing choices
locally and feeds them back into the next AI planning prompt.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path


def capture_stamp(path: str) -> str:
    name = Path(path or "").name
    match = re.search(r"(\d{8})[_-]?(\d{6})", name)
    return "".join(match.groups()) if match else ""


def timeline_features(clips) -> dict:
    clips = list(clips or [])
    if not clips:
        return {"clip_count": 0, "chronology_ratio": 1.0, "hook_first": False, "avg_clip_duration": 0.0}
    keys = [(capture_stamp(c.path), float(c.start)) for c in clips]
    first_caption = str(getattr(clips[0], "caption", "")).lower()
    result_terms = ("成品", "出锅", "完成", "结果", "试吃", "味道", "payoff", "result", "taste")
    later_stamps = [x[0] for x in keys[1:] if x[0]]
    hook_first = any(x in first_caption for x in result_terms) or bool(keys[0][0] and later_stamps and keys[0][0] > min(later_stamps))
    body = keys[1:] if hook_first else keys
    comparable = [(a, b) for a, b in zip(body, body[1:]) if a[0] and b[0]]
    chronological = sum(a <= b for a, b in comparable)
    ratio = chronological / len(comparable) if comparable else 1.0
    durations = [max(0.0, float(c.end) - float(c.start)) for c in clips]
    fonts = Counter(str(getattr(c, "caption_font", "")) for c in clips if getattr(c, "caption", ""))
    positions = Counter(str(getattr(c, "position", "")) for c in clips if getattr(c, "caption", ""))
    transitions = Counter(str(getattr(c, "transition", "none")) for c in clips[1:])
    return {
        "clip_count": len(clips),
        "chronology_ratio": round(ratio, 4),
        "hook_first": hook_first,
        "avg_clip_duration": round(sum(durations) / len(durations), 3),
        "caption_font": fonts.most_common(1)[0][0] if fonts else "",
        "caption_position": positions.most_common(1)[0][0] if positions else "lower_third",
        "transition": transitions.most_common(1)[0][0] if transitions else "none",
    }


def learn_profile(existing: dict | None, clips) -> dict:
    old = dict(existing or {})
    feature = timeline_features(clips)
    if feature["clip_count"] < 2:
        return old
    samples = max(0, int(old.get("samples", 0)))
    weight = min(samples, 9)
    blend = lambda key, incoming: round((float(old.get(key, incoming)) * weight + float(incoming)) / (weight + 1), 4)
    old.update({
        "version": 1,
        "samples": samples + 1,
        "chronology_strength": blend("chronology_strength", feature["chronology_ratio"]),
        "hook_rate": round((float(old.get("hook_rate", int(feature["hook_first"]))) * weight + int(feature["hook_first"])) / (weight + 1), 4),
        "avg_clip_duration": blend("avg_clip_duration", feature["avg_clip_duration"]),
        "caption_font": feature["caption_font"] or old.get("caption_font", ""),
        "caption_position": feature["caption_position"],
        "transition": feature["transition"],
    })
    return old


def profile_prompt(profile: dict | None) -> str:
    p = profile or {}
    if not p or int(p.get("samples", 0)) <= 0:
        return "个人偏好：尚未学习；优先保证因果完整和真实拍摄顺序。"
    chronology = float(p.get("chronology_strength", 1.0))
    order_rule = "正文严格按真实拍摄顺序，禁止章节回跳" if chronology >= 0.85 else "正文以拍摄顺序为主，只有明确蒙太奇理由才可调整"
    hook_rule = "允许一次结果/高潮冷开场" if float(p.get("hook_rate", 0)) >= 0.5 else "从事件起点直接开始，不强制冷开场"
    return (
        f"个人剪辑偏好（已从{int(p.get('samples', 0))}次人工时间线学习）：{order_rule}；{hook_rule}；"
        f"常用镜头约{float(p.get('avg_clip_duration', 3)):.1f}秒；字幕位置{p.get('caption_position', 'lower_third')}；"
        f"常用字体{p.get('caption_font') or '跟随项目'}；常用转场{p.get('transition', 'none')}。"
    )


def profile_summary(profile: dict | None) -> str:
    p = profile or {}
    if not p or int(p.get("samples", 0)) <= 0:
        return "尚未学习人工时间线"
    return f"已学习 {int(p['samples'])} 次 · 顺序权重 {float(p.get('chronology_strength', 1))*100:.0f}% · 平均镜头 {float(p.get('avg_clip_duration', 0)):.1f}s"
