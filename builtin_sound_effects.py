from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


SFX_LIBRARY = [
    {"id": "clock_tick", "name": "机械指针 · 滴", "file": "clock_tick.wav", "category": "节奏", "volume": .72},
    {"id": "clock_tock", "name": "机械指针 · 答", "file": "clock_tock.wav", "category": "节奏", "volume": .72},
    {"id": "whoosh", "name": "轻盈掠过", "file": "whoosh.wav", "category": "转场", "volume": .58},
    {"id": "swipe", "name": "快速滑动", "file": "swipe.wav", "category": "转场", "volume": .62},
    {"id": "paper_tear", "name": "纸张撕裂", "file": "paper_tear.wav", "category": "转场", "volume": .66},
    {"id": "glitch", "name": "数字故障", "file": "glitch.wav", "category": "科技", "volume": .56},
    {"id": "camera", "name": "相机快门", "file": "camera.wav", "category": "生活", "volume": .70},
    {"id": "pop", "name": "清脆弹出", "file": "pop.wav", "category": "轻松", "volume": .62},
    {"id": "sparkle", "name": "闪光星芒", "file": "sparkle.wav", "category": "氛围", "volume": .55},
    {"id": "impact", "name": "电影低频冲击", "file": "impact.wav", "category": "电影", "volume": .64},
    {"id": "riser", "name": "章节上升蓄力", "file": "riser.wav", "category": "叙事", "volume": .54},
    {"id": "bass_drop", "name": "反转低频坠落", "file": "bass_drop.wav", "category": "电影", "volume": .62},
    {"id": "magic_ding", "name": "结果揭晓叮", "file": "magic_ding.wav", "category": "提示", "volume": .56},
    {"id": "bubble_pop", "name": "气泡弹出", "file": "bubble_pop.wav", "category": "轻松", "volume": .58},
    {"id": "soft_chime", "name": "柔和收尾钟声", "file": "soft_chime.wav", "category": "情绪", "volume": .50},
    {"id": "heartbeat", "name": "紧张心跳", "file": "heartbeat.wav", "category": "情绪", "volume": .48},
]


def sfx_by_id(effect_id: str) -> dict | None:
    return next((dict(x) for x in SFX_LIBRARY if x["id"] == effect_id), None)


def resolve_sfx(root: str | Path, effect_id: str) -> str:
    item = sfx_by_id(effect_id)
    return str(Path(root) / "assets" / "sfx" / item["file"]) if item else ""


def _write(path: Path, duration: float, sample_fn):
    rate = 48000; count = max(1, round(duration * rate)); frames = bytearray()
    for i in range(count):
        value = max(-1., min(1., float(sample_fn(i / rate, i, rate))))
        frames.extend(struct.pack("<h", round(value * 32767)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(frames)


def generate_builtin_sfx(folder: str | Path):
    folder = Path(folder); rng = random.Random(491)
    noise = [rng.uniform(-1, 1) for _ in range(48000)]
    n = lambda i: noise[i % len(noise)]
    _write(folder / "clock_tick.wav", .13, lambda t, i, r: (math.sin(2*math.pi*2250*t)*.55 + n(i)*.22) * math.exp(-42*t))
    _write(folder / "clock_tock.wav", .16, lambda t, i, r: (math.sin(2*math.pi*1180*t)*.62 + n(i)*.18) * math.exp(-31*t))
    _write(folder / "whoosh.wav", .58, lambda t, i, r: n(i)*(math.sin(math.pi*t/.58)**1.8)*.42 + math.sin(2*math.pi*(180+920*t)*t)*.08)
    _write(folder / "swipe.wav", .36, lambda t, i, r: n(i)*math.sin(math.pi*t/.36)*.52 + math.sin(2*math.pi*(320+1900*t)*t)*math.sin(math.pi*t/.36)*.12)
    _write(folder / "paper_tear.wav", .52, lambda t, i, r: n(i)*(.22+.55*math.sin(math.pi*t/.52))*(1 if int(t*73)%3 else .25))
    _write(folder / "glitch.wav", .34, lambda t, i, r: (n(i)*.38+math.sin(2*math.pi*(90+int(t*24)*47)*t)*.26)*(1 if int(t*42)%3 else 0))
    _write(folder / "camera.wav", .20, lambda t, i, r: (n(i)*.62 if .035<t<.075 or .105<t<.14 else math.sin(2*math.pi*170*t)*.18)*math.exp(-5*t))
    _write(folder / "pop.wav", .25, lambda t, i, r: math.sin(2*math.pi*(760-520*t)*t)*math.exp(-18*t)*.72)
    _write(folder / "sparkle.wav", .82, lambda t, i, r: sum(math.sin(2*math.pi*f*t)*math.exp(-d*max(0,t-o))*(1 if t>=o else 0) for f,d,o in ((1320,5,.0),(1760,6,.09),(2210,7,.18)))*.20)
    _write(folder / "impact.wav", .88, lambda t, i, r: (math.sin(2*math.pi*(72-25*t)*t)*.70+n(i)*.16)*math.exp(-4.1*t))
    _write(folder / "riser.wav", 1.15, lambda t, i, r: (n(i)*.18+math.sin(2*math.pi*(180+1200*t*t)*t)*.16)*(t/1.15)**1.8)
    _write(folder / "bass_drop.wav", .95, lambda t, i, r: (math.sin(2*math.pi*(92-54*t)*t)*.72+n(i)*.10)*math.exp(-3.2*t))
    _write(folder / "magic_ding.wav", .95, lambda t, i, r: (math.sin(2*math.pi*1568*t)+.55*math.sin(2*math.pi*2352*t))*math.exp(-5.5*t)*.34)
    _write(folder / "bubble_pop.wav", .28, lambda t, i, r: math.sin(2*math.pi*(920-650*t)*t)*math.exp(-17*t)*.74)
    _write(folder / "soft_chime.wav", 1.45, lambda t, i, r: sum(math.sin(2*math.pi*f*t)*math.exp(-d*t) for f,d in ((523.25,2.8),(659.25,3.4),(783.99,4.0)))*.16)
    _write(folder / "heartbeat.wav", .82, lambda t, i, r: math.sin(2*math.pi*62*t)*(.9 if .03<t<.15 or .28<t<.38 else 0)*math.exp(-3*t)*.72)
