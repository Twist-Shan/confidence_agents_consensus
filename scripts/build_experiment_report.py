"""Build the Chinese evidence report from saved runs only; never sends API requests."""
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Line, Rect, Circle, String

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
OUT.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('CN', 'C:/Windows/Fonts/simsun.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('CNBold', 'C:/Windows/Fonts/simhei.ttf'))
pdfmetrics.registerFontFamily('CN', normal='CN', bold='CNBold', italic='CN', boldItalic='CNBold')
INK = colors.HexColor('#183047')
BLUE = colors.HexColor('#236C9C')
ORANGE = colors.HexColor('#BB623A')
GRAY = colors.HexColor('#687787')
PALE = colors.HexColor('#EDF3F7')
W = A4[0] - 88
styles = {
    'body': ParagraphStyle('body', fontName='CN', fontSize=10.2, leading=16.0, textColor=INK, wordWrap='CJK', spaceAfter=9),
    'small': ParagraphStyle('small', fontName='CN', fontSize=8.2, leading=12.1, textColor=GRAY, wordWrap='CJK', spaceAfter=6),
    'title': ParagraphStyle('title', fontName='CNBold', fontSize=23, leading=32, textColor=INK, spaceAfter=17),
    'h1': ParagraphStyle('h1', fontName='CNBold', fontSize=17, leading=23, textColor=INK, spaceAfter=13),
    'h2': ParagraphStyle('h2', fontName='CNBold', fontSize=11.5, leading=17, textColor=BLUE, spaceBefore=8, spaceAfter=7),
    'cell': ParagraphStyle('cell', fontName='CN', fontSize=8.5, leading=12.5, textColor=INK, wordWrap='CJK'),
    'caption': ParagraphStyle('caption', fontName='CN', fontSize=8.5, leading=13, textColor=GRAY, wordWrap='CJK', spaceBefore=5, spaceAfter=9),
}
story, readable, headings = [], [], []
def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))
def summary(name):
    return read(f'runs/{name}/summary.json')
def manifest(name):
    return read(f'runs/{name}/manifest.json')

RUNS = [
 ('E01','live-luna-smoke-20260918-account3','流程小测'),
 ('E02','calibration-luna-20260918','三题型难度校准'),
 ('E03','validation-luna-logic-20260918','逻辑 L1/L2 新题复核'),
 ('E04','expansion-luna-logic-l2-20260920','L2 自然分布扩样'),
 ('E05','balanced-luna-logic-l2-20260921','L2 平衡题库校准'),
 ('E06','reliability-luna-8192-json-20260921','输出可靠性压力测试'),
 ('E07','local-four-arm-luna-20260922','四条件局部重放'),
 ('E08','confidence-gap-luna-20260918','八条件分差探索'),
 ('E09','confidence-gap-replication-luna-20260923','分差独立新题复核'),
 ('E10','supplier-transfer-luna-20260918','供应商局部到群体预测'),
 ('E11','signal-visibility-luna-20260919','需求预测可见性探索'),
 ('E12','signal-visibility-replication-20260920','可见性独立新实例复核'),
]
S = {code: summary(name) for code,name,_ in RUNS}
M = {code: manifest(name) for code,name,_ in RUNS}
inventory = []
for code, name, label in RUNS:
    records = [read(str(p.relative_to(ROOT))) for p in (ROOT/'runs'/name).rglob('calls/*.json')]
    usage = S[code]['usage']
    assert len(records) == usage['requests'], (name, len(records), usage)
    cached, unknown, hits, tokens = 0,0,0,0
    for r in records:
        c = r.get('response',{}).get('usage',{}).get('prompt_tokens_details',{}).get('cached_tokens')
        if c is None: unknown += 1
        else: cached += 1; hits += int(c > 0); tokens += c
    times = [r['started_at'] for r in records if r.get('started_at')]
    inventory.append({'code':code, 'directory':name, 'label':label, 'requests':len(records),
        'valid':sum(bool(r.get('valid')) for r in records),
        'known_cost_usd':usage.get('known_cost_usd',usage.get('reported_cost_usd')),
        'unknown_cost_requests':usage.get('unknown_cost_requests',usage.get('requests_without_cost')),
        'cache_known':cached,'cache_unknown':unknown,'cache_hits':hits,'cached_tokens':tokens,
        'started_local':datetime.fromtimestamp(min(times), timezone(timedelta(hours=8))).isoformat(),
        'returned_models':dict(Counter(r.get('response',{}).get('model') for r in records if r.get('response'))),
        'source_hash':M[code].get('source_hash')})

def para(text, conclusion=None, style='body'):
    readable.append(text + ('\n本段结论：' + conclusion if conclusion else ''))
    markup = escape(text).replace('\n','<br/>')
    if conclusion: markup += '<br/><b>本段结论：</b>' + escape(conclusion)
    story.append(Paragraph(markup, styles[style]))
def h2(text):
    story.append(Paragraph(escape(text),styles['h2'])); readable.append('### '+text)
def page(title, source=None):
    if story: story.append(PageBreak())
    headings.append(title);readable.append('\n## '+title)
    story.append(Paragraph(escape(title),styles['h1']))
    if source: para(source,style='small')
def table(headers, rows, widths=None, size=8.5):
    cs=ParagraphStyle('tbl', parent=styles['cell'], fontSize=size, leading=size*1.45)
    cells=[[Paragraph(escape(str(c)).replace('\n','<br/>'),cs) for c in row] for row in [headers]+rows]
    t=Table(cells,colWidths=widths or [W/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LINEBELOW',(0,0),(-1,0),.7,BLUE),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#D5DEE5')),
        ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.extend([t,Spacer(1,9)])
    readable.append('| '+' | '.join(headers)+' |')
    for row in rows: readable.append('| '+' | '.join(map(str,row))+' |')
def caption(n,text,conclusion):
    para(f'图 {n}｜{text}',style='caption');para('图示结果：'+conclusion,'结论限于图注所列样本与条件。')
def textshape(d,x,y,s,size=9,color=INK,anchor='start'):
    d.add(String(x,y,s,fontName='CN',fontSize=size,fillColor=color,textAnchor=anchor))
def forest(rows, xmin, xmax, ticks, xlabel, height=205):
    d=Drawing(W,height); left,right,bottom,top=123,W-18,40,height-15
    X=lambda x:left+(x-xmin)/(xmax-xmin)*(right-left)
    for tick in ticks:
        d.add(Line(X(tick),bottom,X(tick),top,strokeColor=colors.HexColor('#DCE4EA'),strokeWidth=.5))
        textshape(d,X(tick),bottom-15,str(tick),8,anchor='middle')
    if xmin<=0<=xmax:d.add(Line(X(0),bottom,X(0),top,strokeColor=GRAY,strokeDashArray=[3,3]))
    step=(top-bottom)/len(rows)
    for k,(label,value,lo,hi,color) in enumerate(rows):
        y=top-step*(k+.5);textshape(d,left-9,y-3,label,8.5,anchor='end')
        d.add(Line(X(lo),y,X(hi),y,strokeColor=color,strokeWidth=1.5))
        d.add(Line(X(lo),y-3,X(lo),y+3,strokeColor=color));d.add(Line(X(hi),y-3,X(hi),y+3,strokeColor=color))
        d.add(Circle(X(value),y,3.2,fillColor=color,strokeColor=color))
    d.add(Line(left,bottom,right,bottom,strokeColor=GRAY))
    textshape(d,(left+right)/2,5,xlabel,9,anchor='middle');return d
def bars(labels, series, ylabel, ymax=100, height=215):
    d=Drawing(W,height);l,r,b,t=48,W-16,43,height-34
    for k in range(5):
        val=ymax*k/4;y=b+(t-b)*k/4;d.add(Line(l,y,r,y,strokeColor=colors.HexColor('#DCE4EA'),strokeWidth=.5));textshape(d,l-6,y-3,f'{val:g}',8,anchor='end')
    textshape(d,l,t+20,ylabel,9)
    group=(r-l)/len(labels);bw=min(35,group*.72/len(series))
    for si,(name,values,color) in enumerate(series):
        lx=r-140+si*95;d.add(Rect(lx,t+17,8,8,fillColor=color,strokeColor=color));textshape(d,lx+12,t+17,name,8)
        for j,value in enumerate(values):
            x=l+group*(j+.5)+(si-len(series)/2)*bw
            h=(t-b)*value/ymax;d.add(Rect(x,b,bw-2,h,fillColor=color,strokeColor=color));textshape(d,x+(bw-2)/2,b+h+4,f'{value:.1f}',7.5,anchor='middle')
    for j,label in enumerate(labels):textshape(d,l+group*(j+.5),b-17,label,8.5,anchor='middle')
    return d

