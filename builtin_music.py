from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


MUSIC_LIBRARY = [
    {"id": "travel_breeze", "name": "旅行微风", "file": "travel_breeze.wav", "mood": "旅行 · 明亮", "volume": .20},
    {"id": "kitchen_pop", "name": "厨房跳跳糖", "file": "kitchen_pop.wav", "mood": "美食 · 轻快", "volume": .18},
    {"id": "daily_sunshine", "name": "日常晴天", "file": "daily_sunshine.wav", "mood": "生活 · 温暖", "volume": .20},
    {"id": "story_pulse", "name": "故事脉冲", "file": "story_pulse.wav", "mood": "剧情 · 推进", "volume": .17},
    {"id": "documentary_air", "name": "纪录空气感", "file": "documentary_air.wav", "mood": "纪录 · 克制", "volume": .18},
    {"id": "clean_focus", "name": "清晰专注", "file": "clean_focus.wav", "mood": "口播 · 轻盈", "volume": .14},
]


def music_by_id(music_id: str) -> dict | None:
    return next((dict(x) for x in MUSIC_LIBRARY if x["id"] == music_id), None)


def resolve_music(root: str | Path, music_id: str) -> str:
    item = music_by_id(music_id)
    return str(Path(root) / "assets" / "music" / item["file"]) if item else ""


def _write(path: Path, seconds: float, fn):
    rate = 48000; frames = bytearray()
    for i in range(round(seconds * rate)):
        value = max(-.92, min(.92, float(fn(i / rate, i, rate))))
        frames.extend(struct.pack("<h", round(value * 32767)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(frames)


def generate_builtin_music(folder: str | Path):
    folder = Path(folder); seconds = 12.; rng = random.Random(413)
    def track(notes, bpm, softness=.45, pad=.0):
        beat = 60 / bpm
        def sample(t, i, rate):
            step = int(t / beat) % len(notes); local = t % beat; f = notes[step]
            pluck = math.sin(2*math.pi*f*t) * math.exp(-5.2*local) * softness
            bass = math.sin(2*math.pi*(f/4)*t) * math.exp(-3.2*local) * .12
            air = (rng.random()*2-1) * pad * (.35+.65*math.sin(math.pi*(t%seconds)/seconds)**2)
            kick = math.sin(2*math.pi*(72-28*min(local,.15))*t)*math.exp(-22*local)*.10 if step%2==0 else 0
            return pluck+bass+air+kick
        return sample
    _write(folder/'travel_breeze.wav', seconds, track([261.63,329.63,392.,329.63,293.66,369.99,440.,369.99], 112, .25, .012))
    _write(folder/'kitchen_pop.wav', seconds, track([392.,493.88,587.33,493.88,440.,523.25,659.25,523.25], 124, .22, .006))
    _write(folder/'daily_sunshine.wav', seconds, track([220.,277.18,329.63,277.18,196.,246.94,329.63,246.94], 96, .23, .010))
    _write(folder/'story_pulse.wav', seconds, track([146.83,174.61,220.,174.61,130.81,164.81,196.,164.81], 108, .20, .014))
    _write(folder/'documentary_air.wav', seconds, track([130.81,196.,261.63,196.,146.83,220.,293.66,220.], 72, .14, .025))
    _write(folder/'clean_focus.wav', seconds, track([329.63,392.,493.88,392.,293.66,369.99,440.,369.99], 88, .12, .005))

