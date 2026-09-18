"""Integrate the original proposal and saved pilot evidence. No model calls.

Builds a self-contained Chinese HTML, a matching paginated PDF, and vector figures.
The original stays unchanged in the repository; superseded material is not appended.
"""
import hashlib
import html
import io
import json
import math
import re
import runpy
from pathlib import Path
from html.parser import HTMLParser
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, KeepTogether)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, Line, Circle, String
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Proposal/integrated'
OUT.mkdir(parents=True, exist_ok=True)
FIG = OUT / 'figures'
FIG.mkdir(exist_ok=True)
original = ROOT / 'Proposal/main.pdf'
original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
runpy.run_path(str(ROOT / 'scripts/build_narrative_report_html.py'))
report = (ROOT / 'output/html/confidence_agents_experiment_report_zh.html').read_text(encoding='utf-8')
saved = {m.group(1):m.group(0) for m in re.finditer(r'<section id="([^"]+)">.*?</section>',report,re.S)}
H = html.escape

def p(s): return '<p>'+H(s)+'</p>'
def h(s): return '<h3>'+H(s)+'</h3>'
def note(s): return '<div class="conclusion"><strong>当前结论</strong>'+p(s)+'</div>'
def ex(title,s): return '<div class="example"><strong>'+H(title)+'</strong>'+p(s)+'</div>'
def code(s):return '<pre><code>'+H(s)+'</code></pre>'
def tbl(head,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+H(x)+'</th>' for x in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+H(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def sec(id,title,lead,body):
    return f'<section id="{id}"><h2>{H(title)}</h2><p class="lead">{H(lead)}</p>{body}</section>'

# SVGs use only simple vector elements; the same elements are used for the PDF.
class Diagram:
    def __init__(self,height,title):
        self.height=height
        self.bits=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {height}" role="img" aria-label="{H(title)}">']
    def text(self,x,y,s,size=16,color='#243441',anchor='middle'):
        self.bits.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{H(s)}</text>')
    def box(self,x,y,w,hh,lines,color='#edf5f7'):
        self.bits.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="7" fill="{color}" stroke="#a9bec7"/>')
        first=y+hh/2-(len(lines)-1)*12+5
        for i,s in enumerate(lines):self.text(x+w/2,first+i*24,s)
    def arrow(self,x1,y1,x2,y2,color='#648794'):
        self.bits.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"/>')
        ang=math.atan2(y2-y1,x2-x1)
        for da in [-.5,.5]:
            xx=x2-9*math.cos(ang+da); yy=y2-9*math.sin(ang+da)
            self.bits.append(f'<line x1="{xx}" y1="{yy}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2"/>')
    def end(self):return ''.join(self.bits)+'</svg>'
def fig(svg,caption):return '<figure>'+svg+'<figcaption>'+H(caption)+'</figcaption></figure>'

d=Diagram(395,'同一市场、六份私人资料和六个真实初答')
d.box(215,12,330,64,['程序生成同一个市场','实际需求只由实验者保存'])
for j,signals in enumerate(['低、低、高','低、高、高','低、高、低','低、高、低','高、低、低','低、低、低']):
    x=16+j*124
    d.arrow(380,76,x+54,125)
    d.box(x,126,108,108,[f'成员 {j}',signals,'独立作答'])
    d.arrow(x+54,234,x+54,265)
    d.box(x,266,108,60,[['A · 40%','B · 60%','A · 40%','A · 40%','A · 40%','A · 22.86%'][j]],'#fbf3e7')
d.text(380,363,'下排百分数统一表示 P(高需求)，不表示对所选答案的把握。',15)
worldfig=fig(d.end(),'图 1｜一题如何产生六个初答。上方是同一个市场，中间六个框是各成员自己的三份调查，下方是复核题 demand-00 的真实初答。箭头表示资料分配与独立作答的顺序；成员之间此时尚未交流。本图是信息流程示意，没有数值坐标轴、误差条或样本分布。')

d=Diagram(360,'同一个初始状态分成四个主要比较分支')
d.box(210,10,340,64,['保存同一组六人初答','调查、身份、答案、顺序固定'])
for x,name in [(35,'完整证据：能看同伴调查'),(405,'只看建议：隐藏同伴调查')]:
    d.arrow(380,74,x+160,120)
    d.box(x,120,320,50,[name])
    for xx,label in [(x,'A 方拿高分'),(x+170,'B 方拿高分')]:
        d.arrow(x+160,170,xx+75,215)
        d.box(xx,215,150,66,[label,'各调用两次'],'#fbf3e7')
d.text(380,322,'同一行左右相减：只测高分归属的作用。',16)
d.text(380,348,'再比较两边的差值：检查原始证据是否改变这种作用。',16)
branchfig=fig(d.end(),'图 2｜当前局部实验的四个主要分支。所有分支从同一初始状态重新开始，箭头不表示模型依次经历四种条件。图中省略了等分与隐藏分数两个辅助条件；两个接收者分别接受同样的设计。框的位置区分条件，没有数值坐标轴。')

d=Diagram(335,'下一阶段的局部拟合和事先群体预测')
d.box(20,20,210,90,['训练题：单步更新','输入 → 实际输出','拟合反应规律'])
d.arrow(230,65,285,65)
d.box(285,20,205,90,['验证题：选预测器','确定参数和设置','之后冻结'])
d.arrow(490,65,545,65)
d.box(545,20,195,90,['新测试题','只读初始六人状态','先保存未来预测'])
d.arrow(645,110,645,177)
d.box(420,178,320,80,['再真正运行六人多轮讨论','收集实际轨迹'])
d.arrow(420,218,330,218)
d.box(25,178,305,80,['比较预测与实际结果','是否优于不看置信度的预测器？'],'#fbf3e7')
d.text(380,307,'本图为下一阶段计划；需求任务尚未完成这条完整流程。',16)
futurefig=fig(d.end(),'图 5｜如何检验局部影响能否预测群体。箭头表示研究步骤，测试题的未来回答要在预测保存以后才收集。测试时读取已经发生的下一轮消息再预测后续，只能算条件预测，不能算从初始状态出发的完整预测。本图为计划示意，没有实验数值。')

d=Diagram(355,'一次显示分数后比较继续交流与独立复核')
d.box(200,10,360,64,['同一个初始状态','先按不同归属显示一次分数'])
d.arrow(380,74,380,118)
d.box(195,118,370,60,['获得第一次更新后的状态','每个分数分支各自复制成两份'])
d.arrow(300,178,180,225);d.arrow(460,178,580,225)
d.box(25,225,310,82,['继续交流','以后只传最新答案和理由','程序不再添加分数'])
d.box(425,225,310,82,['独立复核','以后只看自己的最新回答','更新次数相同'],'#fbf3e7')
d.text(380,339,'比较：先前分数的影响是否保留？继续交流是否改变它？',15)
pulsefig=fig(d.end(),'图 6｜原 proposal 的一次性分数干预计划。每个高分归属条件内部，都在第一次更新后复制同一状态，再分成交流与独立复核。后续模型可能自行重复数值或措辞，需记录这种现象；程序意外保留旧消息则属于输入泄漏。该图为尚未在需求任务完成的设计，无数值坐标轴。')

introbody = h('用一句完整的话说明任务')+p('我们让六个语言模型分别查看同一个市场的一部分调查，先判断产品需求高还是低，再给其中的接收者看其他人的建议。我们保持调查、初始选择和成员身份不变，只交换两个人报告上的置信度数字，观察接收者怎样更新判断。最后希望检验：这种单步变化能否预测完整群体在多轮交流后的结果。')
introbody += h('这里的 multi-agent 到底是什么')+p('agent 在本研究中指一次具有指定身份和指定输入的模型参与者。六个成员使用同一个模型接口，编号为成员 0 至成员 5。程序分别发送六份请求，每份只包含这个成员应当知道的资料。模型之间不会自动互相读取回答；哪些消息转给谁，完全由程序安排。')
introbody += ex('读者可以直接理解的操作','第一次向模型提交：“你是成员 0，只看这三份调查，请回答。”再提交：“你是成员 1，只看另外三份调查，请回答。”依次获得六份初答。之后，程序把选定的五份同伴报告放入成员 3 的新请求，让成员 3 再判断一次。这里没有训练六个新模型，也没有一个主管给五个 subagent 派工作。')
introbody += p('独立请求表示输入与会话隔离，不保证六个模型拥有独立知识，也不保证错误彼此无关。同一个模型的六份初答可以相同；私人调查不同也可以自然产生分歧。')+worldfig
introbody += tbl(['研究中常用的词','本文中的具体意思'],[['题目 / 实例','一个程序生成的市场及其十八份调查。'],['初答 / 初始状态','六人各自只看私人调查后，保存下来的六份真实回答。'],['一次更新','一个成员收到指定同伴消息后，再输出一次答案和概率。'],['实验条件 / 分支','从同一初始状态开始的一种输入安排。'],['一轮群体讨论','六人都根据同一份上一轮状态回答；本轮全部完成后才传给下一轮。'],['重复调用','把同一种输入再调用一次，用于观察输出波动；不把前一次输出传回。'],['共识','六人选择相同。它只描述一致性；是否正确要另外评价。']])
introbody += note('当前需求实验完成的是六人初答与两名接收者的单步对照。完整群体多轮讨论是 proposal 的后续目标。下面先把题目与单步实验讲清楚，再介绍如何走向这个目标。')

bridge = h('当前问题怎样承接原 proposal')+p('原 proposal 的核心是“置信度分配与正确性是否一致”：同样的分数给初答正确者或错误者，会不会改变群体错误率。当前需求实验先把一个更基础的问题单独测出来：同样的分数给支持 A 的成员或支持 B 的成员，会不会改变下一次判断；这种改变是否取决于原始证据可见性。')
bridge += tbl(['要区分的对象','原 proposal 的计划','目前需求实验实际采用'],[['任务答案','通常使用外部可验证的唯一答案；后验比较题以较大后验的选项为准。','实际需求由程序生成；完整证据下的参考概率另算。合理概率预测仍可能遇到相反的实际结果。'],['交换依据','初答正确 / 错误。','支持 A / 支持 B，交换时不依赖真实需求。'],['主要观察','四轮后的错误成员比例差。','一次更新中报告 P(B) 的变化，以及两种信息条件下变化的差。'],['研究范围','从局部反应到群体预测与传播。','已完成局部反应与同机制新实例复核；后续群体环节待验证。']])
bridge += p('这种修改让当前实验更容易解释，但也限制了结论。把高分给 B 后 P(B) 上升，说明分数归属影响预测方向。要判断这种影响是否有害，还必须结合实际需求或明确的概率基准。实际需求为低并不意味着模型应该报告 P(B)=0；调查有噪声，合理预测允许不确定性。')
bridge += h('研究意义：需要解决什么，而非预设什么结论')+p('在多模型协作中，接收者往往看不到同伴的全部材料。分数可能成为判断同伴证据强度的线索。我们希望知道：这种线索何时改变行为，原始证据能否限制它的影响，以及能否用局部测量预测后续群体结果。这些答案可以帮助评价消息格式、证据共享和最终决策规则。')
bridge += p('现阶段的实践启示是一个待扩展的设计问题：当同伴附有置信度时，是否应同时提供可核验的证据？本实验支持在该合成任务中继续检验这一方向，尚未证明它能改善真实业务系统。研究也没有把模型当作人类参与者，因此不据此推出人的从众或信任规律。')
bridge += note('把“分数能影响判断”“影响使预测变差”“影响会在群体中传播”分成三个待检验命题，有助于避免把一个局部结果扩写成整个 proposal 已经成立。')

related = p('置信度、意见交流和群体预测已有前人研究。下面只介绍与本项目设计直接相关的联系，不把“模型会受同伴影响”作为新的发现。链接指向论文原始来源；正文所述联系是本项目的方法选择，不能视为这些论文已经验证了本项目结论。')
refs=[
 ('ReConcile（Chen 等，2024 版本）','https://arxiv.org/abs/2309.13007v3','把不同模型的答案、解释和置信度放入讨论，并使用置信度加权投票。','提示我们区分交流阶段的影响与最后投票规则的影响；本项目的计划保持最终投票规则不变。'),
 ('ConfMAD（Lin 与 Hooi，2025）','https://aclanthology.org/2025.findings-emnlp.343/','研究多 agent 辩论中的显式置信度表达。','当前局部实验冻结意见内容，进一步单独交换分数归属。'),
 ('HiddenBench（Li 等，v4）','https://arxiv.org/abs/2505.11556v4','用分散信息任务评估模型群体能否汇集不同成员掌握的材料。','借鉴私人信息分配，并设置完整证据与只看建议的对照；当前市场题是新构造任务。'),
 ('KAIROS（Song 等，v1）','https://arxiv.org/abs/2508.18321v1','在知识问答环境中研究历史互动、当前同伴回答与不同同伴可靠性。','帮助区分当前答案的置信度与来源的历史可靠性；本实验没有给成员添加专家身份或历史记录。'),
 ('Kumaran 等（2025）','https://arxiv.org/abs/2507.03120v1','研究初始承诺与外部建议怎样影响模型改变判断。','支持把自身前答是否可见列为明确控制项；当前每个分支都保留相同的自身前答。'),
 ('Physics of Agents（El 等，v2）','https://arxiv.org/abs/2608.16578v2','研究相互交流的模型群体，并用简洁模型预测其轨迹和群体行为。','原 proposal 希望进一步从受控局部干预出发，预先预测新题上的分数分配效应。'),
 ('Emergence of Biased Consensus（Okawa，v1）','https://arxiv.org/abs/2608.02827v1','研究多模型辩论中的群体偏差，并提出动力学分析框架。','提醒我们把个体准确性、交流影响与群体偏差分开测量。')]
for title,url,prior,ours in refs:
    related+=h(title)+p(prior)+p('本项目的联系：'+ours)+f'<p><a href="{url}">{H(title)}：原始论文来源</a></p>'
related+=note('本项目拟贡献的是一组相连的证据：受控地测分数归属，比较原始证据可见性，再检验局部规律能否提前预测群体结果。研究的新颖性仍需随完整实验与文献比较继续评估。')

future = p('以下为整合后的后续研究计划，没有在本次文档整理中新增 API 调用。当前已完成的两批需求实验用于说明可行性和选择设计，不能再当作从未见过的确认性测试集。')
future += h('实验一：补足局部反应，目的是建立可用于预测的规律')+p('继续保存题目和真实初答，分别改变可见同伴中谁拿到高分。覆盖不同初始 A/B 比例、不同自身选择和不同可见同伴数量。先拟合不含置信度的预测器，再加入置信度，检查新题预测是否改善。选择信息条件、分数范围、样本数和主要指标后，先保存计划再运行。')
future += p('先保留当前 60%/77.1429% 的分数范围，以便局部结果与后续实验可比较。若研究其他分数，再单独列为扩展，不把多个协议的数据混成同一种效应。收集用于群体预测的局部数据时，还需要覆盖多轮交流可能遇到的输入，而不只覆盖第一次初答。')
future += h('实验二：让六个人真正讨论，目的是检验群体预测')+futurefig
future += p('首先把新题划为训练、验证和测试三部分。同一道题的改写、数字变体或选项翻转必须留在同一部分。训练题用于估计预测器参数；验证题用于选择设置；测试题只用于最终评价。题数根据期望精度和预算在测试前固定，不沿用尚未论证的旧样本配置。当前两批数据已用于选择设计，后续不能再把它们当作未查看过的测试集。')
future += ex('说明性例子：怎样才算“提前预测”','看到某道新题六人的初答后，先保存：“在 B 方高分条件下，第四轮选 B 的人数预计更多；达到 B 多数的概率为某个预测值。”随后才真正运行四轮并比较。若先看了实际第四轮再调参数，就只能叫拟合，不能叫这道题的事先预测。这里没有填写示意预测数值，以免与实测结果混淆。')
future += p('第一步先把当前的单次干预扩大到六名成员，保存全体第一次更新后的状态。被交换分数的两位成员由于不看自己的分数，各自可见的分数集合可能改变；因此，六人的整体差异应称为整个分配方案的影响，不能全部解释成可见集合严格不变的局部效应。当前两名接收者的严格局部比较仍应单独报告。')
future += p('随后采用下面的一次性分数干预与撤除设计，检查变化是否能够继续传播。每轮六人都读取同一份上一轮状态，全部完成后才进入下一轮，避免请求完成顺序改变输入。更新轮数和主要评价时点在运行前固定；这里不把“显示一次”与“每轮都显示”混在一起。')
future += p('在这份修订计划中，每次请求都明确列出原始私人调查、最近自己的回答，以及协议允许看见的最近同伴消息。预测器也必须使用相同的信息定义。若最近自己的回答中保留连续概率，或同伴消息中保留理由，就不能仅凭六人的 A/B 组合预测所有后续变化。可以先做只传答案的简化版本，再把加入理由列为单独实验；两者不能共用未经检验的状态假设。')
future += p('群体终点沿用固定的不加权多数规则：六人中至少四人选择某项，才构成该项的多数；三比三单独记为平局。不能在高分条件下改为按置信度加权投票，否则最后结果变化还混入投票规则变化。六人全部一致叫共识；共识是否正确另行计算。')
future += h('实验三：只显示一次分数，目的是检验影响能否保留和传播')+pulsefig
future += p('这一实验允许传递新生成的简短理由，使交流更接近普通 agent 对话。第一轮干预后，后续消息自然不同是待研究的结果。程序必须删除最初的分数覆盖层与原始历史，再检查差异能否通过新答案或新理由延续。与独立复核比较，可以进一步问：持续与同伴交流是否改变了先前分数的影响。')
future += p('可选扩展是只让一位成员看到带分数的固定来源，其他五人从未直接见到该来源，再测其他五人的变化。来源不参加最终投票。这样才有条件研究间接传播；全体同时看到分数，只能测共同暴露后的结果。')
future += h('如何判断后续实验成功或失败')+tbl(['问题','支持性证据','结果不足时应怎样写'],[['局部规律有预测价值吗？','在新测试题上，含分数预测器优于使用相同其他信息的无分数预测器。','分数改变输出，但简洁预测器未达到基线。'],['能预测完整群体吗？','从初始状态出发，不读取未来消息，预测多轮轨迹和终点；误差低于基线。','单步预测成立，完整轨迹预测结论待定。'],['一次干预会留下后续差异吗？','删除原始分数后，后续输入仍通过生成状态携带差异，且群体结果存在配对差。','仅观察到第一次更新效应。'],['有间接传播吗？','未直接接触来源的成员在有路由路径时产生差异，并通过输入日志排除泄漏。','共同暴露或随机波动不足以证明间接传播。']])
future += note('下一阶段重点是事先预测与独立测试。更大的局部概率差本身不完成群体目标；预测器无法超越基线也是需要如实报告的结果。')

model = h('预测器在做什么')+p('实验中的语言模型负责实际回答；研究者另拟合一个小型统计预测器，用已有输入估计下一次输出。预测器不需要再调用大模型。它只描述可观察行为，不能被解释成大模型内部的真实计算过程。')
model += h('先分清两种容易混淆的概率')+p('语言模型报告 P(B)=40%，指这条回答表达“实际需求高”的概率。研究者预测“下一次回答选择 B 的概率为 40%”，指重复运行同样输入时，有多少响应会选 B。这是两个不同的预测目标。当前主结果测前者，因此后续首先应预测模型报告的 P(B)，同时把是否选 B 作为另一个指标。')
model += ex('真实案例对预测设计的启发','成员 3 的 P(B) 从 3.76% 变到 16.49%，两边都选 A。一个只预测 A/B 的方法可能把这两次输出当作相同。要预测我们已经观察到的变化，就要保留连续概率，而不只保留选项。')
model += tbl(['比较方法','使用什么输入','为什么需要它'],[['自身信息基线','私人调查、自己的初答与概率、是否可见同伴调查。','检查新增同伴信息是否提供预测价值。'],['无分数同伴基线','加入同伴初答数量；完整证据时加入同伴调查；不使用置信度字段。','表示已知道同伴意见，但不知道分数归属时能预测到什么程度。'],['含分数预测器','与无分数基线使用相同输入，再加入分数与 A/B 立场的关系。','只有它在新题上更准确，才能说置信度为预测提供额外信息。']])
model += p('一种透明的分数特征是：把可见 B 建议的显示分数相加，再减去可见 A 建议的显示分数之和。该特征只是候选输入，不是已确认的更新公式；它也可能受意见数量影响，因此无分数基线要同时保留 A/B 数量。具体回归形式和正则化只在训练、验证题上选择，不能查看测试结果后再挑选。')
model += h('怎样评价一次更新预测')+p('先预测该输入下模型报告 P(B) 的平均值，使用新题上预测值与实际报告值的均方误差。再单独预测下一次是否选 B，用二元概率评分评价。两个方法的误差差值都先在同题内部平均，再按题比较。仅在训练题拟合更好不够；加入分数后参数不为零，也不代表测试误差一定改善。')
model += h('怎样继续预测多轮')+p('预测器从同一个初始状态出发，用自己预测的下一轮状态继续往前计算。不能把实际未来回答偷偷放回输入。如果要预测群体投票与轨迹波动，只预测每人平均 P(B) 还不够，因为“平均值超过 50%”与“多少次响应超过 50%”并不相同；需要估计响应分布，或另建并验证选项转移模型。')
model += p('需要把私人调查、自己的最新概率、可见同伴消息等真正保留的字段纳入状态。如果允许自由生成理由，完整预测更困难：未来理由本身未知。可以先评价单步预测，再检验简化状态的多轮预测是否仍有效；失败时收窄结论，不能把读取实际消息后的预测叫作从初始状态出发的预测。')
model += p('供应商实验已实现过一次局部拟合到群体预测流程，但加入分数没有改善测试预测。需求任务的新预测器尚未拟合。原稿中固定的影响权重公式、只依赖六个答案的状态模型和相关理论推导不再作为当前主方案的前提。')
model += note('当前可验证的预测目标是：在相同测试题上，知道分数归属能否更准确地预测下一次输出。只有这一步成立，并通过额外的状态和分布检查，才进入完整群体轨迹预测。')

rigor = h('当前实验实际用了哪些设置')+tbl(['项目','已完成的需求实验'],[['模型','保存的请求 ID 为 openai/gpt-5.6-luna；六名成员同一模型。未完成 GLM/Qwen 实证对照。'],['生成设置','medium reasoning；最大输出 8192 token；严格 JSON；保存 answer、p_B、reason。未额外覆盖温度或 API seed。'],['题目与种子','发现批任务种子 20260919，复核批 20260920；分配、顺序与 bootstrap 种子保留 20260919。日期样式数字不等于运行日历日期。'],['请求安排','四个题目并发；题内各条件与重复预先打乱；同一初始状态反复使用。'],['失败','初答不完整则该题不进入干预；更新失败记缺失，不按效果好坏重发。两批需求调用均有效。'],['费用','发现批已知费用约 $0.527820；复核批约 $0.467750，来自运行账单字段，非未来价格报价。']])
rigor += h('如何把“只换两个数字”变成可检查的事实')+p('程序保存实际发出的完整输入，再检查配对请求：模型 ID、任务、自己的调查与前答、同伴身份、建议和顺序一致；A 高分与 B 高分只交换两个 confidence 字段。完整证据与只看建议只相差同伴 surveys 字段。原始理由不传播给同伴，避免理由泄漏调查数量。还检查真实市场状态没有进入模型输入。')
rigor += p('同一输入重复采样时仍应真实调用，不能用本地答案缓存把第二次回答直接复制出来。保存初答以便各分支共享，与供应商提示缓存计费是两件不同的事。12 批实验中，4861 条响应有缓存字段且记录的缓存 token 均为零，15 条状态未知。')
rigor += h('评价质量时，具体计算什么')+tbl(['指标','计算方法与读法'],[['Brier 分数','对单个预测取 (p_B − y)²，其中实际高需求 y=1、低需求 y=0；再对预先规定样本平均，越低越好。例如 p_B=0.4、实际低，则该次为 0.16。'],['完整信息概率误差','取 (p_B − p_full)²，再平均；p_full 由十八份调查计算。只看建议条件下，这个差还包含缺失信息，不能全部称为推理错误。'],['选项正确率','实际高时选 B、实际低时选 A，记 1，否则记 0，再平均。合理预测在有噪声的单题上也可能判断错实际状态。'],['同输入波动','相同输入两次 p_B 的绝对差，再平均。这是重复波动描述，不是均值标准误。'],['后续群体错误比例','一轮中与指定真值不同的人数除以 6；将来用同题不同分数分支的差评价干预。'],['后续群体预测误差','比较事先预测与实际轨迹；多数事件用概率评分，逐轮错误比例可用均方根误差。比较方法必须使用相同测试题。']])
rigor += h('样本数、统计区间和停止规则')+p('当前每批只有约十六个独立市场。重抽样时以市场题为单位，同时带走该题所有条件、接收者和重复；不能把每次 API 响应当作一个独立市场。当前区间属于小样本描述，主要支持同任务机制、同模型的复核方向。后续应根据希望区分的最小效应与题间波动，在测试前固定样本数。')
rigor += p('原 proposal 给出的粗略样本规划是 Q≈(1.96+0.84)²×s_D²/δ²，其中 s_D 是题级配对差的标准差，δ 是希望检测的差。例如 s_D=0.20、δ=0.05，约需 126 道合格独立题。这是正态近似下的规划例子；不构成当前样本的功效结论。重复同一题无法替代增加独立题。')
rigor += h('运行规模与下一步交付')+p('当前两批局部需求实验分别使用 608 和 576 次调用。后续群体运行要另算每题初答、每个条件的六人更新、轮数与重复次数。先用现有 token 记录估算，运行前固定预算上限与停止规则，再扩大规模；不因看到显著或不显著结果临时加题。')
rigor += p('交付顺序为：冻结新协议与数据划分；保存训练结果和验证选择；对新题提前保存群体预测；收集群体轨迹；核对输入路由和失败记录；报告与无分数基线的配对比较。随后再考虑第二模型与网络结构。改变谁能看见谁时，还需区分网络连接方式与每人获得的消息数量；不在当前阶段同时扩展这些因素。')
rigor += note('可复现性的核心是保留生成规则、初答、每次实际输入、输出、失败、费用和分析方法。当前文档所有实测结果来自保存记录；后续计划没有被写成已经完成的实验。')

revision = h('本次保留什么')+p('保留原 proposal 的核心问题：固定证据与初始意见，研究分数归属的局部影响，再检验能否预测群体结果。保留真实初答、配对比较、输入隔离、独立测试、固定投票规则、干预撤除和独立复核对照。')
revision += h('本次删除或调整什么')+tbl(['原计划中的内容','修订处理与原因'],[['把错误方高分作为所有任务的主要对照','当前需求主分析改为 A/B 立场交换；实际状态、完整信息参考概率和预测正确性分别定义。'],['把二元答案转移作为唯一响应','加入对报告概率的预测目标；现有数据已显示概率变化与选项变化可以不同。'],['固定持续分数与答案状态假设','从当前单次干预逐步进入撤除实验；连续概率和理由若保留，就必须进入状态定义。'],['预先锁定影响权重公式和动力学结论','移出主方案；目前没有实测拟合与样本外验证支持这些假设。'],['固定 160 题与约三万次调用的大方案','删除该规模承诺，按实际题间波动、精度目标和预算确定下一批。'],['同时展开多模型、多网络与多个任务家族','列为后续扩展，优先完成一个协议下的局部到群体检验。'],['实验尚未开始、模型配置未定','替换为已保存的实际设置、12 批运行记录及明确的待完成项。']])
revision += p('删除旧理论推导并不表示已经证明其数学结论错误；它们依赖尚未验证的响应形式，而且不是理解当前实验所必需，因此不纳入当前研究的主要论证。逻辑与供应商实验的无效或未复现结果仍完整保留在附录，不因修订而删除。')
revision += h('数据与源文件怎样对应')+tbl(['内容','仓库中的来源'],[['原始研究计划','Proposal/main.tex 与 main.pdf；原文件保留备查，不附在本修订稿末尾。'],['完整中文阶段报告','scripts/build_narrative_report_html.py 与 output/html/confidence_agents_experiment_report_zh.html。'],['需求发现批与复核批','runs/signal-visibility-luna-20260919 与 runs/signal-visibility-replication-20260920。'],['运行前规定','上述目录的 PROTOCOL.md；复核另有 REPLICATION_PLAN.md。'],['具体输入与输出','manifest.json、roots.json、updates.json，以及 items 下的 calls 文件。'],['汇总与核对','summary.json、independent_audit.json，以及本整合稿的 build_audit.json。'],['整合稿重建','scripts/build_integrated_proposal.py；只读取保存的数据，不发起模型调用。']])
revision += note('本修订稿是一份独立可读的研究计划与证据报告。早期实验保留作为事实记录；不适用的旧计划不再作为当前承诺。')

# Extract actual prompts and responses, rather than reconstructing experimental inputs.
prompt_calls={}
run=ROOT/'runs/signal-visibility-replication-20260920'
for path in sorted((run/'items/demand-00/calls').glob('*.json')):
    record=json.loads(path.read_text(encoding='utf-8'))
    messages=record.get('request',{}).get('messages',[])
    if len(messages)!=2:continue
    user=json.loads(messages[1]['content'])
    if user.get('your_member_id')!='member-3':continue
    peers=user.get('peer_reports',[])
    if not peers:key='initial'
    else:
        c={x['member_id']:x.get('confidence') for x in peers}
        if c.get('member-4')==0.771429 and c.get('member-1')==0.6:arm='A_high'
        elif c.get('member-4')==0.6 and c.get('member-1')==0.771429:arm='B_high'
        else:continue
        key=('full' if 'surveys' in peers[0] else 'advice')+'_'+arm
    if key not in prompt_calls:
        prompt_calls[key]={'source':str(path.relative_to(ROOT)).replace('\\','/'),'request':record['request'],'response':record['parsed']}
assert set(prompt_calls)=={'initial','advice_A_high','advice_B_high','full_A_high','full_B_high'}
sysmsg=prompt_calls['initial']['request']['messages'][0]['content']
assert all(x['request']['messages'][0]['content']==sysmsg for x in prompt_calls.values())
prompts = h('一份 prompt 分成两个部分')+p('实际请求含 system 和 user 两条消息。system 给所有成员相同的角色、选择规则和输出要求；user 给这一次作答的具体资料。下面先用中文忠实解释内容，再展示真实字段和返回结果。中文说明没有在已完成实验中发送给模型；实际英文原文在附录 F，可逐项核对。')
prompts += ex('共同 system 提示的中文说明','你是六名平级分析员之一，预测一种新产品的需求。A 表示低需求，B 表示高需求。请报告 p_B，即高需求的概率，取值为 0 到 1。预测按报告概率与最终需求状态的平方误差评价。p_B 大于 0.5 时选 B，否则选 A。使用提供的信息，不要假定知道没有显示的调查。如果显示置信度，它表示报告者声称所推荐状态正确的概率，并不是保证。只返回 JSON，包含 answer、p_B 和一句简短 reason。')
prompts += h('第一次请求：只有自己的三份调查')
prompts += ex('成员 3 的初答 user 内容：中文说明','任务：预测需求低（A）还是高（B）。生成规则：需求高的先验概率为 0.5；如果真实需求高，调查以 0.6 的概率报告高；如果真实需求低，调查以 0.4 的概率报告高。给定真实状态后，十八份调查独立，每名成员最初获得三份不同调查；每份调查只计算一次。你的编号是 member-3；你的调查依次为 low、high、low。每份调查带一个唯一 source_id，供识别来源。')
prompts += p('第一次输入没有 peer_reports（同伴报告），也没有 your_previous_forecast（自己的前答）。没有把真实需求 low、其他人的调查或预期答案传入。source_id 只是调查标识，不能解读成可靠性分数。')
prompts += code(json.dumps(prompt_calls['initial']['response'],ensure_ascii=False,indent=2))
prompts += p('上面是真实返回值。它选择 A，并报告 p_B=0.4；reason 的意思是“两份低、一份高的信号，按给定规则得到高需求概率 0.40”。程序保存这份输出，后面的每个更新分支都使用同一份初答。')
prompts += h('第二次请求：只看建议，A 方拿高分')
prompts += p('system 完全相同；user 保留生成规则、身份、自己的三份调查，再新增下面两个字段。表格保留实际请求中的同伴顺序。')
prompts += code('"your_previous_forecast": {"answer": "A", "p_B": 0.4}')
u=json.loads(prompt_calls['advice_A_high']['request']['messages'][1]['content'])
prompts += tbl(['peer_reports 中的身份','answer','confidence','实际向接收者表达的意思'],[[q['member_id'],q['answer'],str(q['confidence']),('低需求' if q['answer']=='A' else '高需求')+'；对所选状态的把握约 '+f"{q['confidence']*100:.2f}%"] for q in u['peer_reports']])
prompts += code(json.dumps(prompt_calls['advice_A_high']['response'],ensure_ascii=False,indent=2))
prompts += p('这条真实回答给出 p_B=0.0375532，仍选 A。reason 推断了同伴调查的数量；但输入只给了建议和分数，没有给同伴调查。这个理由是需要分析的模型输出，不能当成实验者提供的事实。实际总数是六份高、十二份低。')
prompts += h('第三种输入：B 方拿高分，具体只改哪里')
prompts += tbl(['位置','A 方拿高分的输入','B 方拿高分的输入'],[['member-4 的 confidence','0.771429','0.6'],['member-1 的 confidence','0.6','0.771429'],['其他全部内容','生成规则、自己的资料和前答、同伴选择、身份及顺序','完全相同']])
prompts += code(json.dumps(prompt_calls['advice_B_high']['response'],ensure_ascii=False,indent=2))
prompts += p('实际 prompt 没有写“A 方高分组”或“B 方高分组”，也没有告诉模型预期方向。它只是收到换了两个数字的报告。这两种分支各自从第一次真实回答出发；后一种看不到前一种的更新结果。')
prompts += h('第四种输入：完整证据，具体新增哪里')
prompts += p('在每个 peer_reports 条目中加入 surveys 数组，列出该人的三份调查及 source_id。例如 member-4 那一条在 A 方高分条件下如下；其他四人也各加入真实的三份调查。')
fullu=json.loads(prompt_calls['full_A_high']['request']['messages'][1]['content'])
prompts += code(json.dumps(next(q for q in fullu['peer_reports'] if q['member_id']=='member-4'),ensure_ascii=False,indent=2))
prompts += p('这里会出现一个有意保留的冲突：成员 4 的调查是高、低、低，按题目规则对应对 A 的 60% 把握，但显示分数是我们替换后的 77.1429%。模型拿到原始调查后可以自行核算；这一设置正是要检验可核查证据是否限制分数的影响。')
prompts += code(json.dumps(prompt_calls['full_A_high']['response'],ensure_ascii=False,indent=2))
prompts += note('prompt 的受控变化可以定位到具体字段：交换两个 confidence 数值，或者增加/移除五个 surveys 数组。正文展示的是实际案例；完整英文输入和请求设置保存在附录 F。')

promptappendix=p('本附录直接读取复核批 demand-00、member-3 的保存请求。每种输入选按文件名排序的第一条实际记录，完整保留 system 文本、user 的字段值与数组顺序。下面的 JSON 仅增加缩进便于阅读；原始字符串与请求设置另存于同目录 prompt_examples.json。这些示例都是已经运行过的输入，没有把修订计划伪装成已运行 prompt。')
promptappendix+=h('F.1 共同 system：原始英文全文')+code(sysmsg)
labels=[('initial','F.2 初答：完整 user'),('advice_A_high','F.3 只看建议、A 方高分：完整 user'),('advice_B_high','F.4 只看建议、B 方高分：完整 user'),('full_A_high','F.5 完整证据、A 方高分：完整 user')]
for key,title in labels:
    r=prompt_calls[key]
    promptappendix+=h(title)+p('来源：'+r['source'])+code(json.dumps(json.loads(r['request']['messages'][1]['content']),ensure_ascii=False,indent=2))
promptappendix+=h('F.6 完整证据、B 方高分如何得到')+p('使用 F.5 的完整 user，只把 member-4 的 confidence 改为 0.6，把 member-1 的 confidence 改为 0.771429；其余全部相同。对应实际请求同样保存在 prompt_examples.json 的 full_B_high 条目。程序已核对这两个字段之外没有差异。')
for vis in ['advice','full']:
    ua=json.loads(prompt_calls[vis+'_A_high']['request']['messages'][1]['content'])
    ub=json.loads(prompt_calls[vis+'_B_high']['request']['messages'][1]['content'])
    for q in ua['peer_reports']:
        if q['member_id']=='member-4':q['confidence']=0.6
        if q['member_id']=='member-1':q['confidence']=0.771429
    assert ua==ub
for arm in ['A_high','B_high']:
    uf=json.loads(prompt_calls['full_'+arm]['request']['messages'][1]['content'])
    ua=json.loads(prompt_calls['advice_'+arm]['request']['messages'][1]['content'])
    for q in uf['peer_reports']:q.pop('surveys')
    assert uf==ua
promptappendix+=h('F.7 请求配置：所有条件保持相同')
config={k:v for k,v in prompt_calls['initial']['request'].items() if k!='messages'}
assert all({k:v for k,v in x['request'].items() if k!='messages'}==config for x in prompt_calls.values())
promptappendix+=code(json.dumps(config,ensure_ascii=False,indent=2))
promptappendix+=p('response_format 的 schema 要求 answer、p_B、reason 三个字段，避免把未输出完或格式错误误算成有效答案。没有在 prompt 中附加实验真实需求、对错标签或模型更新的目标值。')
(OUT/'prompt_examples.json').write_text(json.dumps(prompt_calls,ensure_ascii=False,indent=2),encoding='utf-8')

# Reuse the entire detailed report, changing order and figure numbers only.
sections=[]
sections.append(sec('orientation','先把任务讲清楚：六个模型怎样判断同一个市场','读者无需了解多 agent 框架。先看每份请求给什么信息、得到什么回答。',introbody))
sections.append(saved['demand-task'])
sections.append(saved['goal'])
sections.append(sec('bridge','研究意义，以及当前实验与原 proposal 的关系','局部方向变化、预测质量和群体传播，是相连但需要分别验证的问题。',bridge))
design=saved['demand-design'].replace("<h3>",'<h3>',1)
design=design.replace('</section>',branchfig+'</section>')
sections.append(design)
sections.append(sec('prompts','实际 prompt：模型收到什么，返回什么','先读中文说明，再对照真实输入字段；完整英文原文在附录 F。',prompts))
for sid in ['demand-case','demand-results']:
    s=saved[sid].replace('图 1','图 3').replace('图 2','图 4')
    sections.append(s)
sections.append(saved['interpretation'])
sections.append(sec('related','前人研究与我们的具体问题','已有工作提供任务和方法依据；本项目的贡献需要靠整组实验验证。',related))
sections.append(sec('future','后续实验：从一次更新走向群体判断','三个步骤分别检验局部规律、事先群体预测和干预撤除后的传播。',future))
sections.append(sec('model','怎样用局部数据预测群体' ,'这是候选方法。目前需求实验尚未验证这一预测器。',model))
sections.append(sec('rigor','如何实施、评价和复现','模型设置、输入控制、统计单位、质量指标与执行边界。',rigor))
sections.append(saved['status'])
main_count=len(sections)
sections += [saved[x] for x in ['tasks','logic','supplier','records']]
sections.append(sec('revision','附录 E｜修订说明与材料来源','保留可检验的研究主线，删除与当前证据不匹配的前提。',revision))
sections.append(sec('prompt-original','附录 F｜真实英文 prompt 与请求配置','直接取自已保存的复核实验，可与中文讲解逐项对应。',promptappendix))

toc=[]
for i,s in enumerate(sections):
    s=re.sub(r'<div class="num">.*?</div>','',s,count=1)
    title=html.unescape(re.search(r'<h2>(.*?)</h2>',s,re.S).group(1))
    label=f'{i+1:02d}' if i<main_count else '附录 '+chr(65+i-main_count)
    if i<main_count:
        s=s.replace('<h2>','<h2>'+label+' · ',1)
        title=label+' · '+title
    toc.append((re.search(r'<section id="([^"]+)"',s).group(1),title))
    sections[i]=s

css=re.search(r'<style>(.*?)</style>',report,re.S).group(1)
css+='\nheader,section{max-width:980px}main{padding-right:4vw;padding-left:4vw}h1{font-size:35px}.lead{color:#4e6572}figure{background:#fff}.download{font-size:14px}nav a{font-size:12px}.equation{overflow-wrap:anywhere} @media print{.html-only{display:none}}'
css+='\npre{font:13px/1.7 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;border:1px solid #dce5e9;padding:18px;border-radius:5px}code{font-family:inherit}'
header='''<header id="start"><div class="eyebrow">RESEARCH PROPOSAL + PILOT EXPERIMENTS</div><h1>从置信度到群体判断</h1><p class="lead">研究计划与已完成实验整合版<br>先理解任务，再理解对照、结果与下一步验证。</p>'''
header+=p('研究问题：保持证据和初始意见不变，仅改变置信度分配给谁，会怎样改变下一次判断？这种局部变化能否提前预测群体交流的结果？')
header+=p('当前发现：在合成市场需求任务中，只能看到同伴建议时，交换高分归属使报告的高需求概率平均移动 14.81 和 22.48 个百分点，两批方向一致；给出全部原始调查后，平均额外影响很小。需求任务尚未完成完整群体多轮预测。')
header+='<div class="route"><strong>建议的阅读顺序</strong>'+p('第一次阅读按正文顺序即可：任务与真实题目 → 研究目标 → 对照输入 → 真实输出和计算 → 整批结果 → 文献联系 → 后续群体实验。早期找题、实验账目、修订说明与材料来源集中在附录。')+'</div>'
header+=p('本稿合并原 proposal 与完整版中文实验报告。已完成与计划中的实验分别标注；新增示意图只解释流程，不表示尚未收集的结果。整理日期：2026 年 9 月 18 日。')
header+='<div class="tools"><button id="expand">展开所有附录细节</button><button id="collapse">收起补充细节</button><button id="print">打印</button></div></header>'
js=re.search(r'<script>(.*?)</script>',report,re.S).group(1)
nav=''.join(f'<a href="#{sid}">{H(title)}</a>' for sid,title in toc)
doc='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>从置信度到群体判断 · 整合研究计划与实验</title><style>'+css+'</style></head><body><aside><div class="brand">CONFIDENCE AGENTS</div><h2>研究计划与实验</h2><nav><a href="#start">摘要与阅读说明</a>'+nav+'</nav></aside><main>'+header+''.join(sections)+'<footer class="footer">全部实测数据来自本地保存记录；没有为本稿新增模型调用。原始 proposal 在仓库中保留；本稿不再附上旧版本全文。</footer></main><script>'+js+'</script></body></html>'
assert 'sk-or-' not in doc
htmlpath=OUT/'proposal_with_experiments_zh.html'
htmlpath.write_text(doc,encoding='utf-8')

# Minimal HTML tree for a matching PDF without browser-based rendering.
class Node:
    def __init__(self,tag,attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
    def text(self):return ''.join(x if isinstance(x,str) else x.text() for x in self.children)
    def find(self,tag):
        out=[]
        for x in self.children:
            if isinstance(x,Node):
                if x.tag==tag:out.append(x)
                out.extend(x.find(tag))
        return out
class Parser(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.root=Node('root');self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs);self.stack[-1].children.append(n)
        if tag not in ['meta','br','hr','img','link','input']:self.stack.append(n)
    def handle_startendtag(self,tag,attrs):self.stack[-1].children.append(Node(tag,attrs))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)

pdfmetrics.registerFont(TTFont('CN','C:/Windows/Fonts/simsun.ttc',subfontIndex=0))
pdfmetrics.registerFont(TTFont('CNBold','C:/Windows/Fonts/simhei.ttf'))
pdfmetrics.registerFontFamily('CN',normal='CN',bold='CNBold',italic='CN',boldItalic='CNBold')
W=A4[0]-92
INK=colors.HexColor('#243441'); BLUE=colors.HexColor('#286b82')
st={
 'body':ParagraphStyle('body',fontName='CN',fontSize=10.5,leading=17,spaceAfter=9,wordWrap='CJK',textColor=INK),
 'h1':ParagraphStyle('h1',fontName='CNBold',fontSize=19,leading=27,spaceAfter=16,wordWrap='CJK',textColor=INK,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='CNBold',fontSize=12,leading=18,spaceBefore=10,spaceAfter=8,wordWrap='CJK',textColor=BLUE,keepWithNext=True),
 'small':ParagraphStyle('small',fontName='CN',fontSize=8.5,leading=13,spaceAfter=8,wordWrap='CJK',textColor=colors.HexColor('#526674')),
 'cell':ParagraphStyle('cell',fontName='CN',fontSize=8.6,leading=13.4,wordWrap='CJK',textColor=INK),
 'cover':ParagraphStyle('cover',fontName='CNBold',fontSize=29,leading=40,spaceAfter=24,textColor=INK,wordWrap='CJK'),
}
st['note']=ParagraphStyle('note',parent=st['body'],backColor=colors.HexColor('#eef5f5'),borderPadding=9,spaceBefore=10,spaceAfter=15)
st['code']=ParagraphStyle('code',parent=st['body'],fontName='Courier',fontSize=8,leading=11,spaceAfter=10,backColor=colors.HexColor('#f3f6f8'),borderPadding=7)
def para(s,key='body'):return Paragraph(escape(s).replace('\n','<br/>'),st[key])

def svg_drawing(n):
    vb=list(map(float,n.attrs['viewbox' if 'viewbox' in n.attrs else 'viewBox'].split()))
    width,height=vb[2:];d=Drawing(width,height)
    def color(x,default):return colors.HexColor(x) if x and x!='none' else default
    for child in n.children:
        if not isinstance(child,Node):continue
        a=child.attrs
        fill=color(a.get('fill'),INK);stroke=color(a.get('stroke'),None)
        sw=float(a.get('stroke-width',1))
        if child.tag=='rect':
            x,y,w,hh=[float(a[k]) for k in ['x','y','width','height']]
            d.add(Rect(x,height-y-hh,w,hh,rx=float(a.get('rx',0)),fillColor=fill,strokeColor=stroke,strokeWidth=sw))
        elif child.tag=='line':
            d.add(Line(float(a['x1']),height-float(a['y1']),float(a['x2']),height-float(a['y2']),strokeColor=stroke or INK,strokeWidth=sw))
        elif child.tag=='circle':
            d.add(Circle(float(a['cx']),height-float(a['cy']),float(a['r']),fillColor=fill,strokeColor=stroke))
        elif child.tag=='text':
            d.add(String(float(a['x']),height-float(a['y']),child.text(),fontName='CN',fontSize=float(a.get('font-size',13)),textAnchor=a.get('text-anchor','start'),fillColor=fill))
    scale=W/width;d.scale(scale,scale);d.width=W;d.height=height*scale
    return d

figure_pages=[]
class Doc(SimpleDocTemplate):
    def afterFlowable(self,f):
        if hasattr(f,'_heading'):
            key,title=f._heading;self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0)
            self.notify('TOCEntry',(0,title,self.page,key))
        if hasattr(f,'_figure_id'):figure_pages.append((f._figure_id,self.page))
def pagecanvas(c,doc):
    c.setStrokeColor(colors.HexColor('#dce5e9'));c.line(46,39,A4[0]-46,39)
    c.setFont('CN',8);c.setFillColor(colors.HexColor('#65737d'))
    c.drawString(46,26,'从置信度到群体判断 | 研究计划与已完成实验')
    c.drawRightString(A4[0]-46,26,str(doc.page))

story=[Spacer(1,43),para('从置信度到群体判断','cover'),para('From Confidence to Consensus','h2'),para('研究计划与已完成实验整合版','h1')]
hp=Parser();hp.feed(header)
for node in hp.root.find('p'):
    story.append(para(node.text(),'body'))
story.append(PageBreak());story.append(para('目录','h1'))
tocflow=TableOfContents();tocflow.levelStyles=[ParagraphStyle('toc',parent=st['body'],fontSize=9.6,leading=15,spaceBefore=3,leftIndent=0,rightIndent=25)]
story.extend([tocflow,PageBreak()])

def convert(n):
    if isinstance(n,str):return []
    if 'html-only' in n.attrs.get('class',''):return []
    if n.tag in ['h3','summary']:return [para(n.text(),'h2')]
    if n.tag=='p':
        links=[x for x in n.find('a') if x.attrs.get('href','').startswith('https://')]
        if links:
            a=links[0];return [Paragraph(f'<link href="{escape(a.attrs["href"])}" color="#286b82">{escape(a.text())}</link>',st['body']),para(a.attrs['href'],'small')]
        return [para(n.text())]
    if n.tag=='pre':return [para(n.text(),'code')]
    if n.tag=='strong':return [para(n.text(),'h2')]
    if n.tag=='table':
        rows=[]
        for tr in n.find('tr'):
            cells=[x for x in tr.children if isinstance(x,Node) and x.tag in ['th','td']]
            rows.append([para(x.text(),'cell') for x in cells])
        count=len(rows[0]);assert all(len(row)==count for row in rows)
        widths=[W/count]*count
        if count==2:widths=[W*.29,W*.71]
        if count==3:widths=[W*.23,W*.385,W*.385]
        t=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.35,colors.HexColor('#dce5e9')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        return [t,Spacer(1,11)]
    if n.tag=='figure':
        svg=n.find('svg')[0];cap=n.find('figcaption')[0].text()
        drawing=svg_drawing(svg);drawing._figure_id=cap.split('。')[0][:12]
        return [KeepTogether([drawing,Spacer(1,6),para(cap,'small')]),Spacer(1,8)]
    if n.tag=='div' and n.attrs.get('class')=='conclusion':
        return [para(n.text(),'note')]
    if n.tag=='li':
        out=[]
        for x in n.children:out.extend(convert(x))
        return out
    out=[]
    for child in n.children:out.extend(convert(child))
    return out

for i,s in enumerate(sections):
    parser=Parser();parser.feed(s);node=parser.root.find('section')[0]
    title=node.find('h2')[0].text()
    if i:story.append(PageBreak())
    heading=para(title,'h1');heading._heading=(node.attrs['id'],title);story.append(heading)
    for child in node.children:
        if isinstance(child,Node) and child.tag=='h2':continue
        story.extend(convert(child))

bodypdf=OUT/'proposal_integrated_body_zh.pdf'
pdf=Doc(str(bodypdf),pagesize=A4,rightMargin=46,leftMargin=46,topMargin=48,bottomMargin=53,
    title='从置信度到群体判断：研究计划与已完成实验',author='Confidence Agents research project')
pdf.multiBuild(story,onFirstPage=pagecanvas,onLaterPages=pagecanvas)
bodypages=len(PdfReader(str(bodypdf)).pages)
pdfpath=OUT/'proposal_with_experiments_zh.pdf'
pdfpath.write_bytes(bodypdf.read_bytes())
assert hashlib.sha256(original.read_bytes()).hexdigest()==original_hash

# Export figures for reuse; HTML remains standalone.
figures=re.findall(r'<figure>(.*?)</figure>',doc,re.S)
for idx,figure in enumerate(figures,1):
    svg=re.search(r'<svg.*?</svg>',figure,re.S).group(0)
    if 'xmlns=' not in svg:svg=svg.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"',1)
    svg=svg.replace('<svg','<svg style="font-family:Microsoft YaHei,SimSun,sans-serif;font-size:13px;fill:#243441"',1)
    (FIG/f'figure_{idx:02d}.svg').write_text(svg,encoding='utf-8')
ids=re.findall(r' id="([^"]+)"',doc);links=re.findall(r'href="#([^"]+)"',doc)
assert len(ids)==len(set(ids)) and set(links)<=set(ids)
assert len(figures)==6
audit={'sections':len(sections),'main_sections':main_count,'figures':len(figures),'body_pages':bodypages,
    'original_pages_appended':0,'total_pages':bodypages,'prompt_examples':len(prompt_calls),'prompt_pair_checks':'passed',
    'original_sha256':original_hash,'broken_internal_links':0,'new_model_calls':0,
    'source_report_sha256':hashlib.sha256(report.encode()).hexdigest(),
    'html':str(htmlpath),'pdf':str(pdfpath),'visual_review':'pending'}
(OUT/'build_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=True))