total_calls=sum(x['requests'] for x in inventory)
total_valid=sum(x['valid'] for x in inventory)
total_cost=sum(x['known_cost_usd'] for x in inventory)
total_unknown=sum(x['unknown_cost_requests'] for x in inventory)

page('Confidence Agents\n阶段实验报告')
para('从难度校准、固定意见的分数交换，到真实初答与证据可见性的独立复核',style='h2')
para('报告范围：本地仓库中已完成的 12 批真实 Luna 运行、两项离线诊断，以及账户失败与模拟测试记录。截止于 noisy-demand-visibility-v1 新实例复核完成。目录中的 20260919 等数字常为随机种子，不应当作运行日期。','本文是一份实验过程与证据报告，不把 proposal 中尚未实施的设计写成已完成结果。')
table(['目前最重要的发现','证据与边界'],[
 ['可见性效应得到新实例支持','仅见建议时，高分从 A 方移到 B 方使 P(B) 平均增加 22.48 个百分点；与完整证据效应的差值区间为 [17.46, 27.27]。'],
 ['逻辑题反向趋势未明确复现','分差每增加 .10 的错误率差变化：旧题 -4.63 个百分点，新题 -0.26；新题区间跨零。'],
 ['局部到群体预测仍未完成核心验证','供应商任务更新接近全对；第二轮条件差对应完全相同的输入，不能作为置信度传播证据。'],
 ],[125,W-125],9)
para(f'12 批完成运行合计 {total_calls:,} 条请求记录、{total_valid:,} 条有效响应，已知 API 费用 ${total_cost:.6f}；其中 {total_unknown} 条请求费用未知。两次账户失败启动另列，不混入上述合计。没有新增模型调用。','所有实证结果来自同一个 API 模型 ID；未完成 GLM、Qwen 等跨模型比较。')
para('阅读方式：每项实验依次交代目的、设定、计算、简单例子、结果及当前结论。说明性例子与真实案例显式区分。图中的区间均标明统计单位；同一题的重复回答不计为独立题目。','先读总览和指标定义，再比较各批次，可避免把不同问题的效应混为一谈。')
para('编制依据：原始请求/响应、冻结 manifest、summary、独立审计与协议文件。全文保留与原假设相反及区间跨零的结果。',style='small')

page('01｜实验总览与阅读索引')
table(['编号','目的 / 样本','请求数','主要判断'],[
 ['E01','流程小测：2 题，六人讨论 + 局部重放','124','无混合初始状态，主效应不可估'],
 ['E02','3 题型 × 4 级 × 2 题','144','逻辑 L1/L2 值得进一步复核'],
 ['E03','L1/L2 新题各 2 道','24','L2 暂满足阈值，L1 未复现'],
 ['E04','L2 自然分布新题 20 道','120','95% 正确；仅 3 道分歧'],
 ['E05','L2 平衡语义/选项 40 题','240','80.9% 有效正确率；存在输出失败'],
 ['E06','8 道旧失败题，新配置复测','48','48 次有效；不能分解配置作用'],
 ['E07','40 题 × 4 条件 × 3 次','480','错误率差 -1.71 pp，区间跨零'],
 ['E08','旧 40 题 × 8 条件 × 3 次','960','负向分差斜率，探索性'],
 ['E09','新 40 题复核相同八条件','960','负向斜率未明确复现'],
 ['E10','供应商 8 训练 + 8 测试题','592','完整证据后近全对，预测未获益'],
 ['E11','需求预测 16 题 × 两可见性','608','仅建议的分数效应更大'],
 ['E12','固定协议、新生成 16 题','576','15 题纳入；交互方向复现'],
 ],[38,205,49,W-292])
para('E05 的 40 道题随后用于 E07/E08，属于题库复用；E06 使用其中曾发生失败的 8 道题。E09 更换独立逻辑题。E11 与 E12 使用不同需求信号实例；E12 仍沿用同一生成机制。','不能把所有运行的题数简单相加，当作互不重叠的独立样本量。')
para('另有：80 道逻辑题的事后异质性诊断、缓存审计，以及发现批次需求任务的条件概率解释。模拟测试仅验证管线，账户失败测试没有可分析行为结果。','离线分析不增加独立实验，也不增加模型调用数。')

page('02｜研究对象、干预与信息边界')
h2('我们测量什么')
para('核心问题是：冻结题面、初始意见、成员身份及报告顺序，只改变显示 confidence 的归属，下一次判断会怎样改变？proposal 还要求用局部变化预测完整群体轨迹；现有实验只部分覆盖这一目标。','已测到的局部响应与尚待验证的群体传播必须分别陈述。')
table(['概念','定义及用途'],[
 ['agent / 成员','独立调用的同模型实例，由程序显式提供上下文；中立编号，无上下级。'],
 ['初始状态（root）','同题六人的一组实际初答；各处理条件复用同一组初答。早期局部逻辑题使用预设答案，不能称为真实初始状态。'],
 ['自报概率 p_B','模型输出“B 为正确选项 / 高需求”的概率。其所选答案置信度为：选 B 用 p_B，选 A 用 1-p_B。'],
 ['显示分数 c','输入给接收者的报告分数，部分由实验者替换；不等于模型真实信念或历史准确率。'],
 ['固定分数集合','交换高低分时，同一接收者看到的数值集合相同，仅分数对应的同伴/立场改变。'],
 ['完整证据 / 仅建议','需求任务中 full 提供同伴原始信号；advice 保留同伴答案与显示分数，隐藏其原始信号。'],
 ],[115,W-115])
h2('简单例子：同样的票数，不同的分数归属')
para('说明性例子：两人支持 A，两人支持 B。第一条件给 A 方 .95、B 方 .55；第二条件对调。两条件票数相同，分数集合都是 {.95,.95,.55,.55}。如果接收者改变回答，可研究这组数字归属的影响。','分数交换能隔离输入层面的归属变化；仍需重复与跨题分析排除采样波动。')
para('在 E10-E12，只对未被选中交换分数的成员计算严格局部主比较，因为他们能同时看到两名交换对象的报告。交换对象看不到自己的分数，可见分数集合未必保持不变。','全局分数集合固定与每位接收者的分数集合固定是不同的控制条件。')

page('03｜指标与计算方法：正确性和分差')
h2('有效性、正确率与分歧')
para('有效正确率 = 有效且正确的回答数 / 有效回答数。输出截断、非法格式及未返回响应单独记录。校准中的“完整分歧题”要求六次回答均有效，且同时有正确与错误答案；分歧率必须明确以全部题还是完整题为分母。','缺失不能直接记为模型答错；分歧率不等于同题长期稳定的出错概率。')
h2('E07-E09：错误率配对差')
para('令 e(q,a,r)=1 表示题 q 在条件 a 的第 r 次回答错误，否则为 0。题内错误率 E(q,a)=Σ e/R。配对效应 Δ(q,g)=E(q,wrong_high,g)-E(q,correct_high,g)，g 为高低分之差；跨题 Δ(g) 为完整配对题的等权平均。正值表示错误方高分增加错误率。','单位是错误概率差；乘 100 后为百分点（pp），不表示相对百分比增长。')
para('说明性例子：同题错误方高分时 2/3 错，正确方高分时 1/3 错，则 Δ=1/3，即 +33.3 个百分点。若另一题 Δ=-1/3，两题等权平均为 0。','单题大差值可能由每格仅三次采样造成，不能直接视为稳定效应。')
h2('E08/E09：分差斜率')
para('三个分差 g∈{.10,.30,.40}。对每道完整题计算最小二乘斜率：β(q)=Σ[(g-g均值)(Δ(q,g)-Δ均值)] / Σ(g-g均值)²，再对题平均 β。报告“分差每增加 .10 的百分点变化” = 100×.10×β = 10β。等分组没有被当作人为的零效应点纳入回归。','β 描述三个预定分差上的线性趋势，不意味着更大分差范围也线性。')
para('说明性例子：若 Δ=.2g，则 β=.2；分差增加 .10，错误率差增加 .02，即 2 个百分点。该示例仅解释计算，未充当实验数据。','趋势的方向取决于配对差定义，不能把负斜率直接解释为高分有益。')

