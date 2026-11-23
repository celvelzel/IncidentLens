import json,re,subprocess,math
import imageio_ffmpeg
from prepare import BASE,OUT
ff=imageio_ffmpeg.get_ffmpeg_exe()
data=json.loads((OUT/'narration.json').read_text())
if not (OUT/'audio_pacing.json').exists():
    original=BASE/'voiceover_audio/originals';original.mkdir(exist_ok=True)
    factor=sum(x['audio_duration'] for x in data)/(600-9*1.2)
    for item in data:
        p=BASE/f'voiceover_audio/seg{item["segment"]:02}.mp3'
        copy=original/p.name
        if not copy.exists():copy.write_bytes(p.read_bytes())
        temp=p.with_name(p.stem+'_paced.mp3')
        subprocess.run([ff,'-y','-v','error','-i',str(copy),'-af',f'atempo={factor:.9f}','-c:a','libmp3lame','-b:a','128k',str(temp)],check=True)
        temp.replace(p)
        item['original_audio_duration']=item['audio_duration']
        item['tempo_factor']=factor
        probe=subprocess.run([ff,'-i',str(p)],capture_output=True,text=True).stderr
        m=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',probe)
        item['audio_duration']=int(m[1])*3600+int(m[2])*60+float(m[3])
        item['video_frames']=math.ceil((item['audio_duration']+1.2)*30)
        item['video_duration']=item['video_frames']/30
    (OUT/'audio_pacing.json').write_text(json.dumps({'tempo_factor':factor,'target_total_seconds':600,'pitch_preserved':True,'original_directory':str(original)},indent=2))
    (OUT/'narration.json').write_text(json.dumps(data,indent=2))
print('Paced audio:',sum(x['audio_duration'] for x in data),'seconds; video:',sum(x['video_duration'] for x in data))
