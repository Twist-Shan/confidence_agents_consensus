"""Self-contained HTML research report. Offline; reads saved evidence only."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/html'
OUT.mkdir(parents=True, exist_ok=True)
E = json.loads((ROOT/'output/pdf/report_evidence.json').read_text(encoding='utf-8'))
MD = (ROOT/'output/pdf/confidence_agents_experiment_report_zh.md').read_text(encoding='utf-8')
H = html.escape
BLUE,ORANGE,INK,GRID = '#246b8e','#b65c38','#253544','#dbe3e9'

def read(name):
    return json.loads((ROOT/'runs'/name/'summary.json').read_text(encoding='utf-8'))
old = read('signal-visibility-luna-20260919')
new = read('signal-visibility-replication-20260920')
gap_old = read('confidence-gap-luna-20260918')
gap_new = read('confidence-gap-replication-luna-20260923')

def txt(x,y,text,size=13,anchor='start',fill=INK):
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}">{H(str(text))}</text>'
def line(x1,y1,x2,y2,color=GRID,width=1,dash=''):
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>'
def svg_wrap(content,w,h,title):
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{H(title)}" xmlns="http://www.w3.org/2000/svg">'+''.join(content)+'</svg>'
def forest(rows,xmin,xmax,ticks,label):
    w,h,l,r,t,b=760,280,180,725,25,224
    X=lambda v:l+(v-xmin)/(xmax-xmin)*(r-l)
    parts=[]
    for v in ticks:
        parts.extend([line(X(v),t,X(v),b),txt(X(v),b+24,v,12,'middle')])
    if xmin<=0<=xmax:parts.append(line(X(0),t,X(0),b,'#82919d',1,'4 4'))
    step=(b-t)/len(rows)
    for i,(name,v,lo,hi,color) in enumerate(rows):
        y=t+(i+.5)*step
        parts.extend([txt(l-14,y+4,name,13,'end'),line(X(lo),y,X(hi),y,color,2.5),line(X(lo),y-5,X(lo),y+5,color,2),line(X(hi),y-5,X(hi),y+5,color,2),f'<circle cx="{X(v)}" cy="{y}" r="5" fill="{color}"/>'])
    parts.extend([line(l,b,r,b,'#8c9ca7'),txt((l+r)/2,h-8,label,13,'middle')])
    return svg_wrap(parts,w,h,label)
def bars(labels,series,ylabel):
    w,h,l,r,t,b=760,300,55,735,48,242
    parts=[txt(l,22,ylabel,13)]
    for v in range(0,101,25):
        y=b-v/100*(b-t);parts.extend([line(l,y,r,y),txt(l-10,y+4,v,12,'end')])
    group=(r-l)/len(labels);bw=min(47,group*.68/len(series))
    for k,(label,values,color) in enumerate(series):
        lx=485+k*126;parts.extend([f'<rect x="{lx}" y="12" width="11" height="11" fill="{color}"/>',txt(lx+17,22,label,12)])
        for i,v in enumerate(values):
            x=l+(i+.5)*group+(k-len(series)/2)*bw;y=b-v/100*(b-t)
            parts.extend([f'<rect x="{x}" y="{y}" width="{bw-3}" height="{b-y}" fill="{color}" rx="2"/>',txt(x+(bw-3)/2,y-8,f'{v:.1f}',12,'middle')])
    for i,label in enumerate(labels):parts.append(txt(l+(i+.5)*group,b+28,label,13,'middle'))
    return svg_wrap(parts,w,h,ylabel)

figs={1:bars(['自然生成的 20 题','平衡后的 40 题'], [('蕴含',[100*13/18,100*72/112],BLUE),('不蕴含',[100*101/102,100*114/118],ORANGE)],'答对的比例（%，只计有效回答）')}
rows=[]
for s,label,col in [(gap_old,'旧题：探索',BLUE),(gap_new,'新题：复核',ORANGE)]:
    lo,hi=s['descriptive_stratified_item_bootstrap_95pct'];rows.append((label,10*s['primary_slope'],10*lo,10*hi,col))
figs[2]=forest(rows,-9,5,[-8,-4,0,4],'分差增加 0.10 时，错误率差的变化（百分点）')
rows=[]
for key,label in [('full','完整证据'),('advice','只看建议'),('interaction','两种条件的差别')]:
    p=old['primary'][key];lo,hi=p['descriptive_item_bootstrap_95pct'];rows.append((label,100*p['mean_p_B_shift'],100*lo,100*hi,BLUE))
figs[3]=forest(rows,-3,24,[0,5,10,15,20],'把高分移给 B 方后，P(B) 改变多少（百分点）')
rows=[]
for s,prefix,col in [(old,'发现',BLUE),(new,'复核',ORANGE)]:
    for key,label in [('advice','只看建议'),('interaction','两种条件的差别')]:
        p=s['primary'][key];lo,hi=p['descriptive_item_bootstrap_95pct'];rows.append((f'{prefix}：{label}',100*p['mean_p_B_shift'],100*lo,100*hi,col))
# Keep the ordering in the source caption: discovery/replication within each measure.
rows=[rows[0],rows[2],rows[1],rows[3]]
figs[4]=forest(rows,0,32,[0,10,20,30],'概率变化或变化之差（百分点）')
c=E['case_values']
figs[5]=bars(['发现 / 完整证据','发现 / 只看建议','复核 / 完整证据','复核 / 只看建议'],[
 ('A 方拿高分',[100*c[k][f'{v}/A_high'] for k in ('E11','E12') for v in ('full','advice')],BLUE),
 ('B 方拿高分',[100*c[k][f'{v}/B_high'] for k in ('E11','E12') for v in ('full','advice')],ORANGE)],'模型报告的 P(B)（%）')
parts=[];l,r,t,b=55,735,45,255
X=lambda q:l+q/15*(r-l)
Y=lambda v:b-(v+10)/65*(b-t)
for v in range(-10,51,10):parts.extend([line(l,Y(v),r,Y(v),'#83929e' if v==0 else GRID),txt(l-9,Y(v)+4,v,12,'end')])
for s,col,offset in [(old,BLUE,-3),(new,ORANGE,3)]:
    for row in s['item_effects']:
        q=int(row['item_id'].split('-')[-1]);val=100*row['advice']['p_B_shift'];parts.append(f'<circle cx="{X(q)+offset}" cy="{Y(val)}" r="4.5" fill="{col}"><title>{H(row["item_id"])}：{val:.4f} 个百分点</title></circle>')
for q in range(16):parts.append(txt(X(q),b+21,f'{q:02d}',12,'middle'))
parts.extend([txt(l,22,'只看建议时，每题 P(B) 的变化（百分点）',13),txt(r,22,'蓝：发现；橙：复核',12,'end'),txt(395,307,'题目编号（两批同号代表不同题）',13,'middle')])
figs[6]=svg_wrap(parts,760,325,'两批实验各道题的概率变化')

PURPOSE = {
 '05': [('E01','检查实验程序能不能正常运行。','两道题，六个模型分别作答，再互相看答案；另外测试固定同伴答案的情况。','只做小规模检查。模型先前的答案、处理条件、每次调用和结果都保存下来。')],
 '06': [('E02','找一些不会几乎全对、也不会几乎全错的题。','让模型独立回答状态追踪、贝叶斯计算和逻辑判断题。','每类四个复杂度等级，每级两题，每题六次；事先规定挑选标准，不根据分数干预结果挑题。')],
 '07': [('E03','检查上一轮选出的 L1、L2，在新题上是否仍会出现分歧。','用四道之前没跑过的题，每题独立回答六次。','模型、提示和挑选标准不变，只换题。'),('E04','用更多题判断 L2 的难度是否稳定。','再取二十道 L2 题，每题回答六次。','全部保留，不只取模型容易答错的题；分别看“蕴含”和“不蕴含”。')],
 '08': [('E05','排除“某一类题特别多”对总体正确率的影响。','构建四十道题，让“蕴含”和“不蕴含”各占一半。','每类正确选项 A/B 也各半；用精确求解器挑题，不看模型答得好不好。')],
 '09': [('E06','检查怎样减少没有完整答案、或者格式不合法的输出。','重新跑以前出现输出失败的八道题。','统一增加输出上限、固定推理设置、限制 JSON 格式；这是三项一起改变的测试。')],
 '10': [('E07','只把高分改给错误答案，模型会不会更容易答错？','每题给一个接收者看四份同伴报告：两对、两错。','自己和同伴的答案都预先设定。题目、票数和顺序不变，只换显示分数；四条件各重复三次。')],
 '11': [('E08','高分和低分相差越大，答案受影响是否越明显？','比较 .80/.70、.90/.60、.95/.55 三种分差。','每种分差都对调高分归属，加上等分和隐藏分数，共八条件；每条件三次。')],
 '12': [('E09','旧题出现的反向趋势，在新题上能不能重复出现？','用四十道新逻辑题再跑相同的八条件实验。','题目以外的主要设置保持不变；新旧结果分开报告，不靠合并来判断是否复现。')],
 '14': [('E10','让初答由模型真实产生，再检查局部变化能否预测六人一起讨论的结果。','六人各看到一部分供应商数据；更新时全部数据公开。','八道题用于学习下一步选择的规律，另外八道用于检验群体预测；正确/错误同伴之间交换高分。')],
 '17': [('E11 / E12','看得到原始证据时，和只能看建议时，模型对分数的反应是否不同？','六人各看到三条调查，先独立判断市场需求，再看其他人的答案。','同一组初答建立两种信息条件；两人之间交换 .60/.771429，测另外两人的更新。')],
 '19': [('E11','先检查“是否看得到证据”这个区别能否测到。','在十六个市场实例上，比较两种信息条件下的概率变化。','每题两名接收者、四种分数组合、两次重复；先在题内平均，再比较题与题。')],
 '20': [('E12','固定刚才的做法，换新实例检查结论。','重新生成十六个市场，重新取得六人的初答。','只换任务生成种子；出现分歧的十五题继续做干预，一致的那题不补抽。')],
}

TITLES = {
 '01':'做过哪些实验', '02':'我们到底在改变什么', '03':'错误率和分差怎样计算',
 '04':'概率变化、区间和缺失怎样计算', '05':'E01 · 先把实验流程跑通',
 '06':'E02 · 找到能产生分歧的题', '07':'E03-E04 · 换新题，再扩大样本',
 '08':'E05 · 让两类逻辑题各占一半', '09':'E06 · 解决截断和格式问题',
 '10':'E07 · 把高分改给错误答案', '11':'E08 · 再试不同大小的分差',
 '12':'E09 · 用新题检查反向趋势', '13':'题目差异和回答波动：事后检查',
 '14':'E10 · 六人选择供应商：怎么做', '15':'E10 · 供应商实验得到了什么',
 '16':'E10 · 怎样预测六人下一轮的选择', '17':'E11-E12 · 市场需求任务：怎么做',
 '18':'调查信号怎样变成概率', '19':'E11 · 第一批市场实例的结果',
 '20':'E12 · 新实例复核的结果', '21':'两个真实例子：数字到底怎么变',
 '22':'每道题都受影响了吗', '23':'概率变了，预测就更好了吗',
 '24':'一个事后提出的解释，能说明多少', '25':'现在能下哪些结论',
 '附录 A':'附录 A · 真实逻辑题的完整题面', '附录 B':'附录 B · 模型、提示和失败处理',
 '附录 C':'附录 C · 调用量、费用和缓存', '附录 D':'附录 D · 原始文件在哪里',
 '附录 E':'附录 E · 模拟、失败启动和未做的实验',
}

def plain(text):
    replacements={
      '本段结论：':'目前结论：','主效应不可估':'没有可比较的分歧状态',
      '无混合初始状态':'初答全部一致','独立题群体':'新题群体',
      '冻结题面':'固定题面','冻结同题':'保留同题','冻结 manifest':'保存并固定实验清单',
      '运行前冻结':'运行前固定','冻结的':'事先固定的','冻结细节':'固定设置',
      '显示 confidence':'显示的置信度分数','可见性效应':'是否看得到原始证据的影响',
      '只测局部更新':'只测一次回答更新','局部更新':'一次回答更新',
      '有辨识力的非零':'能清楚测出的非零','可辨识性问题':'能否作出有效比较的问题',
      '行为结论':'关于模型回答的结论','规范概率基准':'用于比较的理论概率',
      '事后劣选':'知道全部信息后更差的选择','误差条':'误差线',
      '全体 rollout':'全体多轮讨论','完整群体 rollout':'完整的群体多轮讨论',
      '群体 rollout':'群体多轮讨论','高自报概率错误':'高把握的错误回答',
      '高自报概率':'很高的报告概率','自报概率':'报告的概率',
      '实际重要效应':'有实际意义的影响','无偏估计':'不受挑题影响地估计',
      '显式区分':'明确区分','未识别':'还没区分清楚','识别唯一内部机制':'确定唯一的内部计算方式',
      '异质性':'题目之间的差异','干预测两个接收者':'干预测两个接收者',
      '四个接收者×重复配对':'四个“接收者×重复”配对',
      '不增加独立实验':'不构成新一轮实验','同期':'同一时期',
      'python -s scripts/build_experiment_report.py':'python -s scripts/build_experiment_report_html.py',
      '产物包括本 PDF、可编辑正文 Markdown、抽取指标与来源 SHA-256 清单。':'HTML 把正文和图表放在同一文件内；抽取指标和来源文件的校验值保存在 report_evidence.json。',
    }
    for a,b in replacements.items():text=text.replace(a,b)
    return text

def paragraph(text):
    text=plain(text)
    if text.startswith('来源：') or text.startswith('编制依据：'):
        return '<p class="source">'+H(text)+'</p>'
    if text.startswith('图示结果：'):
        text=text.replace('图示结果：','图里能看到：',1)
    bits=text.split('\n目前结论：',1)
    result='<p>'+H(bits[0]).replace('\n','<br>')+'</p>'
    if len(bits)>1:result+='<p class="takeaway"><strong>目前结论</strong>'+H(bits[1])+'</p>'
    return result

def render_table(rows):
    parsed=[[v.strip() for v in row.strip().strip('|').split('|')] for row in rows]
    head=parsed[0]; body=parsed[1:]
    return '<div class="table-scroll" tabindex="0" aria-label="可横向滚动的数据表"><table><thead><tr>'+''.join('<th scope="col">'+H(plain(v))+'</th>' for v in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+H(plain(v))+'</td>' for v in row)+'</tr>' for row in body)+'</tbody></table></div>'

def render_body(text):
    blocks=re.split(r'\n\s*\n',text.strip());result=[];rows=[]
    for block in blocks+['']:
        if block.startswith('|'):
            # The source places each row in its own block; some cells contain newlines.
            rows.append(block.replace('\n',' '));continue
        if rows:result.append(render_table(rows));rows=[]
        if not block:continue
        if block.startswith('### '):result.append('<h3>'+H(plain(block[4:]))+'</h3>')
        elif re.match(r'图 [1-6]｜',block):
            n=int(block[2]);result.append(f'<figure id="figure-{n}">'+figs[n]+'<figcaption>'+H(plain(block))+'</figcaption></figure>')
        else:result.append(paragraph(block))
    return '\n'.join(result)

sections=[];nav=[]
parts=re.split(r'^## ',MD,flags=re.M)[1:]
for block in parts:
    header,_,body=block.partition('\n')
    if header.startswith('Confidence'):continue
    key=header.split('｜')[0];title=TITLES.get(key,header)
    sid='s'+key if key.isdigit() else 'appendix-'+key[-1].lower()
    overview=''
    for eid,purpose,content,design in PURPOSE.get(key,[]):
        overview+=f'<div class="experiment-brief"><div class="experiment-tag">{H(eid)}</div><dl><div><dt>实验目的</dt><dd>{H(purpose)}</dd></div><div><dt>实验内容</dt><dd>{H(content)}</dd></div><div><dt>怎么比较</dt><dd>{H(design)}</dd></div></dl></div>'
    extra=''
    if key=='06':
        extra='<details class="method"><summary>展开：四个等级具体差在哪里</summary>'+render_table([
          '|题型|L1|L2|L3|L4|',
          '|状态追踪：模数 / 更新步数|11 / 8|37 / 16|97 / 24|251 / 40|',
          '|贝叶斯：假设数 / 观测次数|2 / 4|3 / 8|4 / 16|5 / 32|',
          '|贝叶斯：比较阈值的小数精度|1 位|2 位|3 位|4 位|',
          '|逻辑：变量数 / 子句数|5 / 20|7 / 28|9 / 36|11 / 44|'])+paragraph('状态题每步按给出的整数运算更新；贝叶斯题用精确分数算后验，再与阈值比较；逻辑题检查所有满足前提的赋值。逻辑生成器先选一个满足解，只保留与该解相容的三文字子句，以保证前提能同时成立。\n目前结论：等级控制生成规模，并不保证模型错误率依次增加。')+'</details>'
    if key=='05':
        extra='<details class="method"><summary>展开：小测中的分数如何设置</summary>'+paragraph('六人讨论的分数集合为两个 .95、四个 .55。aligned 尽量让初答正确者获得高分，misaligned 尽量反向分配，hidden 隐藏分数；按初答正确性分配后，分数固定跟随成员，不因后续答对答错而重分。局部小测包含三种高低分组合（.55/.75、.55/.95、.75/.95）各两种分配方向，加上三个等分条件和一个隐藏条件，共十种。\n目前结论：早期小测只用于检查程序；两题初答全对，缺少真正的正确/错误归属对照。')+'</details>'
    if key=='14':
        extra='<details class="method"><summary>展开：供应商题目怎样抽样</summary>'+paragraph('seed=20260918。训练与测试各八题，按完整信息下 A/B 哪个更好，以及总分差 1-4 / 5-10 分成四类，每类两题。调用前按数字条件保留私人材料会支持不同选项的题；不根据模型干预结果挑题。题面声明未见项的 A-B 差独立服从 -12 至 12 的离散均匀分布，期望为零。筛选后的题库并不是这个先验的无条件随机样本。\n目前结论：这个先验用于解释初始决策，不用于声称题库已满足概率校准。')+'</details>'
    contents=overview+render_body(body)+extra
    if key in ('03','04','16','18','24') or key.startswith('附录'):
        intro={
         '03':'正文中的“错误率差”和“分差斜率”各指什么，这里给出公式与小例子。',
         '04':'概率移动不等于答对率提升；区间也不等于把缺失补齐后的范围。',
         '16':'用训练题学到的下一步选择规律，先预测新题结果，再真正调用模型检查。加入分数特征没有比不加入时预测得更好。',
         '18':'三条调查中两条支持高需求时，理论概率是 60%；三条都支持时是约 77.14%。',
         '24':'把分数当成同伴证据强度，可以解释部分输出。但这个解释是在看过部分结果后提出的，不能当作已经验证的机制。',
        }.get(key,'这里保留具体文件、设置或核验材料，需要时可以展开查看。')
        contents='<p class="section-intro">'+H(intro)+'</p><details class="method"><summary>展开计算方法与详细记录</summary>'+contents+'</details>'
    sections.append(f'<section id="{sid}" class="report-section"><div class="section-kicker">'+('实验与分析' if key.isdigit() else '补充材料')+f'</div><h2>{H(title)}</h2>{contents}</section>')
    nav.append((sid,title,key))

css='''
:root{--ink:#253544;--muted:#657482;--blue:#246b8e;--orange:#b65c38;--line:#dbe3e9;--paper:#fff;--wash:#f2f5f7;--sidebar:254px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:var(--wash);color:var(--ink);font:16px/1.9 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}a{color:var(--blue)}button,input{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible{outline:3px solid #79a8be;outline-offset:3px}.skip{position:fixed;top:-60px;left:15px;z-index:10;background:white;padding:8px}.skip:focus{top:10px}
aside{position:fixed;inset:0 auto 0 0;width:var(--sidebar);background:#f8fafb;border-right:1px solid var(--line);padding:28px 18px;overflow:auto;z-index:3}.brand{font-size:12px;letter-spacing:1.2px;font-weight:750;color:var(--blue)}aside h2{font-size:17px;margin:5px 0 19px}nav a{display:block;text-decoration:none;color:var(--muted);font-size:12px;line-height:1.65;padding:6px 8px;border-left:2px solid transparent;margin:2px 0}nav a:hover,nav a.active{background:#e9f0f4;color:var(--blue);border-left-color:var(--blue)}.nav-group{font-size:11px;letter-spacing:1px;color:#8a97a1;margin:20px 8px 7px;font-weight:700}.search{width:100%;padding:8px 10px;font-size:13px;border:1px solid var(--line);border-radius:5px;background:white}.search-status{font-size:11px;color:var(--muted);min-height:20px;margin:4px 0}.aside-note{font-size:11px;color:var(--muted);margin-top:25px}
main{margin-left:var(--sidebar);padding:34px clamp(20px,4.5vw,78px) 80px;max-width:1450px}.hero,.report-section{max-width:990px;margin:0 auto 26px;padding:34px 42px;background:var(--paper);border:1px solid #e0e6eb;border-radius:8px}.hero{border-top:5px solid var(--blue);padding-top:28px}.eyebrow,.section-kicker{font-size:11px;letter-spacing:1.5px;color:var(--blue);font-weight:750}.hero h1{font-size:35px;line-height:1.4;margin:13px 0 12px;font-weight:740;letter-spacing:-.8px}.hero .lead{font-size:17px;color:var(--muted);max-width:720px}.hero .claim{font-size:18px;line-height:1.85;border-left:3px solid var(--blue);padding:0 0 0 18px;margin:24px 0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:25px 0}.stat{padding:16px;background:var(--wash);border-radius:5px}.stat strong{display:block;font-size:25px;color:var(--blue);line-height:1.3}.stat span{font-size:12px;color:var(--muted)}.toolbar{display:flex;gap:8px;flex-wrap:wrap}.toolbar button{background:white;color:var(--blue);border:1px solid var(--line);padding:6px 12px;border-radius:4px;font-size:12px}.toolbar button:hover{background:var(--wash)}h2{font-size:25px;line-height:1.5;margin:6px 0 23px}h3{font-size:17px;margin:28px 0 10px;color:var(--blue)}p{margin:12px 0 17px}.section-intro{color:var(--muted)}.source{font-size:11px;color:#7b8993;overflow-wrap:anywhere}.takeaway{font-size:14px;line-height:1.9;margin:10px 0 23px;padding:12px 15px;background:#f0f5f6;border-left:3px solid #6e99a6;border-radius:0 4px 4px 0}.takeaway strong{display:block;font-size:11px;letter-spacing:1px;color:var(--blue);margin-bottom:2px}.experiment-brief{border:1px solid #cddde5;background:#f8fbfc;border-radius:5px;padding:18px 20px;margin:0 0 25px}.experiment-tag{font-size:11px;font-weight:800;color:var(--blue);margin-bottom:5px}dl{margin:0}dl div{display:grid;grid-template-columns:80px 1fr;gap:12px;margin:10px 0}dt{font-size:13px;color:var(--blue);font-weight:700}dd{margin:0;font-size:14px;line-height:1.85}.table-scroll{overflow:auto;margin:20px 0;max-width:100%;border:1px solid var(--line);border-radius:4px}table{border-collapse:collapse;width:100%;font-size:12.5px;line-height:1.75;min-width:540px}th,td{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#edf3f6;color:var(--ink);font-weight:650}tr:last-child td{border-bottom:0}tbody tr:hover{background:#fafcfd}figure{margin:25px 0;background:#fff;padding:12px 7px 0;border:1px solid var(--line);border-radius:5px}svg{display:block;width:100%;height:auto;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}figcaption{font-size:12px;line-height:1.85;color:var(--muted);padding:14px 15px 16px;border-top:1px solid #edf1f3;margin-top:8px}details{margin:20px 0;border:1px solid var(--line);border-radius:5px;padding:0 18px}summary{font-size:14px;color:var(--blue);font-weight:650;cursor:pointer;padding:14px 0}details[open]>summary{border-bottom:1px solid var(--line);margin-bottom:19px}.glossary{font-size:13px;color:var(--muted)}.footer{max-width:990px;margin:30px auto;text-align:center;font-size:12px;color:var(--muted)}[hidden]{display:none!important}.mobile-top{display:none}.filter-empty{padding:30px;background:white;text-align:center;border-radius:5px}
@media(min-width:1600px){:root{--sidebar:280px}body{font-size:17px}nav a{font-size:13px}}
@media(max-width:1000px){:root{--sidebar:216px}aside{padding:20px 12px}main{padding:22px 20px 60px}.hero,.report-section{padding:27px 26px}.hero h1{font-size:30px}h2{font-size:22px}}
@media(max-width:740px){aside{position:relative;width:auto;max-height:none;border-right:0;border-bottom:1px solid var(--line);padding:17px 20px}aside h2{margin:1px 0 12px}aside nav{display:none;max-height:330px;overflow:auto}aside.show-nav nav{display:block}.mobile-top{display:block;position:absolute;right:20px;top:21px;border:1px solid var(--line);background:white;color:var(--blue);padding:5px 10px;border-radius:4px;font-size:12px}.aside-note{display:none}.search{max-width:430px}main{margin-left:0;padding:18px 12px 40px}.hero,.report-section{padding:22px 18px;border-radius:5px}.hero h1{font-size:27px}.hero .claim{font-size:16px}.stats{gap:7px}.stat{padding:12px 8px}.stat strong{font-size:21px}.stat span{font-size:10px}h2{font-size:22px}dl div{grid-template-columns:1fr;gap:2px}.experiment-brief{padding:15px}.table-scroll{margin-left:-4px;margin-right:-4px}figure{padding:6px 0 0}figcaption{padding:10px;font-size:11px}svg{min-width:520px}figure{overflow-x:auto}body{font-size:15px}details{padding:0 12px}}
@media print{aside,.toolbar,.mobile-top,.skip,.search-status{display:none!important}body{background:white;font-size:10pt}main{margin:0;padding:0;max-width:none}.hero,.report-section{border:0;padding:10px 0;margin:0 0 20px;max-width:none;border-radius:0}h2,h3{break-after:avoid}table,figure,.experiment-brief,.takeaway{break-inside:avoid}.report-section{break-before:page}.table-scroll,figure{overflow:visible}svg{min-width:0}summary{display:none}details{border:0;padding:0}table{min-width:0}a{color:inherit;text-decoration:none}.stats{display:flex}.stat{flex:1}.footer{font-size:8pt}}
'''

navhtml='<a href="#overview">先看主要结论</a>'
groups={'01':'整体问题','05':'第一阶段 · 找题与检查输出','10':'第二阶段 · 逻辑题分数干预','14':'第三阶段 · 六人供应商决策','17':'第四阶段 · 证据可见性','25':'结论与原始记录'}
for sid,title,key in nav:
    if key in groups:navhtml+='<div class="nav-group">'+groups[key]+'</div>'
    navhtml+=f'<a href="#{sid}">{H(title)}</a>'

hero='''<header class="hero" id="overview"><div class="eyebrow">CONFIDENCE AGENTS · 实验记录</div>
<h1>置信度分数会怎样影响模型判断？</h1>
<p class="lead">把目前做过的实验放在一起：为什么做，模型看到什么，我们改变什么，以及结果到底能说明什么。</p>
<div class="claim"><strong>目前最清楚的结果：</strong>模型只能看到同伴建议时，给谁更高的分数会明显改变它报告的概率；能看到全部原始证据时，平均变化很小。这一方向已经在一批新实例上再次出现。</div>
<div class="stats"><div class="stat"><strong>12 批</strong><span>完成的真实模型运行</span></div><div class="stat"><strong>4,876</strong><span>请求记录 · 4,846 条有效</span></div><div class="stat"><strong>6 幅</strong><span>依据保存结果绘制的图表</span></div></div>
<p>也有不符合预期的结果。逻辑题中的“反向趋势”没有在新题上明确重复；供应商任务虽然跑了六人讨论，却没有证明置信度影响会继续传播。报告把这些结果一起保留。</p>
<p class="takeaway"><strong>阅读范围</strong>所有真实实验都使用同一个 Luna API 模型 ID。模拟测试、账户失败和事后分析另列；没有把它们当作新的行为证据。这次整理没有新增模型调用。</p>
<details class="glossary"><summary>先解释几个常用词</summary><p><strong>confidence / 置信度分数：</strong>告诉接收者“这位同伴觉得自己的答案有多大把握”的数字，实验中可能被人为替换。<br><strong>P(B)：</strong>模型给 B 选项的概率；在需求任务中，B 表示高需求。<br><strong>配对比较：</strong>对同一道题，保留相同意见，只改分数，然后比较结果。<br><strong>百分点：</strong>概率从 40% 变到 50%，增加的是 10 个百分点。<br><strong>复核：</strong>先固定做法，再换新题检验同一结论。<br><strong>交互：</strong>这里指“只看建议时的分数影响”减去“能看全部证据时的分数影响”。</p></details>
<div class="toolbar"><button id="expand" type="button">展开所有细节</button><button id="collapse" type="button">收起计算与附录</button><button id="print" type="button">打印报告</button></div>
<p class="source">单文件 HTML · 可离线打开 · 原始记录截止于新实例复核完成 · 目录名中的日期样式数字经常是随机种子，不代表实际运行日期。</p></header>'''

js='''
const sections=[...document.querySelectorAll('.report-section')];
const search=document.querySelector('#search');const status=document.querySelector('#search-status');
const navLinks=[...document.querySelectorAll('nav a')];
document.querySelector('#expand').addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=true));
document.querySelector('#collapse').addEventListener('click',()=>document.querySelectorAll('details').forEach(d=>d.open=false));
document.querySelector('#nav-toggle').addEventListener('click',()=>{const aside=document.querySelector('aside');const open=aside.classList.toggle('show-nav');document.querySelector('#nav-toggle').setAttribute('aria-expanded',String(open));});
let beforeSearch=null;
search.addEventListener('input',()=>{const q=search.value.trim().toLowerCase();if(q&&!beforeSearch)beforeSearch=[...document.querySelectorAll('details')].map(d=>[d,d.open]);let visible=0;
sections.forEach(s=>{const match=!q||s.textContent.toLowerCase().includes(q);s.hidden=!match;if(match){visible++;if(q)s.querySelectorAll('details').forEach(d=>d.open=true)}});
navLinks.forEach(a=>{const s=document.getElementById(a.hash.slice(1));a.hidden=!!s?.hidden});
status.textContent=q?`找到 ${visible} 个相关章节`:'';document.querySelector('#empty').hidden=visible>0;
if(!q&&beforeSearch){beforeSearch.forEach(([d,open])=>d.open=open);beforeSearch=null}});
function revealHash(){const el=document.getElementById(location.hash.slice(1));if(el){if(el.hidden){search.value='';search.dispatchEvent(new Event('input'))}for(let p=el.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true}}
window.addEventListener('hashchange',revealHash);revealHash();
const observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){navLinks.forEach(a=>a.classList.toggle('active',a.hash==='#'+entry.target.id))}}},{rootMargin:'-5% 0px -65% 0px'});sections.forEach(s=>observer.observe(s));
let printState=null;window.addEventListener('beforeprint',()=>{printState={details:[...document.querySelectorAll('details')].map(d=>[d,d.open]),hidden:sections.map(s=>[s,s.hidden])};document.querySelectorAll('details').forEach(d=>d.open=true);sections.forEach(s=>s.hidden=false)});
window.addEventListener('afterprint',()=>{if(printState){printState.details.forEach(([d,o])=>d.open=o);printState.hidden.forEach(([s,h])=>s.hidden=h);printState=null}});
document.querySelector('#print').addEventListener('click',()=>window.print());
'''
document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Confidence Agents：12批实验的目的、设定、真实案例、图表和结论。"><title>Confidence Agents · 实验报告</title><style>'+css+'</style></head><body><a class="skip" href="#main">跳到报告正文</a><aside><div class="brand">CONFIDENCE AGENTS</div><h2>实验报告</h2><button class="mobile-top" id="nav-toggle" type="button" aria-expanded="false" aria-controls="contents">目录</button><label for="search" class="source">查找实验或关键词</label><input class="search" id="search" type="search" placeholder="例如：新题、分差、供应商"><div class="search-status" id="search-status" role="status" aria-live="polite"></div><nav id="contents" aria-label="报告目录">'+navhtml+'</nav><div class="aside-note">先说明目的和做法，再看结果。<br>计算方法与原始记录可展开。</div></aside><main id="main">'+hero+'<p id="empty" class="filter-empty" hidden>没有找到相关章节，请换一个关键词。</p>'+''.join(sections)+'<footer class="footer">依据本地保存的实验清单、原始响应、结果和核验记录整理。<br>显示分数的影响，不自动等于内部信念、非理性或有害依赖。</footer></main><script>'+js+'</script></body></html>'
assert document.count('<svg ')==6
assert 'sk-or-' not in document
assert 'http://' not in document.replace('http://www.w3.org/2000/svg','')
assert 'https://' not in document
target=OUT/'confidence_agents_experiment_report_zh.html'
target.write_text(document,encoding='utf-8')
print(json.dumps({'html':str(target),'sections':len(sections),'charts':6,'bytes':target.stat().st_size},ensure_ascii=True))