page('04｜指标与计算方法：概率、区间与缺失')
h2('E11/E12：自报概率的定向移动')
para('每题、每种可见性 v，先对两名接收者、两次重复求平均：Δ(q,v)=Σ[j,r](p_B(q,j,v,B_high,r)-p_B(q,j,v,A_high,r))/4。再对完整题等权平均。交互 I(q)=Δ(q,advice)-Δ(q,full)。正值表示仅建议时的归属效应更大。','该指标按 A/B 立场定义，与实际需求是否为 B 无关；它测量定向影响，不直接测量损害。')
h2('预测质量与重复波动')
para('需求任务 Brier = 平均(p_B-y)²，y=1 表示实际高需求；越小越好。完整后验距离 MSE = 平均(p_B-p_full)²。选择 B 比例用 1[p_B>.5] 计算；阈值为 .5 时选择 A。相同输入重复差 = 平均 |p_B(r=0)-p_B(r=1)|。','Brier、后验距离、选项变化和概率变化衡量不同对象；重复差不能直接充当处理效应标准误。')
h2('题级分层 bootstrap')
para('冻结同题的配对差，在层内有放回抽取与原层同样多的题，共 2000 次；每次跨题等权求平均。使用排序后第 50 与第 1950 个结果作为描述性 95% 区间。逻辑局部实验按语义真值、正确选项和预设自身正确性分层；需求实验按实际高/低需求分层。供应商实验按题进行配对重抽样。','独立分析单位是题；同题的成员和重复回答不应扩大题级样本量。')
para('区间跨零表示现有数据不能清楚确定方向，不是等价性证明；全为零的样本产生 [0,0]，也不证明总体效应为零。分差实验的多个次要区间没有多重比较校正。','本报告把区间作为小样本描述，不追认充分功效或普遍效应。')
h2('缺失响应界限')
para('把所有缺失回答分别赋为正确或错误，计算目标点估计所有可能取值的最小值和最大值，得到确定性缺失界限。完整题分析排除任何相关条件有缺失的题，因此其点估计可能不在全题缺失界限内。','缺失界限与抽样置信区间解决不同问题，二者不相互替代。')

page('05｜E01：真实 API 与实验流程小测','来源：E01 manifest、summary、REPORT、原始 calls。')
h2('目的与设定')
para('验证真实 API、日志、同步更新和局部重放能否运行。使用两道可精确核验的开发题：贝叶斯比较和模运算状态追踪；每题六个独立初答。实际 smoke 配置为 aligned/misaligned/hidden 三条件、两轮同步更新，另做 4 个合成局部上下文 × 10 条件 × 1 次。共 12+72+40=124 次。','本轮仅验证流程，不具备正式假设检验的题量和上下文覆盖。')
para('同模型 ID 为 openai/gpt-5.6-luna，2048 token 上限，供应商默认推理参数，未启用后来的 strict JSON 约束。六人全连接，答案随轮更新，分数按初始分配跟随成员；局部小测只覆盖自身 A、所有邻居 A、度数 2-5。','该小测配置与 proposal 的完整协议和后续实验均应分别记录。')
h2('简单例子')
para('说明性状态题：从 x=2 开始，依次做 x←(3x+1) mod 5、x←(2x) mod 5，得到 x=4，最终为偶数。模型可以自行计算，也可能参考同伴；如果六人最初都答对，正确/错误成员间的高分归属无法形成有意义的主比较。','无初始分歧本身就是实验可辨识性问题。')
h2('结果与分析')
table(['指标','结果'],[['有效响应','124/124'],['初答','两题各 6/6 正确'],['有分歧初始状态','0'],['最终六个“题×条件”组','错误比例全部为 0'],['局部重放','40/40 正确'],['已知费用','$0.019365']],[180,W-180])
para('限定于分歧状态的主要效应为 null，不能把全状态错误率差为 0 当作置信度无作用。此前两个账户启动各保留一条失败记录，无有效行为结果。','流程已跑通；下一步必须先校准能产生分歧的任务，而不能重复抽样直至得到想要的状态。')

page('06｜E02：三题型、四等级难度校准','来源：E02 manifest、summary、REPORT。')
h2('目的、生成规则与例子')
para('寻找不会几乎全对、且能自然产生对错分歧的题。状态追踪、多假设贝叶斯更新、逻辑蕴含各 4 个生成等级，每级 2 题，每题独立回答 6 次；共 24 题、144 请求，2048 token、默认推理设置。不存在同伴输入或分数干预。','等级指生成复杂度，尚未验证为模型难度的单调尺度。')
para('说明性例子：状态题逐步更新整数；贝叶斯题按“先验×似然，再归一化”比较假设；逻辑题若前提为 X1 和 (非X1 或 X2)，则必然得到 X2。实际逻辑 L1/L2 分别有 5/7 个变量、20/28 个三文字子句，穷举真值。','真值来自确定性计算，无需模型裁判。')
table(['题型','L1 正确/有效','L2','L3','L4'],[
 ['状态追踪','12/12','12/12','12/12','12/12'],['贝叶斯更新','12/12','11/11','8/9','12/12'],['逻辑蕴含','7/12','9/12','12/12','11/11']], [110,99,99,99,W-407])
h2('筛选规则与结果')
para('运行前规定：题型×等级有效正确率 30%-85%，无效率不超过 10%，且至少一题六次有效回答同时有对有错。139/144 有效、130/139 正确；5 次无效含 4 次格式错误和 1 次截断。只有逻辑 L1（58.3%，2/2 分歧）与 L2（75%，1/2 分歧）达到探索阈值。','候选为逻辑 L1/L2，但每层两题不足以确认稳定难度。')
para('L3/L4 生成规模更大却几乎全对；造成这种差异的具体原因未查明。单凭这批结果不能认为更复杂题必然更难，也不能将 Luna 难度结论推广到 GLM/Qwen。','推荐只是下一轮取样依据，需要独立新题复核。')

page('07｜E03/E04：新题复核与自然分布扩样','来源：E03/E04 manifest、summary、REPORT。')
h2('E03 目的、设定、例子与结果')
para('按上一轮冻结的新 seed 20260919，L1/L2 各两题，每题六次、共 24 请求，模型与 2048 token 设置不变。简单理解：把“某一题较难”改成检验“同级新题仍较难”，不复用旧题答案。L1 为 12/12 正确且无分歧；L2 为 10/12 正确、1/2 题分歧，仍满足旧阈值。','L1 的初始现象未复现，L2 可继续扩样，但仍仅两题。')
h2('E04 目的与设定')
para('预先固定 L2 新题 20 道，每题六次，共 120 请求，不按模型表现选题。7 变量、28 子句，seed 20260920，穷举核验。自然生成后只有 3 题蕴含、17 题不蕴含；A/B 正确选项 12/8。','目标题目分布明显不平衡，必须分层报告。')
table(['语义答案','题数','正确/有效','正确率','分歧题'],[
 ['蕴含','3','13/18','72.2%','2/3'],['不蕴含','17','101/102','99.0%','1/17'],['合计','20','114/120','95.0%','3/20']], [100,55,105,100,W-360])
h2('实际案例：v4 的错误与反例')
para('真实 v4 问“28 条前提是否必然推出 X1？”精确枚举 128 个赋值，有 6 个满足全部前提；其中 (X1,...,X7)=(0,0,1,0,1,0,1) 就是 X1 为假的反例，因此答案为不蕴含。六次回答为 A,A,A,B,A,A；唯一错误回答给出 p_B=.99。完整 28 条前提列于附录。','一条反例足以否定蕴含；高自报概率没有保证这次回答正确。')
para('17 题六次全对，3 道分歧题分别为 5/6、4/6、3/6 正确。总体 95% 超过原阈值上限，因此未达到推荐标准；始终答“不蕴含”的基线已为 85%。','自然分布的 L2 仍偏容易；不能只挑三道分歧题作为正式确认性题库。')

page('08｜E05：平衡题库重新校准','来源：E05 manifest、summary、diagnostics、wrong_answers。')
h2('目的与设定')
para('只用精确真值、从固定候选序列依次填满蕴含/不蕴含各 20 题，每类 A/B 正确选项各 10。共检查 113 个候选，不看模型回答筛题；每题六次，仍用 2048 token 原配置。简单例子：原来 20 题里仅 3 题为蕴含，本轮强制两类各半。','题库分布改变了，总体正确率变化不能解释成模型能力随时间变化。')
story.append(bars(['自然分布 E04','平衡分布 E05'],[('蕴含',[100*13/18,100*72/112],BLUE),('不蕴含',[100*101/102,100*114/118],ORANGE)],'有效回答正确率（%）'))
caption(1,'横轴为两批不同题库；纵轴为有效回答正确率（%）。蓝色为蕴含，橙色为不蕴含；无误差条，仅作描述。E04 两类分别 3/17 题，E05 各 20 题；同题六次回答不视为独立题。','两批中蕴含题的观察正确率均较低；这里没有识别语义类别本身的因果作用。')
table(['总体结果','值','分层结果','值'],[['有效正确率','186/230=80.9%','蕴含','72/112=64.3%'],['无效响应','10/240=4.17%','不蕴含','114/118=96.6%'],['完整分歧题','15/40；完整题内 15/32','不完整题','8/40']],[110,140,100,W-350])
para('44 条有效错误回答的所选答案自报概率均≥.99，均值 .9960。该指标为选 B 用 p_B、选 A 用 1-p_B；没有把这个私有概率直接当作后续受控显示分数。','本轮达到探索性难度阈值，并记录了高自报概率错误；尚未证明任何置信度干预效应。')

