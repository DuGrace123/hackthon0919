from ai_story_planner import local_sequence,enforce_continuity,STAGE_ORDER

def make_analyses():
    analyses=[];stages=['prep','cook','taste']
    for source_index in range(3):
        segments=[]
        for i in range(32):
            stage='other' if i%5==2 else stages[source_index]
            start=i*4.0;segments.append({'start':start,'end':start+3.2,'score':95-(i%11),'reason':stage,'caption':'','role':'development','stage':stage,'chapter':f'章节{source_index+1}','shot_type':'','motion':40+i%30,'stability':85,'audio_value':25,'visual_signature':f'{source_index}-{i}'})
        analyses.append({'meta':{'name':f'乱序文件{2-source_index}.mp4','path':f'{source_index}.mp4','capture_order':f'202608201{source_index}0000'},'segments':list(reversed(segments))})
    return analyses

analyses=make_analyses()
for round_no in range(1,6):
    for target in (60,120,180):
        sequence=local_sequence(analyses,target,'美食教程 · 120秒长视频严格按步骤')
        assert sequence and sequence[0]['role']=='hook'
        duration=sum(x['end']-x['start'] for x in sequence)
        assert duration>=target*.82,(target,duration)
        known=[STAGE_ORDER[x['stage']] for x in sequence[1:] if x['stage']!='other']
        assert known==sorted(known),(target,known)
        assert sum(x.get('role')=='hook' for x in sequence)==1
    scrambled=[]
    for source_index,item in reversed(list(enumerate(analyses))):
        for s in item['segments'][:8]:scrambled.append({'source_index':source_index,'source_name':item['meta']['name'],**s})
    fixed=enforce_continuity(scrambled,analyses,'生活记录长视频',120)
    keys=[(analyses[x['source_index']]['meta']['capture_order'],x['start']) for x in fixed[1:]]
    assert keys==sorted(keys),keys
    print(f'LONGFORM ROUND {round_no}/5 PASS · 60/120/180s',flush=True)
print('LONGFORM CONTINUITY PASS: 5 rounds, 3 target durations')
