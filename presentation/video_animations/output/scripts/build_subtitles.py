"""Reference-text/ASR alignment refined against actual silence boundaries."""
from pathlib import Path
import json,re,difflib,math,textwrap
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'presentation/video_animations/output';SUB=OUT/'subtitles';SUB.mkdir(exist_ok=True)
HEADER='''[Script Info]
Title: IncidentLens — synchronized English subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Helvetica Neue,36,&H00F8FAFC,&H00F8FAFC,&H380B1220,&H380B1220,0,0,0,0,100,100,0,0,3,11,0,2,150,150,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
PAIRS=[('JSON schema','json_schema'),('Oh My G-P-T','OhMyGPT'),('H-Y-4 Flash','hy4-flash'),('DeepSeek Flash','deepseek-flash'),("Finalize Gate's","FinalizeGate's"),('Finalize Gate','FinalizeGate'),('structured output dot pie','structured_output.py'),('scorer dot pie','scorer.py'),('statistics dot pie','statistics.py'),('result dot JSON','result.json'),('report dot M-D','report.md'),('trace dot JSON','trace.json'),('leading review consistency','leading_review_consistency'),('validate data','validate-data'),('localhost 8022','localhost:8022'),('Workflow Stop Requested','WORKFLOW_STOP_REQUESTED'),('Stop Ack','STOP_ACK'),('Normal Termination','NORMAL_TERMINATION'),('incident 4014','incident_4014'),('incident 4018','incident_4018'),('incident 4035','incident_4035'),('Postgres lock contention','postgres_lock_contention'),('inconclusive','INCONCLUSIVE'),('resolved','RESOLVED'),('A-C-Ls','ACLs')]
def norm(w):return re.sub(r'[^a-z0-9]','',w.lower())
def weight(w):
 # Spoken form is the weighting source, including spelled acronyms and technical phrases.
 if re.fullmatch(r'[A-Z][A-Z-]+',w.strip('.,:;!?')):return max(1,len(re.sub('[^A-Z]','',w)))
 return max(1,len(re.findall(r'[aeiouy]+',w.lower())))
def wrap(tokens):
 text=' '.join(x['text'] for x in tokens).replace(' — ','—')
 if len(text)<=50:return [text]
 opts=[]
 for k in range(1,len(tokens)):
  a=' '.join(x['text'] for x in tokens[:k]).replace(' — ','—');b=' '.join(x['text'] for x in tokens[k:]).replace(' — ','—')
  if max(len(a),len(b))<=50 and min(len(a.split()),len(b.split()))>=2:
   score=abs(len(a)-len(b)) + (0 if re.search(r'[,;:.!?—]$',a) else 6)
   opts.append((score,[a,b]))
 return min(opts,key=lambda x:x[0])[1] if opts else None
def stamps(t,ass=False):
 unit=100 if ass else 1000;t=round(t*unit);h,t=divmod(t,3600*unit);m,t=divmod(t,60*unit);s,f=divmod(t,unit)
 return f'{h}:{m:02}:{s:02}.{f:02}' if ass else f'{h:02}:{m:02}:{s:02},{f:03}'
def write(cues,srt,ass):
 srt.write_text('\n\n'.join(f"{i}\n{stamps(c['start'])} --> {stamps(c['end'])}\n"+'\n'.join(c['lines']) for i,c in enumerate(cues,1))+'\n',encoding='utf-8')
 ass.write_text(HEADER+''.join('Dialogue: 0,'+stamps(c['start'],True)+','+stamps(c['end'],True)+',Default,,0,0,0,,'+'\\N'.join(c['lines'])+'\n' for c in cues),encoding='utf-8')
allc=[];reports=[];offset=0
for seg in json.loads((OUT/'narration.json').read_text()):
 n=seg['segment'];duration=seg['video_duration'];raw=seg['text'].replace('—',' — ').split();asr=json.loads((OUT/f'raw/seg{n:02}_asr.json').read_text());sil=json.loads((OUT/f'raw/seg{n:02}_silences.json').read_text())['silences'];onset=sil[0][1];speech_end=sil[-1][0]
 aw=[w for s in asr['segments'] for w in s['words']];rn=[norm(w) for w in raw];an=[norm(w['word']) for w in aw]
 timing=[None]*len(raw);opcodes=difflib.SequenceMatcher(None,rn,an,autojunk=False).get_opcodes();mismatch=[]
 for tag,a,b,c,d in opcodes:
  if tag=='equal':
   for i,j in zip(range(a,b),range(c,d)):timing[i]=[aw[j]['start'],aw[j]['end']]
  elif b>a:
   mismatch.append({'reference':' '.join(raw[a:b]),'recognized':' '.join(w['word'] for w in aw[c:d])})
   lo=aw[c]['start'] if c<d else (aw[c-1]['end'] if c else onset)
   hi=aw[d-1]['end'] if c<d else (aw[c]['start'] if c<len(aw) else speech_end)
   total=sum(weight(w) for w in raw[a:b]);pos=lo
   for i in range(a,b):
    end=pos+(hi-lo)*weight(raw[i])/total;timing[i]=[pos,end];pos=end
 # Monotonic boundaries; first/last bounds come from actual waveform, not an assumed delay.
 last=onset
 for i,t in enumerate(timing):
  t[0]=max(last,min(speech_end,t[0]));t[1]=max(t[0],min(speech_end,t[1]));last=t[1]
 timing[0][0]=onset;timing[-1][1]=speech_end
 tokens=[];i=0
 while i<len(raw):
  match=None
  for spoken,display in PAIRS:
   p=spoken.split()
   if rn[i:i+len(p)]==[norm(x) for x in p]:match=(p,display);break
  count=len(match[0]) if match else 1
  if match:
   suffix=re.search(r'([.,!?;:]+)$',raw[i+count-1]);text=match[1]+(suffix[1] if suffix else '')
  else:text=raw[i]
  tokens.append({'text':text,'start':timing[i][0],'end':timing[i+count-1][1],'spoken_weight':sum(weight(w) for w in raw[i:i+count])});i+=count
 # Optimize natural clause boundaries globally, avoiding short final/orphan cues.
 N=len(tokens);dp=[math.inf]*(N+1);dp[N]=0;choice={}
 for a in range(N-1,-1,-1):
  for b in range(a+2,min(N,a+22)+1):
   lines=wrap(tokens[a:b])
   if lines is None:continue
   lo=tokens[a]['start'];hi=tokens[b-1]['end'];dt=hi-lo
   if dt>5.5:break
   if dt<.85:continue
   lastword=tokens[b-1]['text'];gap=(tokens[b]['start']-hi) if b<N else .5
   endpunct=bool(re.search(r'[.!?]$',lastword));clause=bool(re.search(r'[,;:—]$',lastword))
   score=3+(dt-3.2)**2*.35+(0 if endpunct else 1 if clause else 2.5)-min(.65,gap)*2
   if b<N and tokens[b]['text'].lower() in ['and','but','which','while','until','instead,','because','so']:score-=.8
   if lastword.lower().strip('.,') in ['a','an','the','to','of','by','in','for','and','or','with','from','our','its']:score+=7
   if len(lines)==2 and min(map(len,lines))<22:score+=2
   if dt<1:score+=10
   if score+dp[b]<dp[a]:dp[a]=score+dp[b];choice[a]=(b,lines)
 assert 0 in choice,(n,'No cue partition')
 cues=[];a=0
 while a<N:
  b,lines=choice[a];lo=tokens[a]['start'];hi=tokens[b-1]['end'];nextlo=tokens[b]['start'] if b<N else speech_end
  hi=min(nextlo,hi+.12,duration-.15,lo+5.5)
  # Snap a boundary in/near a pause to its actual speech edge.
  for ss,se in sil[1:-1]:
   if ss-.12<=hi<=se+.08 and abs(hi-ss)<.35:hi=min(nextlo,ss+.06)
   if ss-.08<=lo<=se+.12 and abs(lo-se)<.35:lo=se
  hi=min(hi,lo+5.5)
  cues.append({'start':round(lo,3),'end':round(max(hi,lo+1),3),'lines':lines,'spoken_syllable_weight':sum(t['spoken_weight'] for t in tokens[a:b])});a=b
 for i,c in enumerate(cues):
  if i:c['start']=max(c['start'],cues[i-1]['end'])
  assert 1-1e-6<=c['end']-c['start']<=5.5+1e-6,(n,c)
  assert len(c['lines'])<=2 and all(len(x)<=50 for x in c['lines'])
 assert cues[0]['start']==round(onset,3) and cues[-1]['end']<=duration-.15
 write(cues,SUB/f'seg{n:02}.srt',SUB/f'seg{n:02}.ass')
 (OUT/f'raw/seg{n:02}_subtitle_alignment.json').write_text(json.dumps({'method':'Local Whisper base word timestamps, reference-word sequence alignment, spoken-syllable-weighted replacement intervals, and actual FFmpeg silence edges','speech_onset':onset,'speech_end':speech_end,'reference_asr_differences':mismatch,'cues':cues},indent=2))
 reports.append({'segment':n,'cue_count':len(cues),'speech_onset':onset,'speech_end':speech_end,'minimum_cue_seconds':min(c['end']-c['start'] for c in cues),'maximum_cue_seconds':max(c['end']-c['start'] for c in cues),'timeline_offset':offset})
 allc.extend(dict(c,start=c['start']+offset,end=c['end']+offset) for c in cues);offset+=duration
 print(n,len(cues),'cues',f'{onset:.3f}–{speech_end:.3f}s',flush=True)
write(allc,OUT/'IncidentLens_Presentation_10min.srt',OUT/'IncidentLens_Presentation_10min.ass')
(OUT/'subtitle_metadata.json').write_text(json.dumps({'language':'en','burned_in':True,'soft_subtitle_track':False,'font':'Helvetica Neue','font_file':'/System/Library/Fonts/HelveticaNeue.ttc','font_size':36,'cue_count':len(allc),'total_timeline_seconds':offset,'segments':reports,'style':{'primary':'&H00F8FAFC','border_style':3,'back':'&H380B1220','outline':11,'shadow':0,'alignment':2,'margin_l':150,'margin_r':150,'margin_v':38}},indent=2))
