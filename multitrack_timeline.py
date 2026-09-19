from PySide6.QtCore import Qt,Signal,QRectF,QMimeData,QSize,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QBrush,QFont,QPixmap,QDrag
from PySide6.QtWidgets import QWidget,QListWidget

class MediaList(QListWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setDragEnabled(True);self.setIconSize(QSize(96,54));self.setSpacing(4)
    def mimeData(self,items):
        mime=QMimeData()
        if items:mime.setData('application/x-lingjian-media',items[0].data(Qt.UserRole).encode('utf-8'))
        return mime

class TimelineCanvas(QWidget):
    selected=Signal(int);moved=Signal(int,int);trimmed=Signal(int,float,float);seeked=Signal(float);mediaDropped=Signal(str,int);editStarted=Signal();editFinished=Signal();bladeRequested=Signal(int,float);trackStateChanged=Signal(bool,bool)
    LABEL=72;RULER=28;BASE_VIDEO_Y=34;VIDEO_H=76;SUB_H=34;AUDIO_H=48;OVERLAY_H=36
    def __init__(self,parent=None):
        super().__init__(parent);self.project=None;self.zoom=18.;self.playhead=0.;self.selected_index=-1;self.thumbs={};self._mode='';self._press=None;self._hover=-1;self.tool='select';self.snap=True;self.video_locked=False;self.audio_muted=False;self.setMinimumHeight(212);self.setAcceptDrops(True);self.setMouseTracking(True)
    @property
    def overlay_tracks(self):return sorted({int(x.track) for x in (getattr(self.project,'overlays',[]) or [])},reverse=True)
    @property
    def VIDEO_Y(self):return self.BASE_VIDEO_Y+len(self.overlay_tracks)*self.OVERLAY_H
    @property
    def SUB_Y(self):return self.VIDEO_Y+self.VIDEO_H+5
    @property
    def AUDIO_Y(self):return self.SUB_Y+self.SUB_H+5
    def overlay_y(self,track):return self.BASE_VIDEO_Y+self.overlay_tracks.index(int(track))*self.OVERLAY_H
    def set_tool(self,tool):self.tool=tool;self.setCursor(Qt.CrossCursor if tool=='blade' else Qt.ArrowCursor)
    def set_snap(self,on):self.snap=bool(on)
    def set_project(self,p):self.project=p;self.setMinimumHeight(self.AUDIO_Y+self.AUDIO_H+10);self.reflow();self.update()
    def set_thumbnails(self,d):self.thumbs=d;self.update()
    def set_zoom(self,z):self.zoom=max(5.,min(70.,float(z)));self.reflow();self.update()
    def set_playhead(self,t):self.playhead=max(0,float(t));self.update()
    def reflow(self):
        duration=self.project.duration if self.project else 0;self.setMinimumWidth(max(760,int(self.LABEL+duration*self.zoom+100)))
    def positions(self):
        out=[];x=self.LABEL
        if self.project:
            for i,c in enumerate(self.project.clips):
                w=max(36,c.duration*self.zoom);out.append((i,c,x,w));x+=w
        return out
    def clip_at(self,x,y):
        if not (self.VIDEO_Y<=y<=self.VIDEO_Y+self.VIDEO_H):return None
        for item in self.positions():
            if item[2]<=x<=item[2]+item[3]:return item
    def global_at(self,x):return max(0,(x-self.LABEL)/self.zoom)
    def format_time(self,t):return f'{int(t)//60:02d}:{int(t)%60:02d}'
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('#0c0e13'))
        p.fillRect(0,0,self.LABEL,self.height(),QColor('#161922'));p.fillRect(self.LABEL,0,self.width(),self.RULER,QColor('#11141b'))
        p.setPen(QColor('#80889a'));step=1 if self.zoom>=35 else 5 if self.zoom>=12 else 10;duration=max(1,int((self.width()-self.LABEL)/self.zoom)+1)
        for t in range(0,duration+1,step):
            x=self.LABEL+t*self.zoom;p.drawLine(int(x),18,int(x),self.RULER);p.drawText(int(x+3),15,self.format_time(t))
        for track in self.overlay_tracks:
            y=self.overlay_y(track);p.fillRect(self.LABEL,y,self.width()-self.LABEL,self.OVERLAY_H-2,QColor('#1b2030'));p.setPen(QColor('#b9c3d8'));p.drawText(8,y+self.OVERLAY_H//2+4,f'V{track}  叠加/蒙版')
        for overlay in getattr(self.project,'overlays',[]) or []:
            y=self.overlay_y(overlay.track);x=self.LABEL+float(overlay.timeline_start)*self.zoom;w=max(38,float(overlay.duration)*self.zoom);rect=QRectF(x+1,y+2,w-2,self.OVERLAY_H-6);p.setPen(QColor('#63D8C7'));p.setBrush(QColor('#245C62'));p.drawRoundedRect(rect,5,5);p.setPen(QColor('#E9FFFB'));p.setFont(QFont('Microsoft YaHei UI',8));p.drawText(rect.adjusted(6,0,-4,0),Qt.AlignVCenter|Qt.TextSingleLine,f'◈ {overlay.name} · {overlay.mask_shape}')
        for y,label,color in [(self.VIDEO_Y,'V1  视频','#17202c'),(self.SUB_Y,'T1  字幕','#1d1929'),(self.AUDIO_Y,'A1  音乐/原声/音效','#14231f')]:
            h=self.VIDEO_H if y==self.VIDEO_Y else self.SUB_H if y==self.SUB_Y else self.AUDIO_H;p.fillRect(self.LABEL,y,self.width()-self.LABEL,h,QColor(color));p.setPen(QColor('#aab1c1'));suffix=' 🔒' if y==self.VIDEO_Y and self.video_locked else ' 🔇' if y==self.AUDIO_Y and self.audio_muted else '';p.drawText(8,y+h//2+4,label+suffix)
        for i,c,x,w in self.positions():
            sel=i==self.selected_index;rect=QRectF(x+1,self.VIDEO_Y+2,w-2,self.VIDEO_H-4);p.setPen(QPen(QColor('#a98cff') if sel else QColor('#58647a'),2 if sel else 1));p.setBrush(QColor('#4b3a86') if sel else QColor('#253a55'));p.drawRoundedRect(rect,5,5)
            pix=self.thumbs.get(c.path)
            if pix and not pix.isNull():p.setOpacity(.45);p.drawPixmap(rect.toRect(),pix);p.setOpacity(1)
            p.fillRect(QRectF(x+1,self.VIDEO_Y+2,w-2,23),QColor(15,18,26,190));p.setPen(QColor('white'));p.drawText(QRectF(x+7,self.VIDEO_Y+5,w-12,18),Qt.AlignVCenter|Qt.TextSingleLine,c.name)
            p.setPen(QColor('#d5d9e4'));p.drawText(QRectF(x+7,self.VIDEO_Y+32,w-12,20),Qt.AlignVCenter,f'{c.duration:.1f}s')
            badges=[]
            if getattr(c,'transition','none')!='none':badges.append('↔ '+str(c.transition).replace('_',' '))
            if getattr(c,'mask_shape','none')!='none':badges.append('◉ '+str(c.mask_shape).replace('_',' '))
            if getattr(c,'person_effect_path',''):badges.append('✦ 人物跟踪')
            if getattr(c,'title_effect','')=='bounce':badges.append('◌ Q弹标题')
            elif getattr(c,'title_effect','')=='text_window':badges.append('▣ 字内走马灯')
            if badges:
                p.setPen(QColor('#d9c7ff'));p.setFont(QFont('Microsoft YaHei UI',8));p.drawText(QRectF(x+7,self.VIDEO_Y+51,w-12,17),Qt.AlignVCenter|Qt.TextSingleLine,' · '.join(badges))
            if c.caption:
                sr=QRectF(x+1,self.SUB_Y+2,w-2,self.SUB_H-4);p.setPen(QColor('#9f79ec'));p.setBrush(QColor('#4c306f'));p.drawRoundedRect(sr,4,4);p.setPen(QColor('white'));p.drawText(sr.adjusted(6,0,-4,0),Qt.AlignVCenter|Qt.TextSingleLine,c.caption)
            ar=QRectF(x+1,self.AUDIO_Y+2,w-2,self.AUDIO_H-4);p.setPen(QColor('#3d856e'));p.setBrush(QColor('#1d4b42'));p.drawRoundedRect(ar,4,4);p.setPen(QColor('#7acbae'))
            mid=ar.center().y();count=max(3,int(w/8))
            for n in range(count):
                xx=ar.left()+4+n*8;amp=5+((n*7+i*11)%14);p.drawLine(int(xx),int(mid-amp),int(xx),int(mid+amp))
        if self.project:
            for cue in getattr(self.project,'sfx',[]) or []:
                x=self.LABEL+float(cue.start)*self.zoom;w=max(38,min(110,len(cue.name or cue.effect_id)*9+14));rect=QRectF(x,self.AUDIO_Y+3,w,18);p.setPen(QColor('#FFD166'));p.setBrush(QColor('#725A18'));p.drawRoundedRect(rect,5,5);p.setPen(QColor('#FFF2B3'));p.setFont(QFont('Microsoft YaHei UI',8));p.drawText(rect.adjusted(5,0,-3,0),Qt.AlignVCenter|Qt.TextSingleLine,'♪ '+(cue.name or cue.effect_id))
        px=self.LABEL+self.playhead*self.zoom;p.setPen(QPen(QColor('#ff6274'),2));p.drawLine(int(px),0,int(px),self.height());p.setBrush(QColor('#ff6274'));p.setPen(Qt.NoPen);p.drawPolygon([QPointF(px-6,0),QPointF(px+6,0),QPointF(px,9)])
    def mousePressEvent(self,e):
        if e.position().x()<self.LABEL:
            if self.VIDEO_Y<=e.position().y()<=self.VIDEO_Y+self.VIDEO_H:self.video_locked=not self.video_locked
            elif self.AUDIO_Y<=e.position().y()<=self.AUDIO_Y+self.AUDIO_H:self.audio_muted=not self.audio_muted
            self.trackStateChanged.emit(self.video_locked,self.audio_muted);self.update();return
        item=self.clip_at(e.position().x(),e.position().y());self._press=e.position()
        if item:
            i,c,x,w=item;self.selected_index=i;self.selected.emit(i);edge=7
            if self.tool=='blade':self.bladeRequested.emit(i,c.start+(e.position().x()-x)/max(1,w)*c.duration);self.update();return
            if self.video_locked:return
            self._mode='trim-left' if abs(e.position().x()-x)<edge else 'trim-right' if abs(e.position().x()-(x+w))<edge else 'move';self._original=(c.start,c.end,x,w);self.editStarted.emit();self.update()
        else:self._mode='seek';self.seeked.emit(self.global_at(e.position().x()))
    def mouseMoveEvent(self,e):
        item=self.clip_at(e.position().x(),e.position().y());self.setCursor(Qt.SizeHorCursor if item and (abs(e.position().x()-item[2])<7 or abs(e.position().x()-(item[2]+item[3]))<7) else Qt.OpenHandCursor if item else Qt.ArrowCursor)
        if not (e.buttons()&Qt.LeftButton) or self.selected_index<0:return
        if self._mode=='seek':self.seeked.emit(self.global_at(e.position().x()));return
        if self._mode.startswith('trim'):
            c=self.project.clips[self.selected_index];delta=(e.position().x()-self._press.x())/self.zoom;a,b=self._original[0],self._original[1]
            if self._mode=='trim-left':a=min(b-.1,max(0,a+delta))
            else:b=max(a+.1,b+delta)
            if self.snap:a=round(a*10)/10;b=round(b*10)/10
            self.trimmed.emit(self.selected_index,a,b)
    def mouseReleaseEvent(self,e):
        if self._mode=='move' and self.selected_index>=0 and not self.video_locked:
            target_time=self.global_at(e.position().x());acc=0;target=len(self.project.clips)-1
            for i,c in enumerate(self.project.clips):
                if target_time<acc+c.duration/2:target=i;break
                acc+=c.duration
            if target!=self.selected_index:self.moved.emit(self.selected_index,target)
        if self._mode:self.editFinished.emit()
        self._mode=''
    def dragEnterEvent(self,e):
        if e.mimeData().hasFormat('application/x-lingjian-media'):e.acceptProposedAction()
    def dropEvent(self,e):
        path=bytes(e.mimeData().data('application/x-lingjian-media')).decode('utf-8');target_time=self.global_at(e.position().x());acc=0;index=0
        if self.project:
            index=len(self.project.clips)
            for i,c in enumerate(self.project.clips):
                if target_time<acc+c.duration/2:index=i;break
                acc+=c.duration
        self.mediaDropped.emit(path,index);e.acceptProposedAction()