page('09｜E06：输出截断与格式可靠性','来源：E05 invalid_responses、E06 REPORT 与原始请求。')
h2('目的、诊断与配置')
para('E05 的 8 次截断都记录 completion_tokens=2048、reasoning_tokens=2048、content=null：推理与最终输出共享预算在最终答案前用尽。另两条正常结束响应将数字写成“1.”，不符合 JSON。新配置统一为 8192 token、显式 medium、strict JSON Schema，拒绝不支持参数的供应商并关闭 fallback。','截断与格式错误的直接证据不同，处理时应分开记录。')
h2('简单例子与复测设计')
para('说明性例子：即使最后答案只需 {"answer":"A"}，模型仍可能先消耗 2048 个推理 token，因而没有最终内容。压力测试取全部 8 道曾失败题，每题全新回答六次；旧记录保留，不拼接、不修补、不替换。','这是一项针对失败情形的工程复测，不能无偏估计全题库失败率下降。')
table(['指标','旧配置：同八题','新配置：同八题'],[['有效/总响应','38/48','48/48'],['截断 / 格式失败','8 / 2','0 / 0'],['最大输出 token（含推理）','2048','1897'],['输出 token 中位数','1016.5','1021.5'],['正确/有效','不作为本轮对照主指标','26/48'],['已知费用（美元）','0.073457','0.067414']], [205,(W-205)/2,(W-205)/2])
para('新 48 次输出没有一次超过旧 2048 上限，因此本次零失败不能归因于单独增大预算；还同时改变了显式推理设置及输出 schema。后续 E07 有 3 次成功输出超过 2048，最大 2743，说明额外余量确实被使用过。','新配置可用于后续统一运行，但不能保证零失败或声称 8192 是最小安全值。')

page('10｜E07：四条件局部 confidence 对照','来源：E07 manifest、summary、audit、recovery。')
h2('目的、设定与简单例子')
para('检验固定意见下，给错误报告高分是否提高接收者错误率。复用 E05 的全部 40 题；每题自身答案和四份同伴答案均为预设，同伴两对两错。语义×正确选项层内，自身预设正确/错误各半。单接收者、四条件各三次，共 480 请求，统一可靠配置。','这是受控的一次局部更新；没有六名真实同伴生成意见。')
para('真实首题正确选项为 B，自身预设 B，同伴顺序为 A,B,B,A。correct_high 给两份 B .95、两份 A .55；wrong_high 反向；equal 全 .75；hidden 无分数。各条件题面、身份、答案和顺序一致。','主比较保持四份报告的票数及分数集合相同。')
table(['条件','有效响应','错误数','题均错误率'],[['正确方高分','120','28','23.33%'],['错误方高分','119','26','21.67%'],['全部 .75','120','24','20.00%'],['隐藏分数','120','33','27.50%']],[155,105,95,W-355])
h2('主结果、缺失与分析')
para('39 道完整配对题的 Δ=-1.71 个百分点，题级分层 95% 区间 [-8.55,+5.13]；逐题 8 正、8 负、23 零。表内题均错误率使用各条件可用回答，因此两列相减未必等于完整题的主效应。','没有观察到错误高分提高错误率的明确证据，也不能据此证明无效或有益。')
para('终端中断留下 1 条 pending，未重发；确认进程退出后只补发 3 条从未开始的计划请求。479 条可观察响应均正常结束。全 40 题对唯一缺失赋正确/错误，点估计界限为 [-1.67,-0.83] 个百分点；它不是抽样区间。','缺失和恢复操作均保留；次要 equal/hidden 差异只作描述。')

page('11｜E08：八条件分差探索','来源：E08 manifest、summary、REPORT；配对标签经原始请求核验。')
h2('目的、固定条件与例子')
para('在既有 40 题上考察影响是否随高低分差增大。沿用 E07 的预设自身与同伴答案，统一添加“confidence 为报告者所选答案正确概率”的定义；新提示与 E07 不直接合并。高低分为 .80/.70、.90/.60、.95/.55，各交换归属，另有全 .75 与隐藏分数，共八条件、每格三次、960 请求。','各数值对的平均为 .75，改变的是分差及其归属。')
para('说明性例子：若错误方高分时错误率从 20% 降至 10%，同时正确方高分的错误率也变化，必须计算两个条件的差，再判断分差趋势。仅看某一条件下降不能推出分数归属效应。','主要终点是题内 Δ 对分差的斜率。')
table(['分差','配对题','Δ（百分点）','95% 描述区间'],[['.10','38','+4.39','[-3.51,+11.40]'],['.30','39','-8.55','[-15.38,-0.85]'],['.40','39','-7.69','[-17.09,+1.71]']],[75,75,145,W-295])
para('主要斜率用六个不等分条件全完整的 36 题：分差每增加 .10，Δ 改变 -4.63 个百分点，区间 [-8.00,-1.46]。954/960 有效，6 条 unresolved 不重发；已知费用 $1.214094，6 条费用未知。','这批旧题观察到与原方向相反的探索性趋势。')
para('全部 720 条不等分请求经真值逐条核验，正确方/错误方标签未反转。全 40 题任意填补缺失后的平均斜率范围为 [-4.46,-3.57] 个百分点/.10 分差，仅量化缺失影响。题库已用于探索，三个次要分差区间未作多重比较校正。','标签错误不足以解释反向结果；其行为原因未查明，必须用新题复核。')

page('12｜E09：分差趋势的独立新题复核','来源：E09 manifest、summary、REPORT；E08 作为分开报告的发现批次。')
h2('目的、设定与易懂例子')
para('固定八条件、三重复、提示和分析，更换为 seed 20260923 的 40 道平衡 L2 题；上下文 seed 仍 20260922。与此前 88 个去重问题核对，无同一规范化子句/查询组合，但未排除变量重命名同构。简单理解：换一套试卷，用完全相同的评分与干预方案检查旧趋势。','独立复核关注新题结果本身，不靠合并两批获得结论。')
rows=[]
for code,label,col in [('E08','旧题探索',BLUE),('E09','新题复核',ORANGE)]:
    s=S[code];lo,hi=s['descriptive_stratified_item_bootstrap_95pct'];rows.append((label,10*s['primary_slope'],10*lo,10*hi,col))
story.append(forest(rows,-9,5,[-8,-4,0,4],'分差每增加 .10 的错误率差变化（百分点）',155))
caption(2,'横轴为题均斜率换算后的百分点变化；纵轴为两批不同逻辑题。点为估计，横线为按题分层 bootstrap 95% 区间，虚线为零。两批主分析均为 36/40 题；蓝色为旧题，橙色为新题。','旧题 -4.63，新题 -0.26 个百分点/.10 分差；新题区间 [-4.23,+3.57] 包含零。')
table(['分差','旧题 Δ','新题 Δ','新题 95% 区间','新题配对题'],[['.10','+4.39','0.00','[-8.33,+8.33]','40'],['.30','-8.55','-0.90','[-7.21,+5.41]','37'],['.40','-7.69','+5.13','[-0.85,+11.11]','39']],[50,75,75,190,W-390])
para('新题 952/960 有效、8 条未返回，已知费用 $1.167823。全 40 题对缺失任意填补后，平均斜率范围为 [+0.89,+1.31] 个百分点/.10；与完整 36 题的 -0.26 方向不同。各分差用不同完整子集，不能从三个表均值反推主要斜率。','反向趋势未明确复现，且接近零的点估计对完整题筛选敏感；不支持稳定反向效应。')

