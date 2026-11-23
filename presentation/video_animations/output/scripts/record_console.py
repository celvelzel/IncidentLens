from pathlib import Path
import json,subprocess,time,math
from playwright.sync_api import sync_playwright
import imageio_ffmpeg
from prepare import ROOT,OUT

data=json.loads((OUT/'narration.json').read_text());seg=data[4];duration=seg['video_duration']
resolved=json.loads((ROOT/'results/demo_video_resolved/trace.json').read_text());state=resolved['state']
abstained=json.loads((ROOT/'results/demo_video_abstain/trace.json').read_text())
requests=sum(e.get('details',{}).get('actual_http_requests',e.get('details',{}).get('llm_calls',0)) for e in state['events'] if e['event_type'] in ['LLM_CALL','MODEL_FAILURE'])
errors=[];network=[];actions=[];screenshots=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='chrome',headless=True)
    ctx=browser.new_context(viewport={'width':1920,'height':1080},device_scale_factor=1,record_video_dir=str(OUT/'raw/web_console'),record_video_size={'width':1920,'height':1080},color_scheme='light')
    ctx.add_init_script("localStorage.setItem('incident-lens-lang','en');localStorage.setItem('incident-lens-theme','light')")
    page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:network.append({'method':r.method,'url':r.url}))
    page.goto('http://127.0.0.1:8022/?lang=en#/',wait_until='networkidle')
    page.evaluate('''()=>{document.documentElement.style.zoom='1.15';const s=document.createElement('style');s.textContent=`#video-cursor{position:fixed;width:17px;height:17px;border:2px solid #A02337;border-radius:50%;background:#A02337;box-shadow:0 0 0 3px #fff,0 2px 9px #0006;z-index:2147483647;pointer-events:none;transform:translate(-50%,-50%)} .mono,.hypothesis-card,.hypothesis-card *{overflow-wrap:anywhere} .video-highlight{outline:2.5px solid #A02337!important;outline-offset:5px;box-shadow:0 0 18px #a0233735!important}`;document.head.appendChild(s);const d=document.createElement('div');d.id='video-cursor';document.body.appendChild(d);document.addEventListener('mousemove',e=>{d.style.left=e.clientX+'px';d.style.top=e.clientY+'px'})}''')
    start=time.monotonic()
    def until(f):
        remain=start+f*duration-time.monotonic()
        if remain>0:page.wait_for_timeout(remain*1000)
    def focus(locator):
        locator=locator.first;locator.evaluate("e=>e.scrollIntoView({block:'center',behavior:'smooth'})");page.wait_for_timeout(300)
        box=locator.bounding_box()
        if box:page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2,steps=18)
        locator.evaluate("e=>{document.querySelectorAll('.video-highlight').forEach(x=>x.classList.remove('video-highlight'));e.classList.add('video-highlight')}")
    def click(locator,label):
        focus(locator);locator.first.click();actions.append({'seconds':time.monotonic()-start,'action':label})
    def archive(keyword):
        click(page.locator('a[href="#/library"]').first,'Open Trace Archive')
        page.wait_for_selector('#lib-search');page.locator('#lib-search').fill(keyword);page.wait_for_timeout(200)
    def open_row(path):
        click(page.locator(f'tr[data-trace-path="{path}"]'),'Open '+path);page.wait_for_selector('#replay-seek')
    def last():
        button=page.locator('[data-step="last"]')
        if button.is_enabled():click(button,'Seek final persisted event')
    def screenshot(name):
        screenshots.append({'name':name,'seconds':time.monotonic()-start});page.screenshot(path=str(OUT/f'preview_frames/{name}.png'))
    until(.045)
    archive('demo_video')
    screenshot('web_archive')
    until(.105)
    open_row('results/demo_video_resolved/trace.json')
    focus(page.locator('.replay-heading'));screenshot('web_replay_banner')
    until(.18)
    timeline=page.locator('details').filter(has=page.locator('#replay-events'))
    if not timeline.get_attribute('open'):click(timeline.locator('summary'),'Expand Communication Timeline')
    targets=['DECISION','TASK_ASSIGNED','TOOL_CALL','MERGE','DIAGNOSIS_ACCEPTED']
    for i,kind in enumerate(targets):
        index=next(i+1 for i,e in enumerate(state['events']) if e['event_type']==kind)
        click(page.locator(f'#replay-events [data-seek="{index}"]'),f'Inspect {kind}')
        focus(page.locator('#replay-selection'))
        until(.20+i*.028)
    until(.34)
    last()
    # Collapse the long orchestration summary to make the actual detail tabs easy to follow.
    panel=page.locator('#replay-workflow-panel')
    if panel.get_attribute('open') is not None:click(panel.locator('summary'),'Collapse workflow overview')
    click(page.locator('[data-tab="hypotheses"]'),'Open Hypothesis Board')
    focus(page.locator('#run-tab-panel'));screenshot('web_hypotheses')
    until(.46)
    click(page.locator('[data-tab="report"]'),'Open final root-cause report')
    focus(page.locator('.report-hero'));page.wait_for_timeout(350);screenshot('web_resolved')
    until(.515)
    citation=page.locator('#run-tab-panel [data-evidence-id]').first
    cid=citation.get_attribute('data-evidence-id');click(citation,'Audit report citation '+cid)
    page.wait_for_selector('#drawer:not([hidden])')
    page.wait_for_timeout(450);screenshot('web_citation')
    until(.61)
    click(page.locator('#drawer-close'),'Close citation inspector')
    # The app's persisted prefix UI exposes stop events directly.
    focus(timeline.locator('summary'))
    page.locator('#replay-category').select_option('termination')
    focus(page.locator('#replay-events'))
    screenshot('web_stop_protocol')
    until(.67)
    last();metadata=page.locator('#replay-metadata')
    if metadata.get_attribute('open') is None:click(metadata.locator('summary'),'Open recorded run metadata')
    focus(metadata)
    screenshot('web_resource_ledger')
    until(.755)
    archive('demo_video_abstain');open_row('results/demo_video_abstain/trace.json');last()
    panel=page.locator('#replay-workflow-panel')
    if panel.get_attribute('open') is not None:click(panel.locator('summary'),'Collapse abstained workflow overview')
    click(page.locator('[data-tab="report"]'),'Inspect abstained report')
    focus(page.locator('.report-hero'));page.wait_for_timeout(350);screenshot('web_abstained')
    until(.89)
    focus(page.locator('#run-tab-panel'))
    page.wait_for_timeout(350);screenshot('web_abstained_gaps')
    until(.96)
    # Raw Markdown gives the viewer the actual causal gaps without substituting a synthetic report.
    raw=page.locator('.report-raw-summary')
    if raw.count():click(raw,'Open original abstained report Markdown');focus(page.locator('.report-raw'))
    until(1)
    rawpath=page.video.path()
    ctx.close();browser.close()

