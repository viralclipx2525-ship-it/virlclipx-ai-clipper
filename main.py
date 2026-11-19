import os, re, uuid, shutil, subprocess, threading
from pathlib import Path
from typing import Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

ROOT = Path(__file__).resolve().parent
WORK = Path(os.getenv('WORK_DIR', '/tmp/virlclipx'))
WORK.mkdir(parents=True, exist_ok=True)
JOBS: Dict[str, dict] = {}
app = FastAPI(title='VirlClipX AI Clipper')
(WORK / 'outputs').mkdir(parents=True, exist_ok=True)
app.mount('/outputs', StaticFiles(directory=WORK / 'outputs'), name='outputs')
(WORK / 'outputs').mkdir(exist_ok=True)

class ClipRequest(BaseModel):
    url: HttpUrl
    count: int = 3
    duration: int = 25


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-1800:])
    return p.stdout


def process_job(job_id: str, url: str, count: int, duration: int):
    jobdir = WORK / job_id
    jobdir.mkdir(parents=True, exist_ok=True)
    try:
        JOBS[job_id].update(status='downloading', progress=10, message='Getting video information…')
        # yt-dlp only retrieves publicly accessible videos; no DRM or access-control bypass.
        template = str(jobdir / 'source.%(ext)s')
        run(['yt-dlp', '--no-playlist', '--max-filesize', '1500M', '-f', 'bv*[height<=1080]+ba/b[height<=1080]/b', '--merge-output-format', 'mp4', '-o', template, str(url)])
        files = [p for p in jobdir.glob('source.*') if p.suffix.lower() in ['.mp4','.mkv','.webm','.mov']]
        if not files:
            raise RuntimeError('Could not find a downloaded video file.')
        src = files[0]
        JOBS[job_id].update(status='analyzing', progress=35, message='Analyzing scene and audio activity…')
        # Read duration and build candidate windows from audio energy peaks.
        probe = run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(src)])
        total = float(probe.strip())
        if total < 5:
            raise RuntimeError('This video is too short to make clips.')
        import numpy as np
        import wave
        wav = jobdir / 'audio.wav'
        run(['ffmpeg','-y','-i',str(src),'-vn','-ac','1','-ar','8000','-f','wav',str(wav)])
        with wave.open(str(wav),'rb') as wf:
            rate = wf.getframerate(); raw = wf.readframes(wf.getnframes())
        audio = np.frombuffer(raw,dtype=np.int16).astype(np.float32)
        step = rate * 2
        energies=[]
        for i in range(0,len(audio),step):
            chunk=audio[i:i+step]
            if len(chunk): energies.append((i/rate, float(np.sqrt(np.mean(chunk*chunk)))))
        # Score two-second windows; spread selected highlights apart.
        ranked=sorted(energies,key=lambda x:x[1],reverse=True)
        chosen=[]
        for t,score in ranked:
            start=max(0,min(total-duration,t-duration*0.35))
            if all(abs(start-s)>duration*0.8 for s in chosen):
                chosen.append(start)
            if len(chosen)>=count: break
        if not chosen: chosen=[max(0,(total-duration)/2)]
        chosen=sorted(chosen)
        outputs=[]
        JOBS[job_id].update(status='rendering', progress=60, message='Creating vertical gaming clips…')
        for idx,start in enumerate(chosen,1):
            out=WORK/'outputs'/f'{job_id}_{idx}.mp4'
            # Center crop to 9:16, scale to 1080x1920. Original audio is retained.
            run(['ffmpeg','-y','-ss',str(start),'-i',str(src),'-t',str(min(duration,total-start)),'-vf',"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",'-c:v','libx264','-preset','veryfast','-crf','23','-c:a','aac','-b:a','128k','-movflags','+faststart',str(out)])
            outputs.append({'name':f'Gaming highlight {idx}','url':f'/outputs/{out.name}','start':round(start,1)})
            JOBS[job_id].update(progress=60+int(35*idx/len(chosen)), message=f'Rendered clip {idx} of {len(chosen)}…')
        JOBS[job_id].update(status='done',progress=100,message='Your clips are ready!',clips=outputs)
    except Exception as e:
        JOBS[job_id].update(status='error',progress=100,message=str(e)[:500])

@app.get('/')
def home(): return FileResponse(ROOT/'index.html')

@app.get('/api/health')
def health(): return {'ok':True,'name':'VirlClipX AI Clipper'}

@app.post('/api/clip')
def create_clip(req: ClipRequest, bg: BackgroundTasks):
    host = req.url.host.lower()
    if not (host.endswith('youtube.com') or host.endswith('youtu.be')):
        raise HTTPException(400,'Please enter a YouTube URL.')
    if req.count not in range(1,6) or req.duration not in [15,20,25,30,40,45,60]:
        raise HTTPException(400,'Choose 1–5 clips and a supported clip length.')
    job_id=uuid.uuid4().hex[:12]
    JOBS[job_id]={'status':'queued','progress':0,'message':'Queued…','clips':[]}
    bg.add_task(process_job,job_id,str(req.url),req.count,req.duration)
    return {'job_id':job_id}

@app.get('/api/status/{job_id}')
def status(job_id:str):
    if job_id not in JOBS: raise HTTPException(404,'Job not found.')
    return JOBS[job_id]