page('13｜离线诊断：题目差异与重复稳定性','来源：runs/item-diagnostics/REPORT.md 与 diagnostics.json；没有新增调用。')
h2('目的与方法')
para('使用 E08/E09 的 80 道不同题，事后区分：题型层面表现不同，还是同题内分数效应稳定。按语义、预设自身正确性和选项位置分层；另对主要斜率逐一删题重算，并统计相同条件三次回答不一致的比例。','所有分层均为事后探索；不能当作预注册的异质性结论。')
table(['指标','旧题探索','新题复核'],[['隐藏分数：蕴含错误率','38.33%','21.67%'],['隐藏分数：不蕴含错误率','8.33%','0.00%'],['最大分差：蕴含 Δ','-19.30 pp','+11.67 pp'],['最大分差：不蕴含 Δ','+3.33 pp','-1.75 pp'],['删一道题后斜率范围（pp/.10）','[-5.44,-3.67]','[-1.22,+0.48]'],['三次回答不一致的完整单元','122/314','102/312']],[255,(W-255)/2,(W-255)/2])
h2('简单例子与计算边界')
para('说明性例子：同题一条件三次全错，另一条件三次全对，看起来相差 100 个百分点；若把两组视为独立二项样本并固定边际，双侧 Fisher 精确检验 p=2/C(6,3)=.10。每格三次使单题错误率只能取 0、1/3、2/3、1。','单题极端差异仍可能不稳定；需要增加预定重复数才能更精确估计。')
para('隐藏分数仍保留预设自身答案和同伴答案，因此它不代表纯独立答题能力。一组区间跨零、另一组不跨零，也不足以证明组间差异；需要直接检验交互。两批题不同，无法计算同题跨批重测相关。','可以确认观察到的表现随题目集合变化；造成变化的机制尚未识别。')

page('14｜E10：供应商选择的真实初答设计','来源：E10 PROTOCOL、manifest、roots；SUPPLIER_TASK_EXAMPLE.md。')
h2('目的与设定')
para('引入真实私人信息初答，再问局部效应能否预测新题群体结果。8 道训练题、8 道独立测试题，每题六名平级成员。公共记录一项、私人记录六项，每项提供 A/B 净效益；按唯一来源求和选较大者。初始只见公共项与自己私有项，题目声明未见差值期望为零；更新时完整披露。','初答相对完整材料的“错误”不自动表示私人信息下推理不合理。')
h2('实际例子：train-00')
table(['审计记录','A 净效益','B 净效益','A-B','初始可见者'],[['公共项',27,31,-4,'全部'],['私人 1',60,71,-11,'成员 0'],['私人 2',71,64,7,'成员 1'],['私人 3',60,61,-1,'成员 2'],['私人 4',69,67,2,'成员 3'],['私人 5',46,44,2,'成员 4'],['私人 6',44,36,8,'成员 5'],['合计',377,374,3,'更新时全部']],[105,80,80,65,W-330])
para('真实初答为 B,A,B,B,B,A。成员 0 只见差值 -4-11，选 B；成员 1 见 -4+7，选 A；全信息时 A 比 B 高 3。随机选成员 0/1 交换 .55/.95，其他四人为 .75。局部主比较使用成员 2-5，各自看到的全部证据与分数集合不变。','这个例子把初始信息不足与最后选择错误清楚区分。')
para('训练题四条件（aligned、misaligned、equal、hidden），六名成员各一次局部更新。测试题三条件、六人同步两轮：首轮显示分数，次轮隐藏。另做每题一个全信息单模型对照。总计 112+192+288=592 请求；真实初答均存在分歧。','该实验确实包含六人动态更新，但证据由程序强制完整披露。')

page('15｜E10：局部与群体结果，以及输入审计','来源：E10 summary、RESULTS_ZH、independent_audit、group_results。')
h2('结果')
table(['训练局部条件','全部六成员错误 / 48','四名主比较接收者'],[['正确方高分','0/48','0 错误'],['错误方高分','0/48','0 错误'],['全部等分','0/48','0 错误'],['隐藏分数','1/48','0 错误']],[150,170,W-320])
para('8 道训练题主效应为 0；主分析的初答正确者 22 人次均保持正确，初答错误者 10 人次全部改正。全信息单模型对照 15/16 正确，真实初答 96/96 符合题目声明的私人期望效用规则。','完整披露后表现接近上限，局部 pilot 没有提供可预测的非零分数效应。')
table(['测试轮次','正确方高分错误率','错误方高分错误率','隐藏分数错误率'],[['第 1 轮','0/48=0%','0/48=0%','0/48=0%'],['第 2 轮','0/48=0%','2/48=4.17%','1/48=2.08%']],[95,137,137,W-369])
h2('为什么第 2 轮差异不能称为传播')
para('逐字节请求哈希核验发现：第二轮全部 48 个“题×成员”组合，其三个条件输入完全相同。首轮答案都已一致正确，第二轮又隐藏分数且不保留完整历史，因此条件标签没有通过输入继续传递。','第二轮少数错误差异属于相同输入下的响应变动，不能用作首轮 confidence 传播证据。')
para('说明性例子：若三个分支首轮全为 A，次轮都只看到同样的证据和五个 A，程序虽把三次调用放在不同分支，模型实际收到相同文本。偶尔某次答 B，不足以归因于早先的高分归属。','必须检查实际输入是否保留了干预产生的状态差，才能解释后续组间差异。')
para('所有 592 次响应有效，已知费用 $0.151426；群体各轮所有条件均无错误多数或错误一致。零效应样本产生的退化 bootstrap 区间不构成等价性证明。','当前结论只覆盖这一完整、可核验的加法效用任务。')

page('16｜E10：局部到群体预测的计算与表现','来源：E10 冻结源码、预测文件、summary 与独立审计。')
h2('目的、拟合与递推')
para('仅用 8 道训练题的局部更新拟合 P(下一答案=B)=σ(θ·x)，σ(z)=1/(1+exp(-z))。无分数基线有 5 个特征：截距、-完整 A-B 差/10、自身前答符号、同伴符号均值、-私人 A-B 差/12；B 编码 +1，A 编码 -1。分数模型额外加入同伴平均[(c-.75)×符号/.2]及是否显示分数。','两模型使用相同训练行为，差别是是否提供两个分数相关特征。')
para('逻辑回归截距外 L2=.01、2000 步、步长 .2，不用测试题调参。先保存模型和测试两轮预测，再发测试更新。每步枚举六人全部 64 种答案状态；给定共同上一步状态，以六个独立 Bernoulli 转移概率的乘积构造下一状态分布，再递推第二轮。','条件独立及一步记忆是预测近似，尚未验证为真实模型行为规律。')
h2('简单例子与评价对象')
para('说明性例子：若预测两位成员下一次选 B 的概率分别为 .6/.7，独立近似下二人都选 B 的概率为 .42；六人情况同理相乘。这里的 Brier 用实际成员选择 B 的指示变量作为标签，不是题目的正确选项。','预测模型是在预测 agent 行为，而非直接回答任务。')
table(['轮次','含 confidence Brier','无 confidence Brier','前者减后者'],[['第 1 轮','0.046554','0.046153','+0.000401'],['第 2 轮','0.043829','0.042062','+0.001767']],[70,155,155,W-380])
para('两轮中加入 confidence 的预测误差都略高；两模型预测的群体处理差都为 0。实测第二轮 +4.17 个百分点又对应相同输入的波动。因此，当前数据没有显示分数特征带来独立测试预测收益。','局部到群体的代码流程可运行，但核心“预测非零社会影响”的研究目标仍未得到验证。')

page('17｜E11/E12：需求预测任务与控制条件','来源：SIGNAL_VISIBILITY_PROTOCOL、E11/E12 manifest、REPLICATION_PLAN。')
h2('目的与任务生成')
para('区分“可以自行核验全部证据”和“只能看到同伴建议”时的分数归属影响。每批 16 个市场，实际高/低需求各 8；每人三条调查，共 18 条。给定真实需求，信号独立且准确率 .60，模型被告知先验 .50。先调用六名成员取得真实初答，只有同时存在 A/B 的状态进入干预，不补抽。','高低需求的平衡在运行前固定，题目不按干预效果挑选。')
table(['共同信息','full：完整证据','advice：仅见建议'],[['本人输入','自己的三条信号 + 真实前答/p_B','相同'],['五名同伴','真实初答 + 显示分数 + 三条原始信号','真实初答 + 显示分数'],['同伴理由 / 原始 p_B','均不额外传播','均不额外传播'],['题面、身份、顺序','固定','与 full 相同']],[110,(W-110)/2,(W-110)/2])
h2('分数与接收者')
para('在一名支持 A 者与一名支持 B 者间交换 .60/.771429，另四人保留各自初答所选答案的自报概率。两名接收者从未被交换的四人中抽取；四条件为 B_high、A_high、交换两人等分 .685714、全部隐藏分数。注意等分只作用于所选二人，其他四人的分数不统一改写。','两主条件同时保持每个接收者的意见、证据和可见分数集合不变。')
para('简单例子：一位支持 A、一位支持 B。给 B .771429、A .60，或反过来；两条件中 A/B 票数不变。每个接收者在 full/advice 下均做四条件各两次，共每个合格题 2×2×4×2=32 次更新；另有六次初答。','这是两个局部接收者的响应实验，还没有对六人做完整群体 rollout。')
para('统一模型设置为 Luna、medium、8192 token、严格输出 answer/p_B/reason；提示要求 p_B>.5 选 B，否则选 A，以平方误差评价预测，没有要求相信高分或按分数加权。','分数如何影响输出由模型响应决定，程序没有把效应写入最终聚合规则。')

