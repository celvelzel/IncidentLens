"""Local-only ASR reference timing; never edits audio or contacts a provider."""
from pathlib import Path
import json,subprocess,os,time
import numpy as np
import torch, whisper
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'presentation/video_animations/output'
# The project bundles a libass-enabled FFmpeg; decode directly, avoiding global PATH changes.
import glob
FF=glob.glob(str(ROOT/'.venv/lib/python*/site-packages/imageio_ffmpeg/binaries/ffmpeg-*'))[0]
torch.set_num_threads(4)
model=whisper.load_model('base',device='cpu')
for seg in json.loads((OUT/'narration.json').read_text()):
 n=seg['segment'];dest=OUT/f'raw/seg{n:02}_asr.json'
 if dest.exists():continue
 path=OUT/f'clips_nosub/seg{n:02}.mp4'
 if not path.exists():path=OUT/'raw/update_baseline/seg05_dark.mp4'
 pcm=subprocess.check_output([FF,'-v','error','-i',str(path),'-vn','-ac','1','-ar','16000','-f','f32le','-'])
 audio=np.frombuffer(pcm,np.float32).copy();t=time.time()
 result=model.transcribe(audio,language='en',task='transcribe',word_timestamps=True,fp16=False,verbose=None,condition_on_previous_text=False,initial_prompt='IncidentLens, FinalizeGate, IncidentBench, LangGraph, DeepSeek, hy4-flash, OhMyGPT, INCONCLUSIVE, RESOLVED. Technical presentation.')
 dest.write_text(json.dumps(result,indent=2))
 print(f'Local ASR seg{n:02}: {time.time()-t:.1f}s; '+result['text'],flush=True)
