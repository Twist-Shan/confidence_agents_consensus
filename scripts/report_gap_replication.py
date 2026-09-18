"""Audit the new bank run and compare against discovery without pooling."""
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.confidence_sweep import messages
from confidence_agents.runtime import save

old_dir=Path('runs/confidence-gap-luna-20260918')
new_dir=Path('runs/confidence-gap-replication-luna-20260923')
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
old=load(old_dir/'summary.json'); new=load(new_dir/'summary.json')
manifest=load(new_dir/'manifest.json'); previous=load(old_dir/'manifest.json')
for field in ('protocol','model','max_tokens','seed','repeats','workers','arms','primary','analysis','peer_design','confidence_definition','scores'):
    assert manifest[field]==previous[field],field
assert manifest['bank_hash']!=previous['bank_hash']
contexts={c['task']['id']:c for c in manifest['contexts']}
rows=load(new_dir/'results.json')
records=[load(p) for p in (new_dir/'items').glob('*/calls/*.json')]
assert len(rows)==len(records)==960
assert len({r['call_id'] for r in records})==960
pooled=Counter(); matched=0
for record in records:
    _,_,item,arm,rep=record['call_id'].split('/')
    assert record['request']['messages']==messages(contexts[item],arm)
    assert record['request']['model']==manifest['model']['id']
    assert record['request']['max_tokens']==manifest['max_tokens']
    peers=json.loads(record['request']['messages'][1]['content'])['peer_reports']
    truth=contexts[item]['task']['truth']
    if arm not in ('equal','hidden'):
        correct=[p['confidence'] for p in peers if p['answer']==truth]
        wrong=[p['confidence'] for p in peers if p['answer']!=truth]
        assert (min(correct)>max(wrong))==arm.startswith('correct_high')
        matched+=1
    if record.get('parsed'):
        pooled[arm+'/valid']+=1
        pooled[arm+'/wrong']+=record['parsed']['answer']!=truth
audit={'requests':960,'all_requests_match_design':True,'independent_allocation_checks':matched,
       'valid':sum(r.get('valid',False) for r in records),
       'status_counts':dict(Counter(r['status'] for r in records)),
       'failures':dict(Counter(r.get('failure_category') or r.get('error_type') or r['status'] for r in records if not r.get('valid',False))),
       'providers':dict(Counter(r.get('response',{}).get('provider','unknown') for r in records)),
       'pooled_counts':dict(pooled),'missing_call_ids':[r['call_id'] for r in records if not r.get('valid',False)]}
save(new_dir/'audit.json',audit)
def pp(v):
    return '未定义' if v is None else f'{v*100:+.2f}'
def ci(v):
    return '未定义' if v is None else '['+', '.join(pp(x) for x in v)+']'
interval=new['descriptive_stratified_item_bootstrap_95pct']
if interval is None:
    conclusion='有效完整题不足，无法判断负向趋势是否重复出现。'
elif interval[1]<0:
    conclusion='新题复核再次观察到负向趋势，主要斜率区间不包含零。该结果支持此固定单次更新设置中的负向分差趋势，机制尚未确定。'
elif interval[0]>0:
    conclusion='新题复核呈正向趋势，与旧题的负向趋势相反。旧结果的方向未能重复出现，不能宣称稳定反向效应。'
else:
    conclusion='新题复核的主要斜率区间包含零，未能明确复现旧题的负向趋势。当前不足以声称稳定反向效应。'
lines=['# 新题 confidence 分差复核','',conclusion,'',
       '## 目的和冻结设置','',
       '更换 40 道逻辑 L2 题，检验上一轮负向趋势是否在同一生成分布的新题上重复出现。保留八个条件、每条件三次重复、模型配置、提示、分数、上下文生成规则及统计方法。新旧结果单独报告，不以合并结果代替复核。',
       '新题 seed=20260923，上下文 seed=20260922；日期样式 seed 是随机种子。真值两类各 20 题，每类 A/B 各 10；自身预设正确/错误各 20。题目与此前保存题库及 manifest 共 88 个去重问题核对，无相同规范化子句/查询组合；另以独立位掩码枚举程序复核 40 个真值。此去重不声称排除了变量重命名后的同构题。',
       '固定 960 次请求，无基于结果的提前停止或扩样。连接失败保留为缺失，未重发。平级同伴报告和自身先前答案均为预设，模型只进行一次更新。','',
       '## 指标','',
       'Δ = P(错误 | 错误方高分) − P(错误 | 正确方高分)，题内先平均重复，再对完整配对题等权平均。正值表示错误方高分增加错误率。主要指标为每题 Δ 对三个分差 .10/.30/.40 的线性斜率，随后按题平均。',
       '说明性示例：Δ 从 +0.02 降到 −0.04 表示两种高分分配的错误率差下降 6 个百分点，不等于相对隐藏分数的错误率下降 6 个百分点。','',
       '## 主要结果','',
       '| 数据 | 完整题数 | 分差每增加 .10 的 Δ 变化（百分点） | 描述性 95% 区间 |',
       '|---|---:|---:|---|']
