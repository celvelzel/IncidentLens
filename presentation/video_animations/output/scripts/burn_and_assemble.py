from pathlib import Path
import concurrent.futures as cf,subprocess,json,re,hashlib,time
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'presentation/video_animations/output';FF=imageio_ffmpeg.get_ffmpeg_exe();data=json.loads((OUT/'narration.json').read_text())
def loud(path):
 p=subprocess.run([FF,'-hide_banner','-nostats','-i',str(path),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
 return json.loads(re.search(r'\{\s*"input_i".*?\}',p.stderr,re.S)[0])
p=OUT/'clips_nosub/seg05.mp4';before=loud(p);gain=-16-float(before['input_i']);temp=p.with_name('seg05_leveled.mp4')
if abs(gain)>.015:
 assert float(before['input_tp'])+gain<=-1.5
 subprocess.run([FF,'-y','-v','error','-i',str(p),'-map','0:v:0','-map','0:a:0','-c:v','copy','-af',f'volume={gain:.6f}dB','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-t',str(data[4]['video_duration']),'-movflags','+faststart',str(temp)],check=True)
 temp.replace(p)
after=loud(p);assert abs(float(after['input_i'])+16)<=.03
(OUT/'raw/seg05_light_loudness.json').write_text(json.dumps({'before':before,'gain_db':gain,'after':after,'target_lufs':-16},indent=2))
print('New seg05 leveled:',after['input_i'],'LUFS',flush=True)
def burn(seg):
 n=seg['segment'];src=OUT/f'clips_nosub/seg{n:02}.mp4';dest=OUT/f'clips/seg{n:02}.mp4';temp=dest.with_name(dest.stem+'_burning.mp4');start=time.time()
 with (OUT/f'raw/seg{n:02}_subtitle_encode.log').open('w') as log:
  subprocess.run([FF,'-y','-hide_banner','-i',str(src),'-map','0:v:0','-map','0:a:0','-vf',f"scale=in_range=auto:out_range=tv,ass={OUT}/subtitles/seg{n:02}.ass",'-c:v','libx264','-preset','medium','-crf','18','-threads','2','-pix_fmt','yuv420p','-color_range','tv','-r','30','-c:a','copy','-movflags','+faststart',str(temp)],check=True,stdout=subprocess.DEVNULL,stderr=log)
 temp.replace(dest);print(f'Burned seg{n:02} in {time.time()-start:.1f}s',flush=True)
with cf.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(burn,data))
# Drop unplayed negative-PTS AAC encoder priming packets in concat-only remux copies.
# Published segment audio stays exactly equal to its clean source.
ready=OUT/'raw/concat_ready';ready.mkdir(exist_ok=True)
for seg in data:
 n=seg['segment']
 subprocess.run([FF,'-y','-v','error','-i',str(OUT/f'clips/seg{n:02}.mp4'),'-map','0:v:0','-map','0:a:0','-c','copy','-bsf:a',r'noise=drop=lt(pts\,0)','-movflags','+faststart',str(ready/f'seg{n:02}.mp4')],check=True)
concat=OUT/'raw/concat_subtitled.txt';concat.write_text(''.join(f"file '{ready}/seg{s['segment']:02}.mp4'\nduration {s['video_frames']/30:.10f}\n" for s in data))
final=OUT/'IncidentLens_Presentation_10min.mp4';temp=OUT/'IncidentLens_Presentation_10min_building.mp4'
with (OUT/'raw/concat_subtitled.log').open('w') as log:
 subprocess.run([FF,'-y','-hide_banner','-f','concat','-safe','0','-i',str(concat),'-map','0:v:0','-map','0:a:0','-c','copy','-movflags','+faststart',str(temp)],check=True,stderr=log,stdout=subprocess.DEVNULL)
temp.replace(final);print('Subtitled final assembled without AAC priming overlaps.',flush=True)
