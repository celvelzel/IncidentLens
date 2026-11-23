from pathlib import Path
import concurrent.futures as cf
import hashlib, json, os, re, subprocess, time, urllib.request
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'presentation/video_animations'
OUT=BASE/'output'
for folder in ['scripts','stages','clips','preview_frames','raw']:
    (OUT/folder).mkdir(parents=True, exist_ok=True)
secrets=dotenv_values(ROOT/'.env')
def clean_secret(s):
    for k,v in secrets.items():
        if v and ('KEY' in k or 'TOKEN' in k or 'SECRET' in k): s=s.replace(v,'[REDACTED]')
    return s
def save(name,data): (OUT/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
if not (OUT/'source_baseline.json').exists():
    save('source_baseline.json',{str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime_ns':p.stat().st_mtime_ns} for p in BASE.glob('anim*.html')})

def voiceovers():
    import imageio_ffmpeg
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    source=(BASE/'英文口播稿_English_Voiceover.md').read_text()
    pairs=[('incident_4014','incident 4014'),('incident_4018','incident 4018'),('incident_4035','incident 4035'),('postgres_lock_contention','Postgres lock contention'),('leading_review_consistency','leading review consistency'),('structured_output.py','structured output dot pie'),('scorer.py','scorer dot pie'),('statistics.py','statistics dot pie'),('result.json','result dot JSON'),('report.md','report dot M-D'),('trace.json','trace dot JSON'),('validate-data','validate data'),('FinalizeGate','Finalize Gate'),('deepseek-flash','DeepSeek Flash'),('hy4-flash','H-Y-4 Flash'),('json_schema','JSON schema'),('localhost:8022','localhost 8022'),('WORKFLOW_STOP_REQUESTED','Workflow Stop Requested'),('STOP_ACK','Stop Ack'),('NORMAL_TERMINATION','Normal Termination'),('INCONCLUSIVE','inconclusive'),('RESOLVED','resolved'),('OhMyGPT','Oh My G-P-T'),('ACLs','A-C-Ls'),('CoT','chain of thought')]
    segments=[]
    for n in range(1,10):
        block=re.search(r'### Segment '+str(n)+r':(.*?)(?=\n### Segment |\n## Appendix)',source,re.S).group(1)
        v=block.split('> **[Voiceover]**',1)[1]
        lines=[]
        for line in v.splitlines():
            if line.startswith('>'):
                line=re.sub(r'^>\s*','',line)
                if not line.strip().startswith('*(Let it complete'): lines.append(line)
        spoken=' '.join(lines).replace('**','').replace('`','').replace('*','')
        for a,b in pairs: spoken=spoken.replace(a,b)
        segments.append({'segment':n,'text':spoken,'words':len(spoken.split())})
    save('narration.json',segments)
    def generate(seg):
        n=seg['segment']; path=BASE/f'voiceover_audio/seg{n:02}.mp3'
        if not path.exists() or path.stat().st_size<=15000:
            payload={'text':seg['text'],'model_id':'eleven_multilingual_v2','voice_settings':{'stability':.50,'similarity_boost':.78,'style':.15,'use_speaker_boost':True}}
            req=urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{secrets['ELEVENLABS_VOICE_ID']}?output_format=mp3_44100_128",data=json.dumps(payload).encode(),headers={'xi-api-key':secrets['ELEVENLABS_API_KEY'],'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=240) as resp: data=resp.read()
            except Exception as e: raise RuntimeError(f'TTS segment {n}: {type(e).__name__}') from None
            tmp=path.with_suffix('.partial'); tmp.write_bytes(data); tmp.replace(path)
        p=subprocess.run([ff,'-i',str(path)],capture_output=True,text=True)
        m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',p.stderr)
        seg['audio_duration']=int(m[1])*3600+int(m[2])*60+float(m[3]); seg['audio_path']=str(path)
        print(f"Voice {n:02}: {seg['audio_duration']:.2f}s",flush=True)
        return seg
    with cf.ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(generate,segments))
    save('narration.json',result)

def demos():
    data=json.loads((OUT/'captured_demos.json').read_text()) if (OUT/'captured_demos.json').exists() else {}
    def command(key,args):
        if key in data and data[key]['returncode']==0: return
        print('Running '+key,flush=True); started=time.time()
        p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
        data[key]={'command':' '.join(args),'stdout':clean_secret(p.stdout),'stderr':clean_secret(p.stderr),'returncode':p.returncode,'elapsed_seconds':time.time()-started}
        save('captured_demos.json',data)
        print(f'{key}: exit {p.returncode} ({time.time()-started:.1f}s)',flush=True)
    command('validate',['.venv/bin/python','-m','incident_lens.cli','validate-data'])
    command('acl',['.venv/bin/pytest','tests/isolation/test_tool_acl.py','-v'])
    command('regression',['.venv/bin/pytest','tests/unit','tests/evaluation','tests/reliability','tests/isolation','-q'])
    if not (ROOT/'results/offline-reliability-eval/fault-matrix.csv').exists():
        command('reliability_run',['.venv/bin/python','scripts/run_reliability_eval.py','--out','results/offline-reliability-eval'])
    if not (ROOT/'results/offline-reliability-eval/summary.json').exists():
        import csv
        rows=list(csv.DictReader((ROOT/'results/offline-reliability-eval/fault-matrix.csv').open()))
        summary={'cases':len(rows),'matrix_passed':sum(r['passed']=='True' for r in rows),'matrix_total':len(rows),'derived_from':'fault-matrix.csv'}
        (ROOT/'results/offline-reliability-eval/summary.json').write_text(json.dumps(summary,indent=2))
    if (ROOT/'results/offline-reliability-eval/summary.json').exists(): data['reliability_summary']=json.loads((ROOT/'results/offline-reliability-eval/summary.json').read_text())
    if not (ROOT/'results/demo_video_hy4/trace.json').exists():
        if 'hy4' in data and data['hy4']['returncode']!=0: data['hy4_original_cli_failure']=data.pop('hy4')
        command('hy4',['.venv/bin/python',str(OUT/'scripts/live_cli_adapter.py'),'run','--case','incident_001','--provider','ohmygpt','--response-format','json_schema','--thinking','disabled','--variant','dynamic','--out','results/demo_video_hy4'])
    if not (ROOT/'results/demo_video_abstain/trace.json').exists():
        command('abstain',['.venv/bin/python','-m','incident_lens.cli','run','--case','incident_006','--provider','mock','--cache-mode','off','--variant','dynamic','--out','results/demo_video_abstain'])
    command('bugfix',['.venv/bin/pytest','tests/unit/test_structured_output_v13.py','-k','leading_review','-v'])
    if data['bugfix']['returncode']!=0:
        data['bugfix_original_selector']=data.pop('bugfix')
        command('bugfix',['.venv/bin/pytest','tests/unit/test_structured_output_v13.py','-k','review_leading','-v'])
    for name in ['hy4','abstain']:
        folder=ROOT/('results/demo_video_'+name)
        data[name+'_report']=(folder/'report.md').read_text()
        data[name+'_result']=json.loads((folder/'result.json').read_text())
    data['comparison']={cid:json.loads((ROOT/f'results/repro-deepseek-flash-hardened144/states/{cid}.dynamic.json').read_text()) for cid in ['incident_4014','incident_4018']}
    data['safe_repair_source']='\n'.join((ROOT/'src/incident_lens/llm/structured_output.py').read_text().splitlines()[30:57])
    save('captured_demos.json',data)
if __name__=='__main__':
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(voiceovers),pool.submit(demos)]
        for task in tasks: task.result()
