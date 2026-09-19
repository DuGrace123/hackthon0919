from ai_story_planner import enforce_continuity, local_sequence, narrative_mode, STAGE_ORDER

def shot(start,stage,score=80,role='development'):
    return {'source_index':0,'source_name':'未命名作品.mp4','start':start,'end':start+3,'score':score,
            'reason':stage,'caption':'','role':role,'stage':stage,'chapter':stage,'motion':50,
            'stability':85,'audio_value':20,'visual_signature':f'{stage}-{start}'}

# Reproduces the reported failure: taste/result shots were interleaved with earlier prep/cook shots.
raw=[shot(85,'taste',94,'hook'),shot(10,'prep'),shot(60,'cook'),shot(100,'prep'),
     shot(140,'cook'),shot(129,'taste'),shot(118,'other',20),shot(150,'plate')]
analyses=[{'meta':{'name':'未命名作品.mp4','path':'x.mp4','capture_order':'20260820030008'},'segments':raw}]

for round_no in range(1,6):
    fixed=enforce_continuity(raw,analyses,'美食教程 · 成品钩子后严格按步骤')
    assert fixed[0]['role']=='hook' and fixed[0]['stage'] in ('plate','taste')
    body=[x for x in fixed[1:] if x['stage']!='other']
    values=[STAGE_ORDER[x['stage']] for x in body]
    assert values==sorted(values),values
    assert not any(a['stage'] in ('cook','plate','taste') and b['stage']=='prep' for a,b in zip(body,body[1:]))
    assert sum(x['role']=='hook' for x in fixed)==1
    assert narrative_mode('美食教程',raw)=='procedural'
    local=local_sequence(analyses,21,'美食教程 · 严格按步骤')
    local_values=[STAGE_ORDER[x['stage']] for x in local[1:] if x['stage']!='other']
    assert local_values==sorted(local_values)
    print(f'CONTINUITY ROUND {round_no}/5 PASS')
print('CONTINUITY REGRESSION PASS: 5 rounds')
