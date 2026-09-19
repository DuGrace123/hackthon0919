import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
from video_editing_engine import Clip,Project,build_render_command,validate_rendered_mp4

ROOT=Path(__file__).parents[1];FF=str(ROOT/'ffmpeg.exe') if (ROOT/'ffmpeg.exe').exists() else (shutil.which('ffmpeg') or 'ffmpeg');BASE=Path(sys.argv[1] if len(sys.argv)>1 else tempfile.mkdtemp(prefix='lingjian-effects-'));BASE.mkdir(parents=True,exist_ok=True)
TRANSITIONS=['pip_zoom','tear_left','tear_right','pixelize','squeeze','radial','fade_black','fade_white','cover_left','reveal_right']
MASKS=['none','diamond','vertical_strip','split_left','split_right','privacy_blur','vignette','spotlight','ellipse','portrait_card','cinema']

def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if os.name=='nt' else 0)
    if p.returncode:raise AssertionError((p.stderr or '')[-2400:])

src1=BASE/'effect-a.mp4';src2=BASE/'effect-b.mp4'
if not src1.exists():run([FF,'-y','-f','lavfi','-i','testsrc2=size=320x180:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src1)])
if not src2.exists():run([FF,'-y','-f','lavfi','-i','smptebars=size=320x180:rate=30','-f','lavfi','-i','sine=frequency=660:sample_rate=48000','-t','4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src2)])

results=[]
for round_no in range(1,6):
    project=Project(f'高级效果回归 {round_no}')
    for i,mask in enumerate(MASKS):
        transition='none' if i==0 else TRANSITIONS[(i-1)%len(TRANSITIONS)];clip=Clip(str(src1 if i%2==0 else src2),.1,.82,f'高级效果 {i+1}',transition=transition,has_audio=True);clip.transition_duration=.12;clip.mask_shape=mask;clip.mask_x=.46+.04*(i%3);clip.mask_y=.48;clip.mask_width=.58;clip.mask_height=.62;clip.mask_feather=22;clip.mask_opacity=1;project.clips.append(clip)
    out=BASE/f'advanced-effects-{round_no}.mp4';cmd=build_render_command(FF,project,str(out),320,180,'standard');graph=cmd[cmd.index('-filter_complex')+1]
    for token in ('zoomin','hlslice','hrslice','pixelize','squeezeh','radial','fadeblack','fadewhite','coverleft','revealright','vignette=','privacy','geq='):
        assert token in graph,token
    run(cmd);meta=validate_rendered_mp4(FF,str(out));assert meta['width']==320 and meta['height']==180 and meta['has_audio'] and out.stat().st_size>10000
    results.append({'round':round_no,'bytes':out.stat().st_size,'transitions':len(TRANSITIONS),'masks':len(MASKS)});print(f'V4.7 ADVANCED EFFECTS ROUND {round_no}/5 PASS',flush=True)
print(json.dumps({'status':'PASS','rounds':5,'results':results},ensure_ascii=False))
