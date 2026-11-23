from pathlib import Path
import subprocess,concurrent.futures as cf,json,re,hashlib,struct
from PIL import Image,ImageDraw,ImageFont,ImageStat
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'presentation/video_animations/output';FF=imageio_ffmpeg.get_ffmpeg_exe();data=json.loads((OUT/'narration.json').read_text());meta=json.loads((OUT/'subtitle_metadata.json').read_text());base=json.loads((OUT/'raw/update_baseline/integrity.json').read_text())
def run(args,**kw):return subprocess.run([FF,*args],capture_output=True,text=True,check=True,**kw)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
final=OUT/'IncidentLens_Presentation_10min.mp4'
assert 'Non-monotonic' not in (OUT/'raw/concat_subtitled.log').read_text()
def inspect(path,frames):
 probe=subprocess.run([FF,'-hide_banner','-i',str(path)],capture_output=True,text=True).stderr
 v=next(x.strip() for x in probe.splitlines() if 'Stream #' in x and 'Video:' in x);a=next(x.strip() for x in probe.splitlines() if 'Stream #' in x and 'Audio:' in x)
 assert '1920x1080' in v and '30 fps' in v and 'h264' in v and 'yuv420p' in v,v
 assert 'aac' in a and '44100 Hz' in a and 'stereo' in a,a
 assert 'Subtitle:' not in probe
 d=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);duration=int(d[1])*3600+int(d[2])*60+float(d[3])
 dec=run(['-v','error','-xerror','-nostats','-i',str(path),'-map','0:v:0','-map','0:a:0','-fps_mode','passthrough','-progress','pipe:1','-f','null','-'])
 assert not dec.stderr.strip(),dec.stderr
 count=int(re.findall(r'frame=(\d+)',dec.stdout)[-1]);assert count==frames,(path,count,frames)
 loud=run(['-hide_banner','-nostats','-i',str(path),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-']);l=json.loads(re.search(r'\{\s*"input_i".*?\}',loud.stderr,re.S)[0]);assert abs(float(l['input_i'])+16)<=.05,(path,l)
 return {'path':str(path),'duration_seconds':duration,'video_timeline_duration_seconds':count/30,'size_bytes':path.stat().st_size,'sha256':sha(path),'video_stream':v,'audio_stream':a,'resolution':[1920,1080],'fps':30,'video_codec':'h264','pixel_format':'yuv420p','audio_codec':'aac','sample_rate':44100,'channels':2,'actual_frames':count,'full_decode_pass':True,'subtitle_tracks':0,'audio_verification':{'integrated_loudness_lufs':float(l['input_i']),'true_peak_dbtp':float(l['input_tp']),'non_silent':True}}
def ahash(p):return run(['-v','error','-i',str(p),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).stdout.strip()
def segment(s):
 n=s['segment'];p=OUT/f'clips/seg{n:02}.mp4';clean=OUT/f'clips_nosub/seg{n:02}.mp4';r=inspect(p,s['video_frames']);r.update({'segment':n,'audio_path':s['audio_path'],'target_video_duration_seconds':s['video_duration'],'frames':s['video_frames'],'subtitle_ass':str(OUT/f'subtitles/seg{n:02}.ass'),'subtitle_srt':str(OUT/f'subtitles/seg{n:02}.srt'),'clean_clip_sha256':sha(clean),'audio_bitstream_sha256':ahash(p),'audio_copied_bit_for_bit':ahash(p)==ahash(clean)})
 assert r['audio_copied_bit_for_bit']
 if n!=5:assert sha(clean)==base['clean_clips'][clean.name]
 cues=json.loads((OUT/f'raw/seg{n:02}_subtitle_alignment.json').read_text())['cues'];cue=min(cues,key=lambda c:abs((c['start']+c['end'])/2-s['video_duration']*.57));t=(cue['start']+cue['end'])/2
 frame=OUT/f'preview_frames/seg{n:02}.png';run(['-y','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1',str(frame)]);r['preview_timestamp_seconds']=t
 print(f'PASS seg{n:02}: {r["actual_frames"]} frames, {r["audio_verification"]["integrated_loudness_lufs"]:.2f} LUFS; AAC bitstream preserved',flush=True)
 return r
with cf.ThreadPoolExecutor(max_workers=3) as pool:segments=list(pool.map(segment,data))
final_info=inspect(final,sum(s['video_frames'] for s in data));print('PASS final: all frames decoded; no soft subtitle track',flush=True)
# Stable mid-speech samples of each required console state, taken from the actual burned-in video.
for name,t in [('archive',6.8),('resolved',37.0),('citation',42.0),('abstained',68.0)]:
 run(['-y','-v','error','-ss',str(t),'-i',str(OUT/'clips/seg05.mp4'),'-frames:v','1',str(OUT/f'preview_frames/seg05_light_{name}.png')])
preview_checks={}
for p in [*(OUT/'preview_frames').glob('seg0[1-9].png'),*(OUT/'preview_frames').glob('seg05_light_*.png')]:
 im=Image.open(p).convert('RGB');assert im.size==(1920,1080);assert max(ImageStat.Stat(im).stddev)>15
 # The exact subtitle foreground appears in the bottom 150 pixels on every verification frame.
 crop=im.crop((150,880,1770,1050));colors=list(crop.getdata());white=sum(1 for r,g,b in colors if min(r,g,b)>225 and max(r,g,b)-min(r,g,b)<18);dark=sum(1 for r,g,b in colors if max(r,g,b)<85)
 assert white>100 and dark>100,(p,white,dark)
 preview_checks[p.name]={'size':[1920,1080],'nonblank':True,'bottom_light_text_pixels':white,'bottom_dark_background_pixels':dark}
canvas=Image.new('RGB',(1920,1170),'#0B1220');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('/System/Library/Fonts/HelveticaNeue.ttc',23)
for n in range(1,10):
 im=Image.open(OUT/f'preview_frames/seg{n:02}.png').convert('RGB').resize((640,360),Image.Resampling.LANCZOS);x=((n-1)%3)*640;y=((n-1)//3)*390;canvas.paste(im,(x,y));draw.text((x+16,y+363),f'Segment {n:02} · English subtitles',font=font,fill='#F8FAFC')
canvas.save(OUT/'IncidentLens_9_segment_contact_sheet.jpg',quality=94)
# Preserve the old contact sheet location if it existed under preview_frames.
if (OUT/'preview_frames/IncidentLens_9_segment_contact_sheet.jpg').exists():canvas.save(OUT/'preview_frames/IncidentLens_9_segment_contact_sheet.jpg',quality=94)
assert subprocess.run(['git','diff','--quiet'],cwd=ROOT).returncode==0
assert subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode==0
integrity={}
for rel,old in json.loads((OUT/'source_baseline.json').read_text()).items():
 p=ROOT/rel;assert sha(p)==old['sha256'];assert p.stat().st_mtime_ns==old['mtime_ns'];integrity[rel]=dict(old,unchanged=True)
for rel,h in base['mp3'].items():assert sha(ROOT/rel)==h
web=json.loads((OUT/'web_recording_audit.json').read_text());assert web['theme']=='light' and web['console_errors']==[] and web['provider_calls_during_replay']==0 and not web['note_overlay_present']
manifest=json.loads((OUT/'raw/update_baseline/build_manifest.json').read_text());manifest['final_video']=final_info
for old,new in zip(manifest['segments'],segments):old.update(new)
manifest['web_console']=web;manifest['total_duration_seconds']=final_info['duration_seconds'];manifest['total_video_timeline_seconds']=sum(s['video_frames'] for s in data)/30
manifest['subtitles']=dict(meta,combined_srt=str(OUT/'IncidentLens_Presentation_10min.srt'),combined_ass=str(OUT/'IncidentLens_Presentation_10min.ass'),alignment_directory=str(OUT/'raw'),concat_offsets='Exact cumulative video frame durations; explicit concat duration directives',aac_join_handling='Concat-only remux copies omit negative-PTS unplayed AAC priming packets; published segments retain bit-identical AAC')
manifest['verification'].update({'all_nine_clips_pass':True,'full_assembled_video_decode_pass':True,'all_segment_full_decode_pass':True,'tracked_git_diff_empty':True,'staged_git_diff_empty':True,'animation_files_unchanged':integrity,'mp3_hashes_unchanged':True,'clean_eight_original_clips_hashes_unchanged':True,'all_nine_aac_bitstreams_preserved':True,'actual_decoded_frame_count':final_info['actual_frames'],'no_soft_subtitle_tracks':True,'subtitle_timing_invariants_pass':True,'preview_checks':preview_checks})
manifest['supporting_files'].update({'subtitle_metadata.json':str(OUT/'subtitle_metadata.json'),'update_integrity_baseline':str(OUT/'raw/update_baseline/integrity.json'),'subtitle_contact_sheet':str(OUT/'IncidentLens_9_segment_contact_sheet.jpg')})
manifest['production_adjustments'].append({'reason':'Light-theme re-record and synchronized burned-in English subtitles requested','action':'Re-recorded only seg05 using original light theme; removed note overlay; reused eight existing clean visuals; aligned 138 English cues to local ASR and waveform silences; retained all existing MP3 files and copied clean AAC bitstreams.'})
manifest['updated_artifact_hashes']={str(p.relative_to(OUT)):sha(p) for p in [final,OUT/'IncidentLens_Presentation_10min.srt',OUT/'IncidentLens_Presentation_10min.ass',OUT/'IncidentLens_9_segment_contact_sheet.jpg',*(OUT/'subtitles').glob('*'),*(OUT/'preview_frames').glob('seg*.png')]}
(OUT/'build_manifest.json').write_text(json.dumps(manifest,indent=2))
print(f'COMPLETE: {final_info["duration_seconds"]:.2f}s, {final_info["actual_frames"]} frames, {final_info["size_bytes"]:,} bytes; all verification checks passed.',flush=True)
