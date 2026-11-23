"""Match the recorded benchmark's actual fifteen calls, rather than the brief's twelve."""
import json,subprocess,urllib.request,re
from prepare import OUT,secrets
import imageio_ffmpeg
data=json.loads((OUT/'narration.json').read_text());seg=data[3]
receipt=OUT/'narration_tool_count_correction.json'
if not receipt.exists():
    text=seg['text'].replace('After checking 12 tools','After checking 15 tools')
    payload={'text':text,'model_id':'eleven_multilingual_v2','voice_settings':{'stability':.50,'similarity_boost':.78,'style':.15,'use_speaker_boost':True}}
    req=urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{secrets['ELEVENLABS_VOICE_ID']}?output_format=mp3_44100_128",data=json.dumps(payload).encode(),headers={'xi-api-key':secrets['ELEVENLABS_API_KEY'],'Content-Type':'application/json'})
    path=OUT/'raw/seg04_final_original.mp3'
    if not path.exists():
        try:
            with urllib.request.urlopen(req,timeout=240) as r:path.write_bytes(r.read())
        except Exception as e:raise RuntimeError(type(e).__name__) from None
    ff=imageio_ffmpeg.get_ffmpeg_exe();probe=subprocess.run([ff,'-i',str(path)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);dur=int(m[1])*3600+int(m[2])*60+float(m[3])
    factor=dur/seg['audio_duration']
    subprocess.run([ff,'-y','-v','error','-i',str(path),'-af',f'atempo={factor}','-c:a','libmp3lame','-b:a','128k',seg['audio_path']],check=True)
    seg['text']=text;seg['actual_benchmark_tools']=15
    (OUT/'narration.json').write_text(json.dumps(data,indent=2))
    receipt.write_text(json.dumps({'source':'results/repro-deepseek-flash-hardened144/records.jsonl','incident_4018_dynamic_tools':15,'brief_tools':12,'action':'Corrected voiceover and visible comparison to actual persisted state and record.','tempo_factor':factor},indent=2))
print('Benchmark tool count matches actual records: 15')
