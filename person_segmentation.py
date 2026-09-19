"""Offline person segmentation and temporal tracking for LingJian AI.

The model is evaluated repeatedly through the clip; every output frame receives
the temporally-smoothed matte, so the composite follows a moving person.
"""
from __future__ import annotations
import json,os,subprocess,tempfile
from pathlib import Path

MODEL_SHA256='01EB6A29A5C4D8EDB30B56ADAD9BB3A2A0535338E480724A213E0ACFD2D1C73C'

def _even(value):return max(2,int(value)//2*2)

class PersonSegmenter:
    def __init__(self,model_path):
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=max(1,min(8,(os.cpu_count() or 4)-1));options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session=ort.InferenceSession(str(model_path),sess_options=options,providers=['CPUExecutionProvider']);self.input_name=self.session.get_inputs()[0].name;self.output_name=self.session.get_outputs()[0].name
    def matte(self,rgb):
        import numpy as np
        from PIL import Image
        image=Image.fromarray(rgb).resize((320,320),Image.Resampling.BILINEAR);array=np.asarray(image,dtype=np.float32)/255.0;mean=np.array([.485,.456,.406],dtype=np.float32);std=np.array([.229,.224,.225],dtype=np.float32);tensor=((array-mean)/std).transpose(2,0,1)[None]
        pred=self.session.run([self.output_name],{self.input_name:tensor})[0][0,0];lo=float(pred.min());hi=float(pred.max());pred=(pred-lo)/max(1e-6,hi-lo);return pred

def process_person_video(ffmpeg,source,start,end,output,model_path,mode='blur',quality='balanced',strength=72,progress=None):
    import numpy as np
    from PIL import Image,ImageFilter
    duration=max(.1,float(end)-float(start));probe=subprocess.run([ffmpeg,'-hide_banner','-i',str(source)],capture_output=True,text=True,encoding='utf-8',errors='replace').stderr
    import re
    match=re.search(r'Video:.*? (\d{2,5})x(\d{2,5})',probe);sw,sh=(int(match.group(1)),int(match.group(2))) if match else (720,1280);scale=min(1.,1280/max(sw,sh));width,height=_even(sw*scale),_even(sh*scale);fps=30;total=max(1,round(duration*fps));step={'fast':5,'balanced':3,'precise':1}.get(quality,3);frame_bytes=width*height*3
    decoder=subprocess.Popen([ffmpeg,'-v','error','-ss',f'{start:.3f}','-t',f'{duration:.3f}','-i',str(source),'-an','-vf',f'scale={width}:{height},fps={fps}','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);silent=output.with_suffix('.silent.mp4');encoder=subprocess.Popen([ffmpeg,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',str(silent)],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
    engine=PersonSegmenter(model_path);last=None;tracks=[];frame_no=0;strength=max(0,min(100,int(strength)));blur_radius=5+strength*.24
    try:
        while True:
            raw=decoder.stdout.read(frame_bytes)
            if len(raw)<frame_bytes:break
            frame=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3)
            if last is None or frame_no%step==0:
                pred=engine.matte(frame);mask_image=Image.fromarray((pred*255).astype(np.uint8)).resize((width,height),Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(radius=1.2+strength*.018));current=np.asarray(mask_image,dtype=np.float32)/255.;current=np.clip((current-.08)/.78,0,1);last=current if last is None else last*.42+current*.58
                ys,xs=np.where(last>.5)
                if len(xs)>20:
                    x0,x1,y0,y1=int(xs.min()),int(xs.max()),int(ys.min()),int(ys.max());tracks.append({'t':round(frame_no/fps,3),'x':round((x0+x1)/2/width,4),'y':round((y0+y1)/2/height,4),'w':round((x1-x0)/width,4),'h':round((y1-y0)/height,4),'confidence':round(float(last[ys,xs].mean()),4)})
            alpha=np.clip(last[...,None],0,1)
            if mode=='dim':background=(frame.astype(np.float32)*(.18+.0035*(100-strength))).astype(np.uint8)
            elif mode=='color':background=np.empty_like(frame);background[:]=np.array([24,31,45],dtype=np.uint8)
            else:background=np.asarray(Image.fromarray(frame).filter(ImageFilter.GaussianBlur(radius=blur_radius)))
            composed=np.clip(frame.astype(np.float32)*alpha+background.astype(np.float32)*(1-alpha),0,255).astype(np.uint8);encoder.stdin.write(composed.tobytes());frame_no+=1
            if progress and (frame_no%10==0 or frame_no==total):progress(min(94,int(frame_no/max(1,total)*94)),f'AI 人物跟踪 {min(frame_no,total)}/{total} 帧')
    finally:
        if encoder.stdin:encoder.stdin.close()
        encoder.wait();decoder.wait()
    if encoder.returncode or not silent.exists():raise RuntimeError('人物遮罩视频编码失败')
    if progress:progress(96,'正在合并原声并写入跟踪结果')
    merge=[ffmpeg,'-v','error','-y','-i',str(silent),'-ss',f'{start:.3f}','-t',f'{duration:.3f}','-i',str(source),'-map','0:v:0','-map','1:a?','-c:v','copy','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(output)];done=subprocess.run(merge,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if os.name=='nt' else 0);silent.unlink(missing_ok=True)
    if done.returncode:raise RuntimeError('人物效果音视频合并失败：'+done.stderr[-800:])
    report={'version':1,'source':str(source),'start':float(start),'end':float(end),'mode':mode,'quality':quality,'width':width,'height':height,'fps':fps,'frames':frame_no,'inference_step':step,'tracks':tracks};output.with_suffix('.tracking.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if progress:progress(100,'自动抠人与人物移动跟踪完成')
    return report
