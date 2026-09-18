"""Generate the English notes' figures and literal prompt examples from saved runs."""
import json, math
from pathlib import Path
from statistics import mean
from reportlab.graphics.shapes import Drawing,Rect,Line,Circle,String,Polygon
from reportlab.graphics import renderPDF
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Proposal/notes'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'figures').mkdir(exist_ok=True)
(OUT/'prompts').mkdir(exist_ok=True)
BLUE=colors.HexColor('#32647a'); ORANGE=colors.HexColor('#ad603f')
INK=colors.HexColor('#263540'); LINE=colors.HexColor('#cad4da')
PALE=colors.HexColor('#f0f4f6'); WARM=colors.HexColor('#faf3eb')
def txt(d,x,y,s,size=10,anchor='middle',color=INK):
 d.add(String(x,y,s,fontName='Helvetica',fontSize=size,textAnchor=anchor,fillColor=color))
def box(d,x,y,w,h,lines,warm=False):
 d.add(Rect(x,y,w,h,rx=3,fillColor=WARM if warm else PALE,strokeColor=LINE,strokeWidth=.7))
 for j,s in enumerate(lines):txt(d,x+w/2,y+h/2+(len(lines)-1)*7-j*14-3,s)
def arrow(d,x1,y1,x2,y2):
 d.add(Line(x1,y1,x2,y2,strokeColor=BLUE,strokeWidth=.9))
 a=math.atan2(y2-y1,x2-x1)
 pts=[x2,y2]
 for da in [-.45,.45]:pts.extend([x2-6*math.cos(a+da),y2-6*math.sin(a+da)])
 d.add(Polygon(pts,fillColor=BLUE,strokeColor=None))
def save(d,name):renderPDF.drawToFile(d,str(OUT/'figures'/name))

d=Drawing(500,228)
box(d,137,177,226,42,['One market; one hidden demand state','Known to the generator, not to the agents'])
sig=['L L H','L H H','L H L','L H L','H L L','L L L']
ans=['A / 40%','B / 60%','A / 40%','A / 40%','A / 40%','A / 22.86%']
for j in range(6):
 x=3+j*83
 arrow(d,250,177,x+39,141)
 box(d,x,87,78,54,[f'Agent {j}',sig[j],'Private surveys'])
 arrow(d,x+39,87,x+39,64)
 box(d,x,28,78,36,[ans[j]],True)
txt(d,250,7,'Bottom row: initial choice / reported probability of HIGH demand.',10)
save(d,'task.pdf')

d=Drawing(500,219)
box(d,133,173,234,40,['Save one initial six-agent state','Reuse it in every branch'])
for x,name in [(6,'Full evidence'),(263,'Advice only')]:
 arrow(d,250,173,x+116,137)
 box(d,x,104,230,33,[name])
 for xx,label in [(x,'A-high'),(x+125,'B-high')]:
  arrow(d,x+115,104,xx+52,75)
  box(d,xx,34,105,41,[label,'Two calls'],True)
txt(d,250,12,'Each receiver is tested in every branch; outputs are not passed between branches.',9)
save(d,'design.pdf')

run=ROOT/'runs/signal-visibility-replication-20260920'
updates=json.loads((run/'updates.json').read_text(encoding='utf-8'))
get=lambda v,a:mean(r['parsed']['p_B'] for r in updates if r['item_id']=='demand-00' and r['member']==3 and r['visibility']==v and r['arm']==a)
d=Drawing(500,218)
for y in [0,5,10,15,20]:
 yy=37+y*7;d.add(Line(45,yy,490,yy,strokeColor=LINE,strokeWidth=.4));txt(d,37,yy-3,str(y),9,'end')
txt(d,45,202,'Reported probability of HIGH demand (%)',10,'start')
for j,v in enumerate(['full','advice']):
 center=160+j*225
 for k,a in enumerate(['A_high','B_high']):
  val=100*get(v,a);x=center-55+k*60;cc=BLUE if k==0 else ORANGE
  d.add(Rect(x,37,42,val*7,fillColor=cc,strokeColor=None));txt(d,x+21,42+val*7,f'{val:.2f}',9)
  txt(d,x+21,23,'A-high' if k==0 else 'B-high',9)
 txt(d,center,7,'Full evidence' if j==0 else 'Advice only',10)
save(d,'case.pdf')

d=Drawing(500,192)
X=lambda v:150+(v+2)/34*335
for tick in [0,10,20,30]:
 x=X(tick);d.add(Line(x,37,x,178,strokeColor=LINE,strokeWidth=.5));txt(d,x,23,str(tick),9)
allstats=[]
for runname,batch in [('signal-visibility-luna-20260919','Discovery'),('signal-visibility-replication-20260920','Replication')]:
 s=json.loads((ROOT/'runs'/runname/'summary.json').read_text(encoding='utf-8'))
 for v in ['full','advice']:allstats.append((batch,v,s['primary'][v]))
