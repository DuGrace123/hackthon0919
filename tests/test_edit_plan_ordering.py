from __future__ import annotations
import copy,json
from edit_plan import apply_opening_treatment,build_edit_plan,plan_preview_text

def fixture():
    analyses=[]
    for i in range(8):
        stamp=f'20260821{(100000+i*100):06d}'
        name=f'DJI_{stamp}_{290+i:04d}_D.MP4'
        analyses.append({'meta':{'path':name,'name':name,'duration':240.,'has_audio':True,'capture_order':stamp},'segments':[]})
    sequence=[{'source_index':7,'start':180.,'end':185.8,'role':'hook','caption':'先看结果','reason':'未来结果钩子','transition':'none'}]
    for i in range(100):
        source=min(7,i//13);start=float((i%13)*4.1);sequence.append({'source_index':source,'start':start,'end':start+3.6,'role':'outro' if i==99 else 'development','caption':'','reason':'长视频章节补足','transition':'none'})
    sequence[48],sequence[49]=sequence[49],sequence[48]
    return sequence,analyses

results=[]
for round_no in range(1,6):
    sequence,analyses=fixture();original_hook=copy.deepcopy(sequence[0]);plan=build_edit_plan(sequence,analyses,365.4,'旅行长视频，钩子后严格按真实拍摄顺序','long-regression')
    assert plan['validation']['ok'],plan['validation']
    assert plan['validation']['chronology_ratio']==1.0
    assert plan['decisions'][0]['source_index']==original_hook['source_index'] and plan['decisions'][0]['role']=='hook'
    assert plan['validation']['repairs'] and '移动' in plan['validation']['repairs'][0]
    preview=plan_preview_text(plan);assert '自动修复' in preview and '正文顺序一致率 100%' in preview
    treated=apply_opening_treatment(plan,'hollow_vlog','旅行叙事')
    assert treated['validation']['ok'] and treated['validation']['chronology_ratio']==1.0
    assert '方案已阻止' not in plan_preview_text(treated)
    results.append({'round':round_no,'clips':len(plan['decisions']),'ratio':plan['validation']['chronology_ratio'],'repairs':len(plan['validation']['repairs'])})
print(json.dumps({'status':'PASS','scenario':'365.4s / 101 clips / original 99%','rounds':results},ensure_ascii=False))