assert not errors,errors
assert not any('/api/run' in r['url'] for r in network),'Replay unexpectedly invoked a provider run'
(OUT/'web_recording_audit.json').write_text(json.dumps({'browser':'System Google Chrome via Playwright','theme':'light','note_overlay_present':False,'cursor_color':'#A02337','viewport':[1920,1080],'zoom':1.15,'genuine_live_recording':True,'console_errors':errors,'requests':network,'provider_calls_during_replay':0,'actions':actions,'screenshots':screenshots,'resolved_trace':'results/demo_video_resolved/trace.json','abstained_trace':'results/demo_video_abstain/trace.json','raw_video':str(rawpath),'raw_duration_seconds':None,'stop_ack_note':'No STOP_ACK event in this recorded trace; required_roles is empty. No synthetic acknowledgment is inserted.','resource_ledger':{'http_requests':requests,'tools':state['tool_calls_used'],'tokens':state['tokens_used']}},indent=2))
ff=imageio_ffmpeg.get_ffmpeg_exe()
probe=subprocess.run([ff,'-i',str(rawpath)],capture_output=True,text=True).stderr
import re
m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe);original=int(m[1])*3600+int(m[2])*60+float(m[3])
audit=json.loads((OUT/'web_recording_audit.json').read_text());audit['raw_duration_seconds']=original;(OUT/'web_recording_audit.json').write_text(json.dumps(audit,indent=2))
vf=f'setpts={duration/original:.10f}*PTS,fps=30,scale=1920:1080,setsar=1,fade=t=in:st=0:d=0.35,fade=t=out:st={duration-.35}:d=0.35'
af=f'adelay=400|400,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=duration={duration},aformat=sample_rates=44100:channel_layouts=stereo'
with (OUT/'raw/seg05_encode.log').open('w') as log:
    subprocess.run([ff,'-y','-v','warning','-i',str(rawpath),'-i',seg['audio_path'],'-vf',vf,'-af',af,'-c:v','libx264','-preset','medium','-crf','18','-threads','2','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-t',str(duration),'-movflags','+faststart',str(OUT/'clips_nosub/seg05.mp4')],check=True,stderr=log)
print(f'Web Console recorded and muxed: {duration:.2f}s; {len(actions)} actual interactions; zero provider calls',flush=True)
