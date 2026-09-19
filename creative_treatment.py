from __future__ import annotations

import copy


STYLE_PROFILES = {
    "旅行": {"music": "travel_breeze", "accent": "#FFE66D", "font": "站酷快乐体"},
    "美食": {"music": "kitchen_pop", "accent": "#FF8A5B", "font": "站酷快乐体"},
    "生活": {"music": "daily_sunshine", "accent": "#A7F3D0", "font": "站酷快乐体"},
    "剧情": {"music": "story_pulse", "accent": "#FF6B6B", "font": "站酷庆科黄油体"},
    "纪录": {"music": "documentary_air", "accent": "#E2E8F0", "font": "霞鹜文楷"},
    "电影": {"music": "documentary_air", "accent": "#E2E8F0", "font": "霞鹜文楷"},
    "口播": {"music": "clean_focus", "accent": "#7DD3FC", "font": "站酷庆科黄油体"},
}


def _profile(style: str) -> dict:
    text = str(style or "")
    return next((dict(value) for key, value in STYLE_PROFILES.items() if key in text),
                dict(STYLE_PROFILES["生活"]))


def _event(item: dict) -> str:
    text = " ".join(str(item.get(k, "")) for k in ("role", "reason", "caption", "creative_purpose")).lower()
    if item.get("role") == "outro" or any(x in text for x in ("回收", "结尾", "结束", "总结")):
        return "resolution"
    if item.get("role") == "climax" or any(x in text for x in ("结果", "揭示", "成品", "惊喜", "反转", "高潮")):
        return "reveal"
    if any(x in text for x in ("动作", "推进", "移动", "走", "跑", "转身", "运镜", "速度")):
        return "motion"
    if any(x in text for x in ("时间", "回忆", "回溯", "等待", "过去")):
        return "time"
    if any(x in text for x in ("冲突", "障碍", "失败", "危险", "问题")):
        return "conflict"
    if any(x in text for x in ("细节", "食物", "物件", "特写", "人物")):
        return "detail"
    return "chapter" if item.get("role") in ("setup", "development") else "continuity"


def apply_global_creative_treatment(plan: dict, story_style: str = "", density: str = "balanced") -> dict:
    """Create a deterministic, editable full-film sound/effect/music map.

    Strong accents are separated in time and ordinary continuity cuts stay clean.
    The function never reorders decisions, so the capture-order guarantee survives.
    """
    result = copy.deepcopy(plan)
    decisions = result.get("decisions") or []
    profile = _profile(story_style)
    spacing = {"subtle": 14.0, "balanced": 9.0, "energetic": 5.5}.get(density, 9.0)
    cursor = 0.0
    last_accent = -999.0
    cues = list(result.get("sound_cues") or [])
    events = []
    opening_end = max((float(x.get("start", 0)) for x in cues), default=-1.0) + 0.7
    choices = {
        "motion": ("whoosh", "punch_in", "kinetic"),
        "time": ("clock_tick", "slow_push", "typewriter"),
        "conflict": ("bass_drop", "handheld", "stamp"),
        "reveal": ("magic_ding", "punch_in", "jelly"),
        "detail": ("bubble_pop", "slow_push", "pop"),
        "resolution": ("soft_chime", "slow_push", "minimal"),
        "chapter": ("riser", "slow_push", "highlight"),
    }
    for index, item in enumerate(decisions):
        duration = max(0.0, float(item.get("end", 0)) - float(item.get("start", 0)))
        event = _event(item)
        strong = event in choices and cursor >= opening_end and cursor - last_accent >= spacing
        if strong:
            sfx, motion, caption_effect = choices[event]
            volume = .50 if event in ("detail", "time", "resolution") else .62
            cues.append({"effect_id": sfx, "start": round(cursor, 3), "volume": volume,
                         "reason": f"全片事件：{event} · 镜头 {index + 1}"})
            item["motion_effect"] = motion
            item["caption_effect"] = caption_effect
            item["caption_font"] = profile["font"]
            item["caption_color"] = profile["accent"] if caption_effect in ("jelly", "pop", "highlight") else "#FFFFFF"
            if index and item.get("transition", "none") in ("none", "fade", "dissolve"):
                item["transition"] = {"motion": "smooth", "conflict": "tear_left", "reveal": "fade_white",
                                      "time": "dissolve", "detail": "circle", "chapter": "fade_black",
                                      "resolution": "dissolve"}.get(event, item.get("transition", "none"))
            last_accent = cursor
        else:
            item.setdefault("motion_effect", "none")
            item.setdefault("caption_effect", "clean")
        events.append({"ordinal": index, "timeline_start": round(cursor, 3), "duration": round(duration, 3),
                       "event": event, "accent": bool(strong), "motion": item.get("motion_effect", "none"),
                       "caption_effect": item.get("caption_effect", "clean")})
        transition = 0.0 if index == 0 or item.get("transition", "none") == "none" else min(.35, duration * .25)
        cursor += max(.05, duration - transition)
    # Remove accidental collisions while preserving opening cues.
    cues.sort(key=lambda x: float(x.get("start", 0)))
    deduped = []
    for cue in cues:
        if deduped and abs(float(cue.get("start", 0)) - float(deduped[-1].get("start", 0))) < .11:
            if str(cue.get("reason", "")).startswith("开篇"):
                deduped[-1] = cue
            continue
        deduped.append(cue)
    result["sound_cues"] = deduped
    result["global_creative_direction"] = {
        "density": density, "minimum_accent_spacing": spacing, "events": events,
        "accent_count": sum(1 for x in events if x["accent"]),
        "music_id": profile["music"], "music_volume": .20,
        "music_ducking": True, "music_fade_in": 1.0, "music_fade_out": 2.0,
        "font": profile["font"], "accent_color": profile["accent"],
        "rule": "章节、动作峰值、结果揭示和情绪回收才使用强强调；普通因果切点保持干净。",
    }
    return result

