from dataclasses import dataclass

from ai_story_planner import _candidate_rank, enforce_continuity, story_blueprint
from editing_preferences import learn_profile, profile_prompt, timeline_features


@dataclass
class C:
    path: str
    start: float
    end: float
    caption: str = ""
    caption_font: str = "黑体"
    position: str = "lower_third"
    transition: str = "none"


def real_user_timeline():
    # Result hook, then the user's DJI sequence moves only forward.
    return [
        C("DJI_20260825052734_0312_D.MP4", 58.5, 63.0, "OK出锅"),
        C("DJI_20260825045608_0307_D.MP4", 7.75, 11.0, "牛排没解冻"),
        C("DJI_20260825045608_0307_D.MP4", 20.8, 24.0, "解冻了"),
        C("DJI_20260825045819_0308_D.MP4", 0.0, 4.5, "切葱姜蒜"),
        C("DJI_20260825050341_0309_D.MP4", 0.45, 3.2, "切洋葱"),
        C("DJI_20260825051714_0310_D.MP4", 27.8, 31.8, "下油"),
        C("DJI_20260825052108_0311_D.MP4", 23.5, 26.0, "倒酱油"),
        C("DJI_20260825053053_0313_D.MP4", 152.4, 156.4, "味道不错"),
    ]


def continuity_fixture():
    analyses=[]
    for i,stamp in enumerate(("20260825045608","20260825045819","20260825050341","20260825051714","20260825052108","20260825052734","20260825053053")):
        analyses.append({"meta":{"capture_order":stamp,"name":f"DJI_{stamp}.MP4"},"segments":[]})
    sequence=[]
    for source_index in (5,3,0,4,1,2,6):
        stage="plate" if source_index==5 else "taste" if source_index==6 else "cook"
        sequence.append({"source_index":source_index,"start":float(source_index),"end":float(source_index)+2.5,"stage":stage,"score":90,"motion":50,"role":"hook" if source_index==5 else "development"})
    return analyses,sequence


for round_no in range(1,6):
    assert "成品" in story_blueprint("美食教程",30)
    assert "障碍" in story_blueprint("旅行VLOG",60)
    assert "小目标" in story_blueprint("生活记录",30)
    assert "反转" in story_blueprint("剧情短片",120)

    features=timeline_features(real_user_timeline())
    assert features["hook_first"] and features["chronology_ratio"]==1.0
    learned=learn_profile({},real_user_timeline())
    assert learned["samples"]==1 and learned["chronology_strength"]==1.0
    assert "严格按真实拍摄顺序" in profile_prompt(learned)

    filler={"score":90,"stability":80,"audio_value":50,"stage":"other","caption":"刚刚离开一下","reason":"等待"}
    useful={"score":82,"stability":80,"audio_value":50,"stage":"cook","caption":"然后我们先下油","reason":"关键动作变化"}
    assert _candidate_rank(useful)>_candidate_rank(filler)

    analyses,sequence=continuity_fixture()
    for target in (30,60,120):
        fixed=enforce_continuity(sequence,analyses,"美食教程",target)
        keys=[(analyses[x["source_index"]]["meta"]["capture_order"],x["start"]) for x in fixed[1:]]
        assert keys==sorted(keys),keys
        assert sum(x.get("role")=="hook" for x in fixed)==1
    print(f"STORY PROFILE ROUND {round_no}/5 PASS",flush=True)

print("V4.3 STORY + PERSONALIZATION PASS: 5 rounds")
