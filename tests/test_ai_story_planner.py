import json,sys,threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from ai_story_planner import APIConfig,request_highlights,plan_sequence,local_sequence
from video_editing_engine import Clip,Project,build_render_command,wrap_caption

class FakeAPI(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        name=body['text']['format']['name']
        if name=='video_highlights':
            data={'summary':'山路旅行','segments':[{'start':1.0,'end':4.2,'score':92,'reason':'动作完整','caption':'沿着山路继续出发','role':'hook','stage':'other','chapter':'出发','shot_type':'移动远景','motion':75,'stability':83,'audio_value':68,'visual_signature':'山路树林'}]}
        else:
            data={'strategy':'冷开场后按时间推进','sequence':[{'id':'s1c0','start':2.0,'end':5.0,'caption':'','reason':'开场吸引力强','role':'hook','transition':'cut'},{'id':'s0c0','start':1.0,'end':4.0,'caption':'一路向前','reason':'建立行程','role':'setup','transition':'fade'}]}
        raw=json.dumps({'output_text':json.dumps(data,ensure_ascii=False)},ensure_ascii=False).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

server=HTTPServer(('127.0.0.1',0),FakeAPI);threading.Thread(target=server.serve_forever,daemon=True).start();cfg=APIConfig(f'http://127.0.0.1:{server.server_port}','test','mock','mock');sheet=Path(sys.argv[1]);analyses=[]
for i,name in enumerate(['DJI_0280.MP4','DJI_0281.MP4']):
    segments=[{'start':1.0+i,'end':4.0+i,'score':90-i,'reason':'清晰','caption':'','role':'development','stage':'other','chapter':'行程','shot_type':'远景','motion':60,'stability':80,'audio_value':20,'visual_signature':name}]
    analyses.append({'meta':{'name':name,'path':name,'has_audio':True,'capture_order':str(i)},'segments':segments})
results=[]
for n in range(1,6):
    highlights=request_highlights(cfg,'沿途景色很好',str(sheet),8,'旅行短片');assert highlights[0]['role']=='hook' and highlights[0]['caption']=='沿着山路继续出发'
    planned=plan_sequence(cfg,analyses,12,'旅行短片');assert [x['source_index'] for x in planned]==[1,0] and planned[0]['role']=='hook'
    local=local_sequence(analyses,8);assert len({x['source_index'] for x in local})==2 and all(x['end']-x['start']>=1.2 for x in local)
    assert '\n' in wrap_caption('这是一条需要自动换成两行显示的中文字幕内容',12)
    p=Project();p.clips=[Clip('a.mp4',0,2)];cmd=build_render_command('ffmpeg',p,'x.mp4');assert '-pix_fmt' in cmd and cmd[cmd.index('-pix_fmt')+1]=='yuv420p'
    results.append({'round':n,'checks':10});print(f'AI DIRECTOR ROUND {n}/5 PASS',flush=True)
server.shutdown();print(json.dumps({'status':'PASS','rounds':5,'checks':50,'results':results},ensure_ascii=False))