for label,s in [('旧题探索',old),('新题复核',new)]:
    interval=s['descriptive_stratified_item_bootstrap_95pct']
    lines.append(f"| {label} | {s['primary_complete_items']} | {pp(s['primary_slope']*.1) if s['primary_slope'] is not None else '未定义'} | {ci([x*.1 for x in interval]) if interval else '未定义'} |")
lines+=['','| 高分 / 低分 | 旧题 Δ（百分点） | 新题 Δ（百分点） | 新题 95% 区间 | 新题配对题数 | 新题缺失界限 |',
        '|---|---:|---:|---|---:|---|']
for gap,label in [('10','.80 / .70'),('30','.90 / .60'),('40','.95 / .55')]:
    a=old['gap_contrasts'][gap]; b=new['gap_contrasts'][gap]
    lines.append(f"| {label} | {pp(a['primary_delta_wrong_high_minus_correct_high'])} | {pp(b['primary_delta_wrong_high_minus_correct_high'])} | {ci(b['descriptive_stratified_item_bootstrap_95pct'])} | {b['primary_paired_items']} | {ci(b['all_completed_item_missing_response_bounds'])} |")
lines+=['','各区间按题分层 bootstrap 2000 次，三个分差的次要区间未作多重比较校正。缺失界限是缺失回答所有可能正确/错误赋值造成的范围，不是抽样置信区间。','',
        '| 新题条件 | 有效回答数 | 错误数 | 题均错误率 |','|---|---:|---:|---:|']
for gap in ('10','30','40'):
    for arm in ('correct_high','wrong_high'):
        a=new['gap_contrasts'][gap]['arms'][arm]
        lines.append(f"| {arm}_{gap} | {a['valid']} | {a['wrong']} | {100*a['item_weighted_wrong_rate']:.2f}% |")
for arm in ('equal','hidden'):
    a=new['gap_contrasts']['10']['arms'][arm]
    lines.append(f"| {arm} | {a['valid']} | {a['wrong']} | {100*a['item_weighted_wrong_rate']:.2f}% |")
lines+=['','## 完整性与限制','',
        f"有效回答 {audit['valid']}/960，失败类别 {audit['failures']}；已知费用 ${new['usage']['reported_cost_usd']:.6f}，{new['usage']['requests_without_cost']} 个请求费用未知。核验全部请求符合冻结提示，独立检查全部 720 个不等分条件分配方向。",'',
        '缺失可能非随机，完整题分析存在选择偏差风险。每条件三次重复有限，统计单位为题目。新题复核仍局限于同一生成器、模型别名、提示和一次更新；模型机制及多轮群体效应未验证。模型别名并非不可变版本。','',
        '## 结论','',conclusion,'']
sensitivity_path=new_dir/'sensitivity.json'
if sensitivity_path.exists():
    sensitivity=load(sensitivity_path)
    lines.extend(['## 缺失响应敏感性补充','',
                  '主要斜率使用同一组 36 道完整题；各分差表使用各自的完整配对题，因此不能直接从表中三个均值反推主要斜率。',
                  f"在全部 40 题中对缺失回答进行所有可能的正确/错误赋值，平均斜率对应分差每增加 .10 的 Δ 变化界限为 {ci([x*.1 for x in sensitivity['all40_slope_missing_bounds']])} 个百分点。这个确定性范围不包括抽样不确定性，不是置信区间。与完整题估计方向不同，说明少量缺失题的排除也会影响接近零的点估计。",''])
(new_dir/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({'audit':audit,'primary_slope':new['primary_slope'],
                  'primary_interval':new['descriptive_stratified_item_bootstrap_95pct'],
                  'gap_deltas':{g:s['primary_delta_wrong_high_minus_correct_high'] for g,s in new['gap_contrasts'].items()}},indent=2))
