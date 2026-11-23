from pathlib import Path
import concurrent.futures as cf
import hashlib,json,re,subprocess
import imageio_ffmpeg
from prepare import ROOT,BASE,OUT,secrets

FF=imageio_ffmpeg.get_ffmpeg_exe()
data=json.loads((OUT/'narration.json').read_text())
titles=['Opening Hook & Core Contract','Architecture & Four Variants','CLI Data, ACL & Reliability','Real Cross-Model CLI Run','Web Console Recorded Replay','Anti-Leakage Audit & Bug Fix','Full-Scale & Cross-Model Results','Limitations & Future Work','Closing Summary']
def inspect(path,audio_check=True):
    probe=subprocess.run([FF,'-hide_banner','-i',str(path)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe)
    duration=int(m[1])*3600+int(m[2])*60+float(m[3])
    video=next(x.strip() for x in probe.splitlines() if 'Stream #' in x and 'Video:' in x)
    audio=next(x.strip() for x in probe.splitlines() if 'Stream #' in x and 'Audio:' in x)
    assert '1920x1080' in video and '30 fps' in video and 'h264' in video,video
    assert 'aac' in audio and '44100 Hz' in audio and 'stereo' in audio,audio
    result={'path':str(path),'duration_seconds':duration,'size_bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'video_stream':video,'audio_stream':audio,'resolution':[1920,1080],'fps':30,'video_codec':'h264','audio_codec':'aac','sample_rate':44100,'channels':2}
    if audio_check:
        p=subprocess.run([FF,'-hide_banner','-nostats','-i',str(path),'-vn','-af','volumedetect,loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True)
        assert p.returncode==0
        mean=float(re.search(r'mean_volume: ([\-\d.]+)',p.stderr)[1]);peak=float(re.search(r'max_volume: ([\-\d.]+)',p.stderr)[1])
        loud=json.loads(re.search(r'\{\s*"input_i".*?\}',p.stderr,re.S)[0])
        assert mean>-35 and abs(float(loud['input_i'])+16)<2.0,(path,mean,loud)
        result['audio_verification']={'mean_volume_db':mean,'max_volume_db':peak,'integrated_loudness_lufs':float(loud['input_i']),'true_peak_dbtp':float(loud['input_tp']),'non_silent':True}
    return result

def segment(seg):
    n=seg['segment'];path=OUT/f'clips/seg{n:02}.mp4'
    result=inspect(path)
    assert abs(result['duration_seconds']-seg['video_duration'])<.06,(n,result['duration_seconds'],seg['video_duration'])
    frame_probe=subprocess.run([FF,'-v','error','-nostats','-i',str(path),'-map','0:v:0','-c','copy','-progress','pipe:1','-f','null','-'],capture_output=True,text=True,check=True)
    actual_frames=int(re.findall(r'frame=(\d+)',frame_probe.stdout)[-1])
    assert actual_frames==seg['video_frames'],(n,actual_frames,seg['video_frames'])
    result['actual_frames']=actual_frames
    mp3_probe=subprocess.run([FF,'-i',seg['audio_path']],capture_output=True,text=True).stderr
    am=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',mp3_probe)
    actual_audio=int(am[1])*3600+int(am[2])*60+float(am[3])
    assert 1.15<=seg['video_duration']-actual_audio<=1.28,(n,actual_audio,seg['video_duration'])
    for frac,label in [(.57,'')]+([(.49,'_resolved'),(.86,'_abstained')] if n==5 else []):
        image=OUT/f'preview_frames/seg{n:02}{label}.png'
        subprocess.run([FF,'-y','-v','error','-ss',str(seg['video_duration']*frac),'-i',str(path),'-frames:v','1',str(image)],check=True)
    result.update({'segment':n,'title':titles[n-1],'audio_path':seg['audio_path'],'audio_duration_seconds':actual_audio,'target_video_duration_seconds':seg['video_duration'],'frames':seg['video_frames'],'audio_delay_seconds':.4,'visual_settle_seconds':.8,'audio_size_bytes':Path(seg['audio_path']).stat().st_size})
    print(f'Verified segment {n:02}: {result["duration_seconds"]:.2f}s; {result["audio_verification"]["integrated_loudness_lufs"]:.1f} LUFS',flush=True)
    return result

if __name__=='__main__':
    with cf.ThreadPoolExecutor(max_workers=3) as pool: segments=list(pool.map(segment,data))
    concat=OUT/'raw/concat.txt';concat.write_text(''.join(f"file '{OUT}/clips/seg{n:02}.mp4'\n" for n in range(1,10)))
    final=OUT/'IncidentLens_Presentation_10min.mp4'
    log=OUT/'raw/concat.log'
    with log.open('w') as stderr:subprocess.run([FF,'-y','-hide_banner','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(final)],check=True,stdout=subprocess.DEVNULL,stderr=stderr)
    final_info=inspect(final)
    assert 540<=final_info['duration_seconds']<=630
    assert abs(final_info['duration_seconds']-sum(x['target_video_duration_seconds'] for x in segments))<.35
    # Decode every frame in the assembled video: catches corruption across joins.
    decode=subprocess.run([FF,'-v','error','-nostats','-i',str(final),'-progress','pipe:1','-f','null','-'],capture_output=True,text=True)
    assert decode.returncode==0 and not decode.stderr.strip(),decode.stderr[-1000:]
    actual_final_frames=int(re.findall(r'frame=(\d+)',decode.stdout)[-1])
    assert actual_final_frames==sum(x['frames'] for x in segments)
    final_info['actual_frames']=actual_final_frames
    baseline=json.loads((OUT/'source_baseline.json').read_text());integrity={}
    for rel,old in baseline.items():
        p=ROOT/rel;now={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime_ns':p.stat().st_mtime_ns}
        assert old==now,(rel,old,now)
        integrity[rel]=dict(now,unchanged=True)
    assert subprocess.run(['git','diff','--quiet'],cwd=ROOT).returncode==0
    assert subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode==0
    leaks=[]
    sensitive=[v.encode() for k,v in secrets.items() if v and any(w in k for w in ['KEY','TOKEN','SECRET'])]
    for folder in [OUT,BASE/'voiceover_audio']:
        for p in folder.rglob('*'):
            if p.is_file() and p.stat().st_size<20_000_000:
                blob=p.read_bytes()
                if any(v in blob for v in sensitive):leaks.append(str(p))
    assert not leaks,'Sensitive values found in output artifacts'
    stage_violations=[]
    for p in (OUT/'stages').glob('*.html'):
        if re.search(r'\brepro(?:duction)?\b',p.read_text(),re.I):stage_violations.append(str(p))
    assert not stage_violations
    manifest={'project':'IncidentLens','final_video':final_info,'segments':segments,'total_duration_seconds':final_info['duration_seconds'],'total_frames_expected':sum(x['frames'] for x in segments),'encoding':{'resolution':'1920x1080','frame_rate':'30/1','video_codec':'H.264 / libx264','pixel_format':'yuv420p','preset':'medium','crf':18,'audio_codec':'AAC','audio_bitrate':'192k','sample_rate':44100,'channels':2,'loudness_target_lufs':-16,'faststart':True},'verification':{'all_nine_clips_pass':True,'full_assembled_video_decode_pass':True,'tracked_git_diff_empty':True,'staged_git_diff_empty':True,'animation_files_unchanged':integrity,'secret_scan_pass':True,'generated_stage_framing_pass':True,'preview_directory':str(OUT/'preview_frames')},'production_adjustments':[{'reason':'Voice default pace exceeded duration target','action':'Uniform pitch-preserving atempo; original ElevenLabs MP3 files retained in voiceover_audio/originals.'},{'reason':'CLI accepts ohmygpt, artifact metadata accepts only real/mock','action':'Build-only adapter classifies live OhMyGPT as real; project source untouched. Original CLI failed after completing provider work; one replacement live investigation was required.'},{'reason':'Live Hunyuan investigation emitted INCONCLUSIVE','action':'Preserved actual outputs. Corrected segment 4 voiceover once to describe abstention. Console resolved walkthrough uses an unchanged completed Hunyuan experimental state exported with repository save_run.'},{'reason':'Requested pytest -k leading_review selected zero tests','action':'Ran matching -k review_leading; one test passed. Both exact outputs retained.'},{'reason':'Existing reliability matrix omitted summary.json','action':'Derived 110/110 summary from existing authentic fault-matrix.csv; no matrix claims invented.'},{'reason':'Resolved trace has required_roles=[] and no STOP_ACK','action':'Recording explicitly says STOP_ACK not required; no synthetic event added.'}],'supporting_files':{name:str(OUT/name) for name in ['captured_demos.json','narration.json','narration_live_correction.json','resolved_trace_provenance.json','web_recording_audit.json','audio_pacing.json']},'web_console':json.loads((OUT/'web_recording_audit.json').read_text()),'original_animation_baseline':str(OUT/'source_baseline.json')}
    manifest['production_adjustments'].append({'reason':'Persisted incident_4018.dynamic state and experiment record contain 15 tools, while the supplied brief says 12.','action':'The final comparison and segment 4 narration use the actual count of 15.'})
    manifest['audio_final_level_corrections']=[json.loads((OUT/f'raw/seg{n:02}_loudness.json').read_text()) for n in range(1,10)]
    manifest['supporting_files']['narration_tool_count_correction.json']=str(OUT/'narration_tool_count_correction.json')
    manifest['verification']['actual_decoded_frame_count']=actual_final_frames
    (OUT/'build_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'COMPLETE: {final_info["duration_seconds"]:.2f}s, {final_info["size_bytes"]:,} bytes; all checks passed',flush=True)
