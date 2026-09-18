"""Audit the completed sweep and write a Chinese report from persisted data."""
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.confidence_sweep import GAPS, messages
from confidence_agents.runtime import save

directory=Path('runs/confidence-gap-luna-20260918')
manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
rows=json.loads((directory/'results.json').read_text(encoding='utf-8'))
records=[json.loads(p.read_text(encoding='utf-8')) for p in (directory/'items').glob('*/calls/*.json')]
assert len(records)==len(rows)==960
contexts={c['task']['id']:c for c in manifest['contexts']}
for record in records:
    _,_,item,arm,rep=record['call_id'].split('/')
    assert record['request']['messages']==messages(contexts[item],arm)
    assert record['request']['model']==manifest['model']['id']
    assert record['request']['max_tokens']==8192
assert len({r['call_id'] for r in records})==960
audit={'requests':len(records),'all_messages_match_frozen_design':True,
       'status_counts':dict(Counter(r['status'] for r in records)),
       'valid':sum(r.get('valid',False) for r in records),
       'failure_categories':dict(Counter(r.get('failure_category') or r.get('error_type') or r['status'] for r in records if not r.get('valid',False))),
       'providers':dict(Counter(r.get('response',{}).get('provider','unknown') for r in records)),
       'missing_call_ids':[r['call_id'] for r in records if not r.get('valid',False)],
       'max_completion_tokens':max(r.get('response',{}).get('usage',{}).get('completion_tokens',0) for r in records),
       'usage':summary['usage']}
save(directory/'audit.json',audit)
def pct(value):
    return '未定义' if value is None else f'{100*value:.2f}'
def interval(values):
    return '未定义' if values is None else f'[{pct(values[0])}, {pct(values[1])}]'
ci=summary['descriptive_stratified_item_bootstrap_95pct']
conclusion=('主要斜率区间包含零，尚未观察到分差增大带来一致影响的明确证据。' if ci and ci[0]<=0<=ci[1]
            else ('观察到负向的探索性趋势：分差增加时，错误方高分相对正确方高分的错误率差下降，方向与原假设相反。主要斜率区间未包含零，需用新题确认。' if ci and ci[1]<0
                  else '主要斜率区间未包含零；这是复用题库上的探索性结果，需用新题确认。'))
lines=['# Confidence 分差实验报告','',conclusion,'',
       '## 目的与指标','',
       '检验平级同伴报告的 confidence 分差是否改变接收者的错误率。对每道题、每个分差计算 Δ = 错误方高分的错误率 − 正确方高分的错误率。正值表示错误方高分增加错误率。主要指标为三个分差下 Δ 对分差的题内线性回归斜率，再按题等权平均。','',
       '说明性示例：若分差从 0.10 到 0.40，Δ 从 0 到 0.06，则这两个点对应斜率为 0.20；本实验实际使用三个分差拟合。','',
       '## 设置','',
       '2026-09-18 启动；随机种子 20260922。40 道既有平衡逻辑题，每条件重复 3 次，共 8 条件、960 次请求。模型 GPT-5.6 Luna，medium 推理，8192 token 上限，严格 JSON 输出。自身答案和四份同伴答案均为预设；正确和错误同伴各两人；每题各条件的题目、身份、顺序和自身答案固定。',
       '分数均值 .75；高低分为 .80/.70、.90/.60、.95/.55，分别交换高分方；另有等分 .75 和隐藏分数。所有新条件统一明确 confidence 指对自身所选答案正确的报告概率。新旧实验不直接合并。','',
       '## 结果','',
       f"主要分析完整题数：{summary['primary_complete_items']}/40。斜率换算为分差每增加 0.10，Δ 改变 {pct(summary['primary_slope']*.1) if summary['primary_slope'] is not None else '未定义'} 个百分点；描述性 95% 区间 {interval([x*.1 for x in ci]) if ci else '未定义'} 个百分点。",'',
       '| 分差 | 正确方高分错误率 | 错误方高分错误率 | 完整配对题数 | 配对 Δ（百分点） | 描述性 95% 区间 | 缺失响应界限 |',
       '|---|---:|---:|---:|---:|---|---|']
for gap in GAPS:
    result=summary['gap_contrasts'][gap]
    lines.append(f"| {int(gap)/100:.2f} | {pct(result['arms']['correct_high']['item_weighted_wrong_rate'])}% | {pct(result['arms']['wrong_high']['item_weighted_wrong_rate'])}% | {result['primary_paired_items']} | {pct(result['primary_delta_wrong_high_minus_correct_high'])} | {interval(result['descriptive_stratified_item_bootstrap_95pct'])} | {interval(result['all_completed_item_missing_response_bounds'])} |")
control=summary['gap_contrasts']['10']['arms']
lines.extend(['',f"等分 .75 的题均错误率：{pct(control['equal']['item_weighted_wrong_rate'])}%；隐藏分数：{pct(control['hidden']['item_weighted_wrong_rate'])}%。",'',
              '各条件错误率使用该条件有效回答的题均值；配对 Δ 使用完整配对题，两者在缺失时不一定相减相等。区间按题分层 bootstrap 2000 次，保持语义真值、正确选项和预设自身正确性分层。三个分差区间均未校正多重比较。缺失响应界限将缺失值分别赋为最有利/最不利结果，属于确定性范围，不是置信区间。','',
              '## 完整性与限制','',
              f"960 个请求记录中有效回答 {audit['valid']} 个；状态统计 {audit['status_counts']}。未完整返回的请求没有重发，费用可能未知。已知费用 ${summary['usage']['reported_cost_usd']:.6f}，另有 {summary['usage']['requests_without_cost']} 个请求费用未知。所有请求的提示均通过冻结设计核验。",'',
              '缺失响应可能并非随机，完整题分析有选择偏差风险。主要斜率没有填补缺失值，各分差另报缺失界限。既有题库复用、单一模型、单一上下文种子和每条件三次重复限制推广范围。当前实验只测试预设同伴报告下的一次更新，尚未检验真实多轮群体讨论。',
              '全部条件均报告，不按效果筛选题目或追加采样。分差与结果的机制关系尚未验证。','',
              '## 当前结论','',conclusion,
              '不能据此声称模型主动抵抗高 confidence，原因未查明。任何方向的探索结果均需要独立新题复核；区间包含零不能证明 confidence 在所有场景都无效。',''])
check_path=directory/'independent_check.json'
if check_path.exists():
    check=json.loads(check_path.read_text(encoding='utf-8'))
    lines.extend(['## 独立复核','',
                  f"对全部 {check['allocation_requests_verified']} 个不等分请求，直接根据题目真值检查分数大小，确认正确方/错误方标签没有反转；并直接从原始回答重算错误计数。",
                  f"额外敏感性分析：全部 40 题对缺失回答作任意正确/错误赋值，平均斜率对应分差每增加 0.10 的 Δ 变化界限为 {interval([x*.1 for x in check['all40_slope_missing_bounds']])} 个百分点。该范围仅反映缺失回答的不确定性，不是抽样置信区间。",''])
(directory/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
