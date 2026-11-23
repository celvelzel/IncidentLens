"""A factual replacement for the one voiceover whose assumed live outcome changed."""
import json,re,subprocess,urllib.request,math
from prepare import OUT,BASE,ROOT,secrets
import imageio_ffmpeg
from incident_lens.artifacts import save_run,load_replay
from incident_lens.schemas import InvestigationState

data=json.loads((OUT/'narration.json').read_text());seg=data[3]
if not (OUT/'narration_live_correction.json').exists():
    original=seg['text']
    start=original.index('In under a minute,')
    end=original.index('Next, let',start)
    replacement='This live run finishes with inconclusive and writes result dot JSON, report dot M-D, and trace dot JSON. The report preserves the leading explanations, observed evidence, and causal gaps. A confirmed root cause remains null: the system does not turn a plausible explanation into a claim it cannot verify. '
    text=original[:start]+replacement+original[end:]
    payload={'text':text,'model_id':'eleven_multilingual_v2','voice_settings':{'stability':.50,'similarity_boost':.78,'style':.15,'use_speaker_boost':True}}
    req=urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{secrets['ELEVENLABS_VOICE_ID']}?output_format=mp3_44100_128",data=json.dumps(payload).encode(),headers={'xi-api-key':secrets['ELEVENLABS_API_KEY'],'Content-Type':'application/json'})
    path=OUT/'raw/seg04_live_corrected_original.mp3'
    if not path.exists():
        try:
            with urllib.request.urlopen(req,timeout=240) as r:path.write_bytes(r.read())
        except Exception as e:raise RuntimeError(type(e).__name__) from None
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    probe=subprocess.run([ff,'-i',str(path)],capture_output=True,text=True).stderr
    m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);dur=int(m[1])*3600+int(m[2])*60+float(m[3])
    factor=dur/seg['audio_duration']
    subprocess.run([ff,'-y','-v','error','-i',str(path),'-af',f'atempo={factor}','-c:a','libmp3lame','-b:a','128k',seg['audio_path']],check=True)
    correction={'reason':'Actual live hy4 run abstained; source script assumed RESOLVED and a sub-minute runtime.','original_text':original,'replacement_text':text,'original_duration':dur,'tempo_factor':factor,'target_duration':seg['audio_duration']}
    (OUT/'narration_live_correction.json').write_text(json.dumps(correction,indent=2))
    seg['text']=text;seg['factual_live_outcome_correction']=True
    (OUT/'narration.json').write_text(json.dumps(data,indent=2))

# Export a genuine completed cross-model state through the repository's validated
# artifact writer, with no edits to state, events, evidence, or run identity.
source=ROOT/'results/repro-ohmygpt-hy4-flash-nothink-24slots/states/incident_4014.dynamic.json'
dest=ROOT/'results/demo_video_resolved'
if not (dest/'trace.json').exists():
    state=InvestigationState.model_validate_json(source.read_text())
    save_run(state,dest,'real','dynamic','off')
trace,state=load_replay(dest/'trace.json')
(OUT/'resolved_trace_provenance.json').write_text(json.dumps({'source_state':str(source),'exported_trace':str(dest/'trace.json'),'status':state.report.status,'run_id':state.run_id,'events':len(state.events),'export_method':'save_run with original validated state; no synthetic events; no new provider call'},indent=2))
print('Corrected live narration and validated resolved archive:',state.report.status)
