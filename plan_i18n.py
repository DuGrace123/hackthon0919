"""Language helpers for text the AI planning pipeline writes into plans and reports.

Plans carry their language in ``plan["language"]`` ("zh" by default, "en" for the
English web UI). Every module that writes human-readable text into a plan reads
that key so the whole report, opening presets and repair notes come out in one language.
"""
from __future__ import annotations

LANGUAGES = ("zh", "en")


def normalize_language(value) -> str:
    return "en" if str(value or "").strip().lower().startswith("en") else "zh"


def plan_language(plan: dict | None) -> str:
    return normalize_language((plan or {}).get("language"))


def tr(language: str, zh: str, en: str) -> str:
    return en if normalize_language(language) == "en" else zh


ROLE_LABELS = {
    "zh": {"hook": "冷开场钩子", "setup": "铺垫", "development": "发展", "climax": "高潮", "outro": "收尾", "broll": "空镜"},
    "en": {"hook": "cold open", "setup": "setup", "development": "development", "climax": "climax", "outro": "outro", "broll": "B-roll"},
}

TRANSITION_LABELS = {
    "zh": {"none": "直接切换", "cut": "直接切换", "fade": "淡入淡出", "dissolve": "叠化", "wipe_left": "向左擦除",
           "wipe_right": "向右擦除", "slide_left": "向左滑动", "slide_right": "向右滑动", "circle": "圆形遮罩",
           "smooth": "平滑过渡", "pip_zoom": "画中画推近", "tear_left": "左撕裂", "tear_right": "右撕裂",
           "pixelize": "像素化", "squeeze": "挤压", "radial": "径向", "fade_black": "黑场", "fade_white": "白场",
           "cover_left": "左覆盖", "reveal_right": "右揭示"},
    "en": {"none": "cut", "cut": "cut", "fade": "fade", "dissolve": "dissolve", "wipe_left": "wipe left",
           "wipe_right": "wipe right", "slide_left": "slide left", "slide_right": "slide right", "circle": "circle mask",
           "smooth": "smooth", "pip_zoom": "picture-in-picture zoom", "tear_left": "tear left", "tear_right": "tear right",
           "pixelize": "pixelize", "squeeze": "squeeze", "radial": "radial", "fade_black": "fade to black", "fade_white": "fade to white",
           "cover_left": "cover left", "reveal_right": "reveal right"},
}

# The web UI submits directing styles as their Chinese option values (the planner keys on them).
STYLE_LABELS_EN = {
    "旅行叙事 · 目标—障碍—发现—回收": "Travel story · goal—obstacle—discovery—payoff",
    "美食教程 · 成品钩子后严格按步骤": "Food tutorial · result hook, then strict steps",
    "生活记录 · 小目标与阶段性回报": "Life vlog · small goals and payoffs",
    "剧情短片 · 冲突—尝试—反转—回收": "Short drama · conflict—attempt—twist—payoff",
    "纪录片 · 尊重事件顺序与完整语义": "Documentary · respect event order and meaning",
    "电影感 · 克制转场与留白": "Cinematic · restrained transitions and space",
    "口播知识 · 语义优先并删除停顿": "Talking head · meaning first, cut pauses",
    "旅行叙事": "Travel story", "美食教程": "Food tutorial", "生活记录": "Life vlog", "剧情短片": "Short drama",
    "纪录片": "Documentary", "电影感": "Cinematic", "口播知识": "Talking head",
}


def role_label(language: str, role: str) -> str:
    table = ROLE_LABELS[normalize_language(language)]
    return table.get(str(role or ""), str(role or ""))


def transition_label(language: str, transition: str) -> str:
    table = TRANSITION_LABELS[normalize_language(language)]
    return table.get(str(transition or "none"), str(transition or "none"))


def style_label(language: str, style: str) -> str:
    text = str(style or "")
    return STYLE_LABELS_EN.get(text, text) if normalize_language(language) == "en" else text


def named(language: str, item: dict | None) -> str:
    """Display name of a library entry (music, sound effect) that carries name/name_en."""
    if not item:
        return ""
    if normalize_language(language) == "en":
        return str(item.get("name_en") or item.get("name") or "")
    return str(item.get("name") or "")
