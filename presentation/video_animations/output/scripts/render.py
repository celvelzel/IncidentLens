import base64, concurrent.futures as cf, hashlib,json,math,subprocess,time,sys
from pathlib import Path
import imageio_ffmpeg
from playwright.sync_api import sync_playwright
from prepare import BASE,OUT

URL='http://127.0.0.1:8767/'
DATA=json.loads((OUT/'narration.json').read_text())
NAMES={1:'slide1_title.html',3:'demo1_terminal.html',4:'demo2_cli.html',6:'demo4_bugfix.html',8:'slide8_limitations.html',9:'slide9_closing.html'}
ANIMS={1:'anim1_opening_hook.html',2:'anim2_architecture_variants.html',6:'anim3_audit_and_bugfix.html',7:'anim4_results_dashboard.html'}

def landmark(n,phrase,default):
    text=DATA[n-1]['text'];pos=text.find(phrase)
    return len(text[:pos].split())/len(text.split()) if pos>=0 else default

def build_composites():
    for n in [1,6]:
        a=ANIMS[n];s=NAMES[n];split=.82 if n==1 else .52
        doc=f'''<!doctype html><html><head><style>html,body{{margin:0;width:1920px;height:1080px;background:#0F172A;overflow:hidden}}iframe{{position:absolute;inset:0;width:1920px;height:1080px;border:0;pointer-events:none}}#b{{opacity:0}}</style></head><body><iframe id="a" src="../../{a}?t=0&paused=1&clean=1"></iframe><iframe id="b" src="{s}"></iframe><script>
        window.render=async(p)=>{{let split={split};const a=document.getElementById('a'),b=document.getElementById('b');const u=Math.max(0,Math.min(1,(p-split)/.025)); b.style.opacity=u;const time=Math.min(1,p/split)*{35 if n==1 else 30};const input=a.contentDocument.getElementById('timeline');input.value=time;input.dispatchEvent(new Event('input'));b.contentWindow.render(Math.max(0,(p-split)/(1-split)));await new Promise(r=>requestAnimationFrame(r));}};</script></body></html>'''
        (OUT/'stages'/f'composite{n}.html').write_text(doc)

def setup(browser,n):
    page=browser.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
    if n in [1,6]:path=f'output/stages/composite{n}.html'
    elif n in ANIMS:path=ANIMS[n]+'?t=0&paused=1&clean=1'
    else:path='output/stages/'+NAMES[n]
    page.goto(URL+path,wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(80)
    cdp=page.context.new_cdp_session(page)
    return page,cdp

def seek(page,n,t):
    seg=DATA[n-1];p=max(0,min(1,(t-.4)/seg['audio_duration']))
    if n in [1,6,3,4,8,9]:
        page.evaluate('async p=>{await window.render(p);await new Promise(r=>requestAnimationFrame(r))}',p)
    else:
        if n==2:
            split=landmark(2,'To evaluate whether',.76)
            v=p/split*38 if p<split else 38+(p-split)/(1-split)*22
        else:
            first=landmark(7,'To test whether',.33);second=landmark(7,'And look at',.68)
            v=p/first*35 if p<first else 35+(p-first)/(second-first)*25 if p<second else 60+(p-second)/(1-second)*35
        page.evaluate('async t=>{const e=document.getElementById("timeline");e.value=t;e.dispatchEvent(new Event("input"));await new Promise(r=>requestAnimationFrame(r))}',v)

def capture(cdp):
    return base64.b64decode(cdp.send('Page.captureScreenshot',{'format':'jpeg','quality':92,'fromSurface':True})['data'])

def render_segment(n):
    seg=DATA[n-1];frames=seg['video_frames'];duration=frames/30
    clip=OUT/f'clips/seg{n:02}.mp4';done=OUT/f'raw/seg{n:02}.done.json'
    if clip.exists() and done.exists():
        print(f'Segment {n:02} already rendered',flush=True);return
    ff=imageio_ffmpeg.get_ffmpeg_exe();log=OUT/f'raw/seg{n:02}_encode.log'
    with sync_playwright() as pw,log.open('w') as stderr:
        browser=pw.chromium.launch(channel='chrome',headless=True,args=['--hide-scrollbars','--disable-background-timer-throttling','--disable-renderer-backgrounding'])
        page,cdp=setup(browser,n)
        filter=f'[0:v]fade=t=in:st=0:d=0.35,fade=t=out:st={duration-.35}:d=0.35[v];[1:a]adelay=400|400,loudnorm=I=-16:TP=-1.5:LRA=11,apad,atrim=duration={duration},aformat=sample_rates=44100:channel_layouts=stereo[a]'
        cmd=[ff,'-y','-v','warning','-f','image2pipe','-vcodec','mjpeg','-framerate','30','-i','-','-i',seg['audio_path'],'-filter_complex',filter,'-map','[v]','-map','[a]','-c:v','libx264','-preset','medium','-crf','18','-threads','2','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-t',str(duration),'-movflags','+faststart',str(clip)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=stderr)
        start=time.monotonic()
        try:
            for frame in range(frames):
                seek(page,n,frame/30)
                data=capture(cdp)
                proc.stdin.write(data)
                if frame==int(frames*.57):
                    (OUT/f'preview_frames/seg{n:02}.jpg').write_bytes(data)
                if frame%600==0:print(f'Rendering {n:02}: {frame}/{frames} frames',flush=True)
            proc.stdin.close();code=proc.wait()
            if code:raise RuntimeError(f'Encoder {n} failed: see {log}')
        finally:
            browser.close()
            if proc.poll() is None:proc.terminate()
        done.write_text(json.dumps({'frames':frames,'duration':duration,'render_wall_seconds':time.monotonic()-start,'capture':'deterministic JPEG quality=92, 30fps, 1920x1080','animation_source_modified':False},indent=2))
        print(f'Finished segment {n:02}: {duration:.2f}s in {time.monotonic()-start:.1f}s',flush=True)

def previews():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome')
        for n in [1,2,3,4,6,7,8,9]:
            page,cdp=setup(browser,n)
            for p in ([.3,.7,.93] if n in [1,2,6,7] else [.14,.43,.85] if n in [3,4,8] else [.6]):
                seek(page,n,.4+p*DATA[n-1]['audio_duration']);page.screenshot(path=str(OUT/f'preview_frames/stage{n:02}_{int(p*100)}.png'))
                over=page.evaluate('Array.from(document.querySelectorAll("main pre")).filter(e=>e.getBoundingClientRect().bottom>985).length')
                print('Preview',n,p,'overflow pre blocks',over)
            page.close()
        browser.close()

if __name__=='__main__':
    build_composites()
    if '--previews' in sys.argv:previews()
    else:
        with cf.ProcessPoolExecutor(max_workers=3) as pool:
            for r in pool.map(render_segment,[7,2,1,6,4,3,8,9]):pass
