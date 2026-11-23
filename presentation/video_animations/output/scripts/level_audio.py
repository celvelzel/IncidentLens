"""Apply the small measured loudness correction after dynamic loudnorm encoding."""
import concurrent.futures as cf
import hashlib,json,re,subprocess
import imageio_ffmpeg
from prepare import OUT
FF=imageio_ffmpeg.get_ffmpeg_exe()
data=json.loads((OUT/'narration.json').read_text())
def level(seg):
    n=seg['segment'];path=OUT/f'clips/seg{n:02}.mp4';receipt=OUT/f'raw/seg{n:02}_loudness.json'
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if receipt.exists() and json.loads(receipt.read_text())['output_sha256']==digest:return
    p=subprocess.run([FF,'-hide_banner','-nostats','-i',str(path),'-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    loud=json.loads(re.search(r'\{\s*"input_i".*?\}',p.stderr,re.S)[0]);gain=-16-float(loud['input_i'])
    assert float(loud['input_tp'])+gain<=-1.5
    temp=path.with_name(path.stem+'_leveled.mp4')
    subprocess.run([FF,'-y','-v','error','-i',str(path),'-map','0:v:0','-map','0:a:0','-c:v','copy','-af',f'volume={gain:.5f}dB','-c:a','aac','-b:a','192k','-ar','44100','-ac','2','-t',str(seg['video_duration']),'-movflags','+faststart',str(temp)],check=True)
    temp.replace(path)
    receipt.write_text(json.dumps({'input_sha256':digest,'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'before_integrated_lufs':float(loud['input_i']),'gain_db':gain,'target_lufs':-16,'preserved_video_stream':True},indent=2))
    print(f'Final audio level {n:02}: applied {gain:+.2f} dB',flush=True)
if __name__=='__main__':
    with cf.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(level,data))