page('18｜需求预测的概率计算与解释边界')
h2('精确后验')
para('若 n 条信号中 h 条为 high，先验赔率为 1，则后验赔率 O=(.6/.4)^h×(.4/.6)^(n-h)=(3/2)^(2h-n)，p_full=O/(1+O)。实际计算用精确分数；完整信息 n=18，私人信息 n=3。','完整后验是已知生成模型下、看到全部原始信号时的规范概率基准。')
para('说明性例子：私人三条中两 high 一 low，O=1.5，因此 P(B)=.60；三条全 high 时 O=3.375，P(B)=27/35≈.771429。这两个数正是干预用的高低分。完整 18 条若 12 high、6 low，则 p_full=729/793≈.919294。','显示分数在数值上可以被接收者理解为不同强度的私人证据，但这种理解不是机制证据。')
h2('仅建议、忽略分数的辅助参考')
para('若假设同伴始终按三条调查多数给出建议，则单个建议准确率 r=3a²(1-a)+a³=3a²-2a³=.648，其中 a=.6。目标先用自身三条信号得到赔率；每个 B 建议乘 r/(1-r)=81/44，每个 A 建议乘 44/81，再归一化。','该参考依赖同伴遵循多数策略的假设，不是未知 LLM 通信策略下唯一正确的后验。')
h2('受控分数与规范性')
para('实验者交换后的分数不保证忠实反映各同伴私有信号。full 中原始信号已全部给出，分数不增加实际状态信息；advice 中隐藏了原始信号，分数可能被当作证据强度线索。模型的文字理由可用于提出假设，但不能证明内部计算路径。','观察到 advice 受分数影响，不能直接定性为盲从、非理性或有害。')
para('每题完整配对需两名接收者、两次重复、两可见性及两主条件均有效。相同输入的重复调用各有独立 call_id，不复制一次响应凑重复。主区间以实际高/低需求分层、按题重抽样。','概率移动的可解释性依赖严格配对和明确的信息集合。')

page('19｜E11：证据可见性探索的结果','来源：E11 summary、independent_audit、RESULTS_ZH。')
h2('结果与样本')
para('16/16 个真实初始状态存在分歧；96 初答加 512 更新，共 608 次有效、无截断，已知费用 $0.527820。96/96 初答符合私人三信号多数策略。两接收者、两重复先题内平均，16 题等权。','该批具备完整配对，但仍属于前期探索后选定的新任务 pilot。')
rows=[]
for key,label in [('full','完整证据'),('advice','仅见建议'),('interaction','两条件效应差')]:
 p=S['E11']['primary'][key];lo,hi=p['descriptive_item_bootstrap_95pct'];rows.append((label,100*p['mean_p_B_shift'],100*lo,100*hi,BLUE))
story.append(forest(rows,-3,24,[0,5,10,15,20],'P(B) 变化或变化差（百分点）',205))
caption(3,'横轴为将高分由 A 方移向 B 方的题均概率变化；纵轴为 full、advice 及 advice-full。蓝点为估计，横线为 16 题分层 bootstrap 95% 区间；虚线表示零。每题四个接收者×重复配对先合为一项。','仅建议 +14.81 pp，完整证据 -0.067 pp；交互 +14.87 pp，区间 [10.30,19.59]。')
table(['指标','完整证据','仅见建议'],[['P(B) 变化的区间（pp）','[-0.2023,+0.0009]','[10.34,19.65]'],['选择 B 比例变化','0 pp','+10.94 pp'],['相同输入重复平均绝对差','0.147 pp','3.890 pp']],[225,(W-225)/2,(W-225)/2])
para('15/16 题仅建议效应为正，15/16 题交互为正；demand-09 的仅建议效应为 -2.53154 pp，完整保留。零答项/概率阈值不一致。','结果支持本批内的信息条件差异，但当时仍需新实例复核，不能只凭正向题占多数宣称普遍规律。')

page('20｜E12：固定协议的新实例独立复核','来源：E12 REPLICATION_PLAN、PREFLIGHT、summary、independent_audit。')
h2('目的、唯一改变及纳入规则')
para('保持模型、提示、分数、重复次数、分配顺序规则与分析方法，任务生成种子从 20260919 改为 20260920；实验分配与 bootstrap 种子仍为 20260919。16 新题无原始信号重复；若忽略成员身份，只比较各人信号数量，则 4/16 与旧批结构等价，未因此重新挑题。','这是同一机制的新样本复核，未宣称跨任务家族泛化。')
para('15/16 题出现真实初答分歧，另 1 题一致而依原协议排除，不补题。96 初答加 480 更新，共 576/576 有效，无截断，费用 $0.467750。预先判断标准为新批交互正向、其描述区间不含零，并检查 advice 方向。','实际样本数由原始纳入规则决定，未按效应结果扩样。')
rows=[]
for code,label,col in [('E11','发现：仅见建议',BLUE),('E12','复核：仅见建议',ORANGE),('E11','发现：条件效应差',BLUE),('E12','复核：条件效应差',ORANGE)]:
 key='advice' if '建议' in label else 'interaction';p=S[code]['primary'][key];lo,hi=p['descriptive_item_bootstrap_95pct'];rows.append((label,100*p['mean_p_B_shift'],100*lo,100*hi,col))
story.append(forest(rows,0,32,[0,10,20,30],'P(B) 变化或变化差（百分点）',200))
caption(4,'横轴为概率移动或交互，纵轴为批次与指标。蓝色发现批 16 题，橙色复核批 15 题；点为估计，横线为各批分别计算的题级 95% 区间。未合并两批。','复核仅建议 +22.48 pp [17.38,27.90]；交互 +22.48 pp [17.46,27.27]，满足预先规定的方向复核。')
para('完整证据效应 +0.000176 pp，区间 [+0.000021,+0.000441] pp；虽略高于零，量级极小。15/15 题仅建议效应与交互都为正；选择 B 比例增加 30 pp。','可以陈述新实例方向复现；不能将极小 full 数值表述为实际重要效应，也不能认为效应大小已稳定。')

page('21｜真实案例：同一题只换分数，具体发生什么','来源：两需求批次 demand-00，预先按题号与接收者记录顺序取首例，未按效应大小挑选。')
h2('发现批次：成员 2')
para('原始 18 条信号中 12 high、6 low，实际状态 high；成员 2 自己见 high,low,high，初答 B，p_B=.6。交换对象为支持 A 的成员 4 与支持 B 的成员 3。在 full 两条件都约为 .919294；advice 下 A_high 两次均为 .835052，B_high 两次为 .962446/.962400。','该例概率向获得高分的 B 方移动，但四次 advice 都仍选择 B。')
h2('复核批次：成员 3')
para('新 demand-00 与旧同名槽位不是同一题：18 条中 6 high、12 low，实际状态 low；成员 3 自己见 low,high,low，初答 A，p_B=.4。交换支持 A 的成员 4 与支持 B 的成员 1。完整后验为 64/793≈.080706。','两批实例的信号与初答不同，不能用同名 ID 当作同题纵向比较。')
case_values={}
for code in ('E11','E12'):
 name=next(n for c,n,_ in RUNS if c==code);roots=read(f'runs/{name}/roots.json');updates=read(f'runs/{name}/updates.json');target=roots['demand-00']['targets'][0]
 case_values[code]={f'{v}/{a}':mean(r['parsed']['p_B'] for r in updates if r['item_id']=='demand-00' and r['member']==target and r['visibility']==v and r['arm']==a) for v in ('full','advice') for a in ('A_high','B_high')}
story.append(bars(['发现/full','发现/advice','复核/full','复核/advice'],[
 ('A 方高分',[100*case_values[c][f'{v}/A_high'] for c in ('E11','E12') for v in ('full','advice')],BLUE),
 ('B 方高分',[100*case_values[c][f'{v}/B_high'] for c in ('E11','E12') for v in ('full','advice')],ORANGE)],'接收者报告 P(B)（%）',100,215))
caption(5,'横轴为两个真实例子的可见性条件，纵轴为 P(B)×100；蓝/橙分别为 A/B 获高分。柱高为同一接收者两次响应均值，无误差条；这些案例不代替整批估计。','复核 advice 从 .037553 升至 .164948，增加 12.74 pp，但仍选择 A；full 保持约 .080706。')
para('复核案例的模型理由把交换后的分数解释为总计 5 high/13 low 或 7 high/11 low，而实际为 6 high/12 low。这是可观察到的文字解释；不保证忠实反映内部推理。','分数可能被用作未见证据强度的线索，这一机制解释仍需专门实验验证。')