allstats.sort(key=lambda z:(z[1]!='full',z[0]!='Discovery'))
for i,(batch,v,z) in enumerate(allstats):
 y=163-i*37;cc=BLUE if batch=='Discovery' else ORANGE
 txt(d,138,y-3,batch+' / '+('full' if v=='full' else 'advice'),10,'end')
 lo,hi=[100*x for x in z['descriptive_item_bootstrap_95pct']];mu=z['mean_p_B_shift']*100
 d.add(Line(X(lo),y,X(hi),y,strokeColor=cc,strokeWidth=1.5));d.add(Circle(X(mu),y,3,fillColor=cc,strokeColor=None))
txt(d,325,5,'Change in reported P(HIGH): B-high minus A-high (pp)',9)
save(d,'results.pdf')

d=Drawing(500,185)
box(d,5,121,145,55,['Training items','Observe one-step updates','Fit a response predictor'])
arrow(d,150,149,178,149)
box(d,178,121,145,55,['Validation items','Choose settings','Then freeze the predictor'])
arrow(d,323,149,350,149)
box(d,350,121,145,55,['New test items','Save group forecasts','Before observing updates'])
arrow(d,423,121,423,83)
box(d,303,24,192,59,['Run actual group updates','Compare with saved forecasts','and confidence-blind baselines'],True)
txt(d,142,62,'Planned, not completed on demand tasks.',10)
save(d,'prediction.pdf')

calls={}
for f in sorted((run/'items/demand-00/calls').glob('*.json')):
 r=json.loads(f.read_text(encoding='utf-8'));ms=r.get('request',{}).get('messages',[])
 if len(ms)!=2:continue
 u=json.loads(ms[1]['content'])
 if u.get('your_member_id')!='member-3':continue
 peers=u.get('peer_reports',[])
 if not peers:key='initial'
 else:
  cs={x['member_id']:x.get('confidence') for x in peers}
  if cs.get('member-4')==.771429 and cs.get('member-1')==.6:arm='A_high'
  elif cs.get('member-4')==.6 and cs.get('member-1')==.771429:arm='B_high'
  else:continue
  key=('full' if 'surveys' in peers[0] else 'advice')+'_'+arm
 calls.setdefault(key,{'source':str(f.relative_to(ROOT)).replace('\\','/'),'request':r['request'],'response':r['parsed']})
assert len(calls)==5
(OUT/'prompt_examples.json').write_text(json.dumps(calls,indent=2),encoding='utf-8')
for key,r in calls.items():
 (OUT/'prompts'/f'{key}_user.json').write_text(r['request']['messages'][1]['content'],encoding='utf-8')
 (OUT/'prompts'/f'{key}_response.json').write_text(json.dumps(r['response'],indent=2),encoding='utf-8')
(OUT/'prompts/system.txt').write_text(calls['initial']['request']['messages'][0]['content'],encoding='utf-8')
# Compact JSON for typesetting, preserving all keys, values and array order.
def compact_user(u):
 lines=['{']
 for k,v in u.items():
  if isinstance(v,list):
   lines.append('  '+json.dumps(k)+': [')
   for q in v:lines.append('    '+json.dumps(q)+',')
   lines[-1]=lines[-1].rstrip(',');lines.append('  ],')
  elif isinstance(v,dict):
   lines.append('  '+json.dumps(k)+': {')
   for kk,vv in v.items():lines.append('    '+json.dumps(kk)+': '+json.dumps(vv)+',')
   lines[-1]=lines[-1].rstrip(',');lines.append('  },')
  else:lines.append('  '+json.dumps(k)+': '+json.dumps(v)+',')
 lines[-1]=lines[-1].rstrip(',');lines.append('}')
 out='\n'.join(lines);assert json.loads(out)==u
 return out
for key in ['initial','advice_A_high']:
 (OUT/'prompts'/f'{key}_formatted.json').write_text(compact_user(json.loads(calls[key]['request']['messages'][1]['content'])),encoding='utf-8')
full=json.loads(calls['full_A_high']['request']['messages'][1]['content'])
(OUT/'prompts/full_peer_example.json').write_text(json.dumps(next(x for x in full['peer_reports'] if x['member_id']=='member-4'),indent=2),encoding='utf-8')
config={k:v for k,v in calls['initial']['request'].items() if k!='messages'}
(OUT/'prompts/request_configuration.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
for vis in ['advice','full']:
 a=json.loads(calls[vis+'_A_high']['request']['messages'][1]['content']);b=json.loads(calls[vis+'_B_high']['request']['messages'][1]['content'])
 for peer in a['peer_reports']:
  if peer['member_id']=='member-4':peer['confidence']=.6
  if peer['member_id']=='member-1':peer['confidence']=.771429
 assert a==b
for arm in ['A_high','B_high']:
 full=json.loads(calls['full_'+arm]['request']['messages'][1]['content'])
 advice=json.loads(calls['advice_'+arm]['request']['messages'][1]['content'])
 for peer in full['peer_reports']:peer.pop('surveys')
 assert full==advice
print(json.dumps({'figures':5,'actual_prompt_examples':len(calls),'paired_prompt_check':'passed','directory':str(OUT)}))
