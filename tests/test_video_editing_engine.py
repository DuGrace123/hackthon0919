import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from video_editing_engine import *

ROOT=Path(__file__).parents[1];FF=str(ROOT/'ffmpeg.exe') if (ROOT/'ffmpeg.exe').exists() else (shutil.which('ffmpeg') or 'ffmpeg')
def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if os.name=='nt' else 0)
    if p.returncode:raise AssertionError((p.stderr or '')[-1500:])

def assets(folder):
    v1=folder/'a.mp4';v2=folder/'b.mp4';silent=folder/'silent.mp4';music=folder/'music.wav'
    run([FF,'-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(v1)])
    run([FF,'-y','-f','lavfi','-i','color=c=0x6750A4:size=320x180:rate=30','-f','lavfi','-i','sine=frequency=660:sample_rate=48000','-t','2.5','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(v2)])
    run([FF,'-y','-f','lavfi','-i','color=c=0x168AAD:size=320x180:rate=30','-t','2','-c:v','libx264','-pix_fmt','yuv420p',str(silent)])
    run([FF,'-y','-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','8',str(music)])
    return v1,v2,silent,music

def round_test(n,base,paths):
    v1,v2,silent,music=paths;m1=probe_media(FF,str(v1));m2=probe_media(FF,str(v2));m3=probe_media(FF,str(silent))
    assert 2.9<m1['duration']<3.1 and m1['has_audio'];assert not m3['has_audio'];assert m1['width']==320
    thumb=base/f'thumb{n}.jpg';thumbnail(FF,str(v1),str(thumb),.5);assert thumb.stat().st_size>100
    p=Project('测试作品');p.add(m1);p.add(m2);p.add(m3);assert len(p.clips)==3
    p.trim(0,.2,2.8);p.split(0,1.4);assert len(p.clips)==4 and abs(p.clips[0].duration-1.2)<.01
    p.move(3,1);assert p.clips[1].path==str(silent.resolve());p.delete(1);assert len(p.clips)==3
    try:p.trim(0,2,1);raise AssertionError('invalid trim accepted')
    except ValueError:pass
    p.clips[0].caption='第%d轮 字幕测试'%n;p.clips[0].position=['top','center','bottom'][n%3];p.bgm=str(music);p.bgm_volume=.15
    project=base/f'round{n}.ljproject';p.save(project);loaded=Project.load(project);assert loaded.to_dict()==p.to_dict()
    out=base/f'round{n}.mp4';run(build_render_command(FF,loaded,str(out),320,180,'standard'));meta=probe_media(FF,str(out));assert out.stat().st_size>5000 and meta['has_audio'] and meta['duration']>4
    auto=Project();auto.add(m1);auto.add(m2);auto.auto_edit(4);assert 3.8<=auto.duration<=4.1
    return {'round':n,'output_bytes':out.stat().st_size,'duration':meta['duration'],'checks':17}

if __name__=='__main__':
    base=Path(sys.argv[1] if len(sys.argv)>1 else tempfile.mkdtemp(prefix='lingjian-test-'));base.mkdir(parents=True,exist_ok=True);paths=assets(base);results=[]
    for n in range(1,6):results.append(round_test(n,base,paths));print(f'ROUND {n}/5 PASS · {results[-1]}',flush=True)
    report={'status':'PASS','rounds':5,'total_checks':sum(x['checks'] for x in results),'results':results};(base/'test-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