page('22｜需求预测：逐题效应与重复波动')
para('为检查平均效应是否只由少数题推动，图 6 展示全部已纳入题的 advice 配对效应，不按效应排序；两批分别展示。','逐题图用于透明呈现异质性，不能把每题四个配对当作稳定单题估计。')
d=Drawing(W,265);left,right,bottom,top=45,W-15,43,235
xx=lambda q:left+q/15*(right-left); yy=lambda val:bottom+(val+10)/65*(top-bottom)
for val in (-10,0,10,20,30,40,50):
 d.add(Line(left,yy(val),right,yy(val),strokeColor=GRAY if val==0 else colors.HexColor('#DCE4EA'),strokeWidth=.7 if val==0 else .4));textshape(d,left-7,yy(val)-3,str(val),8,anchor='end')
for code,label,color,offset in [('E11','发现（16 题）',BLUE,-2),('E12','复核（15 题）',ORANGE,2)]:
 for row in S[code]['item_effects']:
  q=int(row['item_id'].split('-')[-1]);value=100*row['advice']['p_B_shift'];d.add(Circle(xx(q)+offset,yy(value),3,fillColor=color,strokeColor=color))
for q in range(16):textshape(d,xx(q),bottom-15,f'{q:02d}',7.5,anchor='middle')
textshape(d,left,top+15,'仅见建议的题内 P(B) 变化（百分点）',9)
textshape(d,W/2,6,'题目槽位编号（两批同号不代表同一题）',9,anchor='middle')
textshape(d,right-175,top+15,'蓝：发现；橙：复核',8)
story.append(d)
caption(6,'横轴为 demand-00 至 demand-15 槽位；纵轴为该题 B_high-A_high 的 P(B) 变化（pp）。每点先平均两接收者与两重复，无逐题区间；点略错开以免重叠。复核排除的一致意见题没有点，不补零。','发现批 15/16 正向，复核 15/15 正向；现有正向结果不只来自单一极端题。')
table(['相同输入两次回答平均绝对差','发现批（pp）','复核批（pp）'],[['full','0.1465','0.1205'],['advice','3.8901','4.5977']],[275,(W-275)/2,(W-275)/2])
para('重复波动的计算覆盖四个分数条件，不等于主配对差的标准误。题间效应大小仍有差异；样本小、实例结构有限，不能据正向比例推断其他任务的效应分布。','可以确认当前两批中局部方向较一致，尚未估计跨任务机制的普遍性。')

page('23｜概率移动是否改善结果：次要质量指标','来源：E11/E12 summary.cells；下表每格发现 64 响应，复核 60 响应。')
para('概率向高分建议移动与预测变好是两件需要分别测量的事。以下用实际需求状态计算 Brier；同时报告复核批距完整后验的 MSE 和分类准确率。','评价质量应使用正确标签和适当信息基准，不能只看响应方向。')
quality_rows=[]
for v in ('full','advice'):
 for arm,lab in [('A_high','A 高分'),('B_high','B 高分'),('pair_equal','两人等分'),('hidden','隐藏')]:
  c=S['E12']['cells'][f'{v}/{arm}'];old=S['E11']['cells'][f'{v}/{arm}']
  quality_rows.append([f'{v}/{lab}',f"{old['Brier_realized_state']:.5f}",f"{c['Brier_realized_state']:.5f}",f"{c['MSE_full_information_posterior']:.3g}",f"{100*c['accuracy_realized_state']:.1f}%"])
table(['条件','发现 Brier','复核 Brier','复核后验 MSE','复核准确率'],quality_rows,[115,95,95,105,W-410])
para('复核中 advice 的 B_high Brier 为 .11852、A_high 为 .18073；发现批则分别 .07214/.06540，排序不同。分配按 A/B 而非实际正确性，有限题库的实际状态也会影响分数。以上是次要描述，没有预定的多重比较校正。','不能由这张表建立“给 B 高分改善预测”或“confidence 总体有害”的普遍结论。')
para('full 有实际全部信号，其后验 MSE 可衡量与精确概率的偏离；advice 缺少原始信号，距 full 后验的差异还含信息缺失，不能全部归为推理错误。Brier 对实际状态评价：合理的 .9 概率预测仍可能遇到低概率反例。','准确率、概率合理性与信息条件需结合解读。')

page('24｜事后条件模型：解释线索及其限制','来源：E11 posthoc_conditional_model.json 与 scripts/explain_signal_visibility.py。')
h2('目的、时点与假设')
para('在发现批运行中、已看过首个完成题之后，加入一个条件概率解释：假设接收者把显示分数视为校准的私人后验，并假设私人证据在给定需求时独立。该解释为事后分析，没有升级为 E12 的主要检验。','解释模型的提出时点晚于部分结果，不能称为预先成功预测。')
h2('计算与简单例子')
para('以目标自己三条信号的赔率 O_self 为起点。每名支持 B 的同伴贡献赔率 c/(1-c)，支持 A 的同伴贡献 (1-c)/c；相乘后令 p=O/(1+O)。full 直接使用全部信号的精确后验；隐藏分数时用多数策略准确率 .648。','这些公式描述“把报告当成可靠后验”的接收规则，不是真实干预机制下的规范后验。')
para('说明性例子：一名 B 同伴 c=.6、一名 A 同伴 c=.771429，其合并赔率因子约为 1.5/3.375；交换后约为 3.375/1.5。即使双方各一票，估计仍会改变。','数值分数可编码隐含证据强度；票数保持不变并不意味着条件模型概率保持不变。')
table(['发现批次的解释性结果','数值'],[['条件模型预测的 advice 平均效应','+16.34 pp'],['真实模型 advice 平均效应','+14.81 pp'],['条件模型与输出 p_B 平均绝对差：full','0.000733（0.0733 pp）'],['条件模型与输出 p_B 平均绝对差：advice','0.019630（1.9630 pp）']],[345,W-345])
para('显示分数已被实验者改写；若接收者知道这一改写机制，就不能再把分数简单当作真实后验。输出接近某个公式也不识别唯一内部机制。','当前只能把这一模型作为可检验的解释线索，不能据此确认贝叶斯推理或人类式信任机制。')

page('25｜跨实验结论：已经支持与仍未验证')
table(['问题','目前证据','可得结论'],[
 ['题目难度是否已稳定？','自然 L2 95%；平衡 L2 80.9%，且两类差异明显','依赖实例分布与配置；生成等级不等于实测难度。'],
 ['逻辑题中错误高分是否增加错误？','四条件区间跨零；负分差趋势在新题未明确复现','没有稳定方向证据，不证明所有场景都无效。'],
 ['真实初答后能否识别局部影响？','供应商完整披露后近全对；需求 advice 出现复核支持','信息结构是必须明确控制的实验条件。'],
 ['完整证据会怎样？','需求 full 平均效应很小；供应商局部差为零','当前可核验任务对分数的额外响应有限；不作等价性声明。'],
 ['局部能否预测群体？','已实现供应商训练/测试管线，但无有辨识力非零效应','核心群体预测目标仍未得到验证。'],
 ['是否为 subagent 信任研究？','无主从层级，无工具任务委派；真实群体为平级成员','当前结论针对平级建议输入及局部/同步更新。'],
 ],[100,200,W-300])
para('两轮需求任务一致支持：“在这个生成机制与提示中，证据不可直接核验时，显示分数的归属对自报概率影响更大。”不同可见性条件对同题共享初答和其他输入，因此该局部比较控制较清楚。','这是目前最有支撑的行为结论，范围仅为单模型、有限任务机制、局部更新。')
para('尚未验证：跨模型、真实工具结果、行为经济学/社会学的外部有效性、自然语言理由传播、不同图结构、多轮非零影响的预测，以及显示分数是否被合理利用。对这些问题不能从当前结果外推。','下一步宜分别检验机制与群体迁移；本报告不启动任何新调用。')

page('附录 A｜真实逻辑案例的完整前提与核验')
para('E04 的 v4：X1-X7 为布尔变量；下面 28 个括号必须同时成立。问是否必然推出 X1。A=不蕴含，B=蕴含；NOT 表示非，OR 表示或。','这是实际题目，足以独立重建穷举求解，不是缩写后的说明性题。')
task=next(t for t in M['E04']['tasks'] if t['id'].endswith('-v4'))
def lit(x):return ('NOT ' if x<0 else '')+'X'+str(abs(x))
clauses=['('+' OR '.join(lit(x) for x in c)+')' for c in task['problem']['clauses']]
table(['编号','前提','编号','前提'],[[f'{i+1:02d}',clauses[i],f'{i+15:02d}',clauses[i+14]] for i in range(14)],[35,(W-70)/2,35,(W-70)/2],8)
para('枚举 2^7=128 个赋值，筛出同时满足全部子句的赋值；若其中存在 X1=0，就不蕴含 X1。共有 6 个满足赋值，反例 (0,0,1,0,1,0,1) 满足全部 28 个子句。实际回答序列 A,A,A,B,A,A，唯一错误报告 p_B=.99。','反例确立题目真值；模型理由是否流畅或自报概率多高都不会改变精确真值。')

page('附录 B｜模型设置、提示差异与停止规则')
table(['阶段','模型/输出设置','状态与信息'],[
 ['E01-E05','Luna；2048 token；默认推理；无 strict schema','独立校准或小测；响应非法单列'],
 ['E06','Luna；8192；medium；strict JSON','初答 answer/p_B/reason'],
 ['E07-E09','同上；更新只输出 answer','自身和同伴意见预设；E08 起统一定义 confidence'],
 ['E10','同上；严格 A/B 更新','真实私人初答；完整审计证据；次轮隐藏分数'],
 ['E11-E12','同上；每次输出 answer/p_B/reason','真实调查初答；full/advice 对照；两次重复'],
 ],[75,220,W-295])
para('所有完成的真实运行使用 API ID openai/gpt-5.6-luna；运行前保留目录快照，记录返回模型与供应商。相同 ID 不保证供应商底层版本永久不变。未设置可配对的 API 采样种子；本地 seed 控制题库和请求设计。','输入控制可审计，底层服务的完全时间稳定性不能保证。')
para('E01 的早期更新非法时保留旧答案并记失败；E07-E09 缺失保留、不重发，主分析用完整配对，另给界限；E10 若群体首轮缺失则跳过该条件次轮；E11/E12 按完整主配对题统计。每个协议的缺失规则应单独使用。','跨协议比较前必须区分缺失规则，不能静默用统一填补覆盖旧统计。')
para('运行前冻结 manifest、任务、配置与源码 hash；完成响应按 call_id 复用，pending/unresolved 不自动重发。实验目录分开，模型从显式消息获取状态，不共享对话内存。凭据不写入报告或实验文件。','断点续跑不创造新样本；请求来源与条件可逐条追溯。')

page('附录 C｜请求、费用与缓存重新审计')
table(['实验','请求记录','有效响应','已知费用 USD','未知费用数'],[[x['code'],x['requests'],x['valid'],f"{x['known_cost_usd']:.6f}",x['unknown_cost_requests']] for x in inventory]+[['合计',total_calls,total_valid,f'{total_cost:.6f}',total_unknown]],[65,95,95,150,W-405])
known_cache=sum(x['cache_known'] for x in inventory);unknown_cache=sum(x['cache_unknown'] for x in inventory);hits=sum(x['cache_hits'] for x in inventory);cached_tokens=sum(x['cached_tokens'] for x in inventory)
para(f'缓存审计覆盖上表全部原始记录：{known_cache} 条有 cached_tokens 字段，{hits} 条记录命中、累计 {cached_tokens} 个缓存 token；{unknown_cache} 条缓存字段/响应缺失，记为未知。这个统计重新纳入了供应商与两批需求实验。','供应商提示缓存依据接口返回字段统计；缺失字段不能当作零命中。')
para('说明性例子：同一条件重复两次应有两个不同 call_id，并各自返回响应；断点续跑再次遇到已经完成的同一 call_id，只读取旧记录。远端提示缓存即便命中也只是复用输入计算，不等于复制输出。','本地结果复用与远端提示缓存必须区分，缓存命中不自动损害重复采样独立性。')
para('已知费用求和来自 usage.cost，未完整返回请求的实际账单可能另有费用。账户失败目录两条无有效结果记录不计入上表；mock 目录均排除。','费用是记录范围内的已知 API 成本，不是保证完整的最终账单。')

page('附录 D｜逐批来源索引与复现入口')
para('下列路径相对项目根目录 confidence_agents。编号与正文一致；每个目录保留 manifest.json、summary.json 和原始 calls（可能在 items 子目录）。目录后缀数字是 seed/命名标签。','数据定位以目录和文件内容为准，不能从名称推断日历运行顺序。',style='small')
table(['编号','运行目录（runs/ 下）','本地首请求时间（UTC+8）'],[[x['code'],x['directory'],x['started_local'][:19].replace('T',' ')] for x in inventory],[40,320,W-360],7.7)
para('需求实验独立审计：scripts/audit_signal_visibility.py；复核比较：scripts/compare_visibility_replication.py；供应商审计：scripts/audit_supplier_transfer.py。它们读取已有记录，不产生模型调用。','可从原始响应重算主效应，并核对请求不变项与冻结源码。')
para('报告生成：python -s scripts/build_experiment_report.py。产物包括本 PDF、可编辑正文 Markdown、抽取指标与来源 SHA-256 清单。E11/E12 独立审计与 E10 已保存审计为关键证据，报告不依赖模型自行回忆过去结果。','本报告可以离线重建，并定位每项主要结论的数据来源。')

page('附录 E｜模拟测试、失败启动与未完成目标')
h2('非实证运行记录')
mock_dirs=sorted(p.name for p in (ROOT/'runs').iterdir() if p.is_dir() and 'mock' in p.name)
table(['类别','目录 / 状态'],[['模拟管线测试','\n'.join(mock_dirs)],['失败账户启动','live-luna-smoke-20260918\nlive-luna-smoke-20260918-new-account\n每目录一条失败记录，无有效行为结果'],['离线分析','item-diagnostics；CACHE_REPORT；posthoc_conditional_model；独立审计与报告脚本']], [115,W-115],8.5)
para('模拟输出由程序提供，用于验证调用预算、断点续跑、分组和统计逻辑。失败启动只反映当时接口或账户不可用，不是模型表现。','这两类记录都不用于支持 confidence 行为结论。')
h2('相对 proposal 的覆盖与空缺')
para('proposal 计划包括固定消息局部响应、持续分数的群体动态、自然语言脉冲与独立自审对照，以及跨图结构的局部到群体预测。当前已做局部干预、小规模同步讨论和供应商预测流程；需求任务新增了明确的证据可见性比较。','实施协议的调整已逐批记录，不能将 proposal 全部目标视为已经完成。')
para('尚未完成真实 subagent 委派、多模型比较、自然语言理由的多轮传播、图结构迁移，以及具有非零局部效应的独立群体预测验证。逻辑题与需求任务的效应终点不同，不能合成一个“总体 confidence 效应”。','当前最可靠的贡献是信息边界清楚的局部行为证据，群体预测仍是下一阶段目标。')

class ReportDoc(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=='h1':
            title=flowable.getPlainText();key='section_'+str(len(self.section_pages))
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0,False)
            self.section_pages.append({'title':title,'page':self.page})

def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#D5DEE5'));canvas.line(44,43,A4[0]-44,43)
    canvas.setFont('CN',8);canvas.setFillColor(GRAY);canvas.drawString(44,29,'CONFIDENCE AGENTS  /  阶段实验记录与独立复核')
    canvas.drawRightString(A4[0]-44,29,str(doc.page));canvas.restoreState()

sources=[]
for code,name,_ in RUNS:
    for filename in ('manifest.json','summary.json','REPORT.md','RESULTS_ZH.md','independent_audit.json','PROTOCOL.md'):
        p=ROOT/'runs'/name/filename
        if p.exists():sources.append({'experiment':code,'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
for p in [ROOT/'Proposal/main.pdf',ROOT/'runs/item-diagnostics/REPORT.md',ROOT/'runs/signal-visibility-luna-20260919/posthoc_conditional_model.json',ROOT/'runs/signal-visibility-replication-20260920/REPLICATION_PLAN.md']:
    sources.append({'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
out=OUT/'confidence_agents_experiment_report_zh.pdf'
doc=ReportDoc(str(out),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=43,bottomMargin=56,
    title='Confidence Agents 阶段实验报告',author='Confidence Agents Research',pageCompression=1)
doc.section_pages=[]
doc.build(story,onFirstPage=footer,onLaterPages=footer)
(OUT/'confidence_agents_experiment_report_zh.md').write_text('\n\n'.join(readable)+'\n',encoding='utf-8')
(OUT/'report_evidence.json').write_text(json.dumps({'inventory':inventory,'sources':sources,'case_values':case_values,'sections':doc.section_pages},ensure_ascii=False,indent=2),encoding='utf-8')
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'pdf':str(out),'planned_sections':len(headings),'section_pages':doc.section_pages,'requests':total_calls,'valid':total_valid,'known_cost':total_cost,'cache_known':known_cache,'cache_hits':hits,'cache_tokens':cached_tokens,'cache_unknown':unknown_cache},ensure_ascii=False,indent=2))
