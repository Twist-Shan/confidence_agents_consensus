"""Offline, explicitly post-hoc diagnostics for both frozen confidence sweeps."""
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
from statistics import mean, variance
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.design import rng
from confidence_agents.runtime import save

RUNS={'discovery':'confidence-gap-luna-20260918','replication':'confidence-gap-replication-luna-20260923'}
OUT=Path('runs/item-diagnostics')


def estimate(items,key,seed):
    items=[r for r in items if r.get(key) is not None]
    if not items:
        return {'n':0,'mean':None,'ci':None,'leave_one_out_range':None}
    vals=[r[key] for r in items]
    groups=defaultdict(list)
    for r in items:
        groups[r['semantic'],r['truth'],r['own_correct']].append(r[key])
    random=rng(seed,key)
    boot=sorted(mean(v for group in groups.values() for v in random.choices(group,k=len(group))) for _ in range(2000))
    loo=[(sum(vals)-v)/(len(vals)-1) for v in vals] if len(vals)>1 else []
    return {'n':len(vals),'mean':mean(vals),'ci':[boot[49],boot[1949]],
            'leave_one_out_range':[min(loo),max(loo)] if loo else None,
            'sign_counts':dict(Counter('positive' if v>1e-10 else 'negative' if v< -1e-10 else 'zero' for v in vals))}


def analyze(name,folder):
    rows=json.loads((folder/'results.json').read_text(encoding='utf-8'))
    items=defaultdict(list)
    for r in rows:
        items[r['item_id']].append(r)
    records=[]; complete_cells=0; variable_cells=0
    for item,rs in items.items():
        first=rs[0]
        result={k:first[k] for k in ('item_id','semantic','truth','own_correct')}
        cells={arm:[r['wrong'] for r in rs if r['arm']==arm and r['answer'] is not None] for arm in {r['arm'] for r in rs}}
        for vals in cells.values():
            if len(vals)==3:
                complete_cells+=1
                variable_cells+=len(set(vals))>1
        result['hidden_error']=mean(cells['hidden']) if cells['hidden'] else None
        for gap in ('10','30','40'):
            a,b=cells['correct_high_'+gap],cells['wrong_high_'+gap]
            result['delta_'+gap]=mean(b)-mean(a) if len(a)==len(b)==3 else None
            # Unbiased estimated sampling variance of two independent Bernoulli means.
            result['noise_'+gap]=variance(a)/3+variance(b)/3 if len(a)==len(b)==3 else None
        result['slope_per_010']=sum(w*result['delta_'+gap] for gap,w in [('10',-2.5/7),('30',.5/7),('40',2/7)]) if all(result['delta_'+g] is not None for g in ('10','30','40')) else None
        records.append(result)
    metrics={k:estimate(records,k,name) for k in ('hidden_error','delta_10','delta_30','delta_40','slope_per_010')}
    subgroups={}
    for field in ('semantic','own_correct','truth'):
        for value in sorted({r[field] for r in records},key=str):
            subset=[r for r in records if r[field]==value]
            subgroups[field+'='+str(value)]={k:estimate(subset,k,(name,field,value)) for k in metrics}
    noise={}
    for gap in ('10','30','40'):
        sub=[r for r in records if r['delta_'+gap] is not None]
        observed=variance(r['delta_'+gap] for r in sub)
        sampling=mean(r['noise_'+gap] for r in sub)
        noise[gap]={'observed_variance':observed,'estimated_sampling_variance':sampling,
                    'raw_difference':observed-sampling,
                    'note':'Method-of-moments diagnostic only. May be negative. n=3 cell variance estimates are unstable; do not infer absence/presence of true heterogeneity.'}
    return {'metrics':metrics,'subgroups':subgroups,'complete_three_response_cells':complete_cells,
            'cells_with_both_answers':variable_cells,'noise_diagnostic':noise,'items':records}


def pp(v):
    return 'NA' if v is None else f'{v*100:+.2f}'
def ci(x):
    return 'NA' if x is None else '['+', '.join(pp(v) for v in x)+']'


if __name__=='__main__':
    result={name:analyze(name,Path('runs')/folder) for name,folder in RUNS.items()}
    for name,data in result.items():
        original=json.loads((Path('runs')/RUNS[name]/'summary.json').read_text(encoding='utf-8'))
        assert abs(data['metrics']['slope_per_010']['mean']-original['primary_slope']*.1)<1e-12
    save(OUT/'diagnostics.json',result)
    lines=['# 80 道题的事后诊断','',
           '本分析不新增模型调用。所有分层和敏感性检查属于事后探索，不能作为独立确认性证据；两批题分别报告。',
           'Δ 为错误方高分减正确方高分的错误率差，正值表示增加错误率。斜率换算为分差每增加 .10 时 Δ 的变化。区间为按语义真值、正确选项和预设自身正确性分层的题级 bootstrap 2000 次，未校正多重比较。隐藏条件按每题有效回答计算错误率再题间等权，其余效应使用完整配对题；bootstrap 使用本诊断固定种子，区间端点会与原报告有蒙特卡洛差异。','',
           '## 第一步：不同题是否具有不同表现','',
           '| 批次 | 分层 | 隐藏分数错误率 | 最大分差 Δ（百分点） | Δ 的 95% 区间 | 配对题数 |',
           '|---|---|---:|---:|---|---:|']
    for name,data in result.items():
        for label,sub in data['subgroups'].items():
            lines.append(f"| {name} | {label} | {pp(sub['hidden_error']['mean'])}% | {pp(sub['delta_40']['mean'])} | {ci(sub['delta_40']['ci'])} | {sub['delta_40']['n']} |")
    lines+=['','隐藏分数时仍呈现同伴答案及预设自身答案，因此该条件衡量这类输入下的表现，不能当作模型独立答题能力。每题自身状态只有一个预设值，因此其分层比较不是同一道题内切换自身正确性的实验。组间效应差异需要交互检验及新题复核，不能从一组区间包含零、另一组不包含零推断。','',
            '## 第二步：同题改变 confidence 后，估计是否稳定','',
            '| 批次 | 主要斜率（百分点 / .10 分差） | 逐一删除一道题后范围 | 最大分差 Δ 的逐题正/负/零计数 | 相同条件三次回答不一致的单元 |',
            '|---|---:|---|---|---|']
    for name,data in result.items():
        slope=data['metrics']['slope_per_010']; effect=data['metrics']['delta_40']
        lines.append(f"| {name} | {pp(slope['mean'])} | {ci(slope['leave_one_out_range'])} | {effect['sign_counts']} | {data['cells_with_both_answers']}/{data['complete_three_response_cells']} |")
    lines+=['','逐一删除题目的范围是敏感性范围，不是置信区间。范围不跨零只能排除“单独某一道题决定点估计符号”，不能证明可推广到新题。不同批次题目不相同，不能计算同题效果的跨批次相关或复测稳定性。',
            '每个条件只有三次调用，单题错误率只能以 1/3 递增。假设两个条件独立，即使一组 3/3 错、另一组 0/3 错，在固定边际的双侧 Fisher 精确检验中 p=2/C(6,3)=0.10；不能把这种单题大差值直接称为稳定效应。',
            '另在 JSON 中报告观察到的题间效应方差及估计的题内采样方差。两者相减只是粗略矩估计，可能为负；每单元 n=3 导致方差估计不稳定，不能据此直接确认或否定真实题间异质性。','',
            '## 下一轮如何区分','',
            '先在不看 confidence 干预结果的条件下定义题型与证据强弱，按这些属性分层抽新题；对每个冻结题目上下文重复各 confidence 条件。题内比较估计 confidence 效应，题间比较检验预先规定的属性是否调节该效应。',
            '同题重测应使用一批预先选定的全部题或随机子集，不只选已有大效应题。若要研究自身初始立场的作用，需在同一道题中同时交叉正确/错误自身答案，或使用真实独立初始回答后冻结；两种方案对应不同研究目标。',
            '重复次数与题目数分别控制题内估计精度和跨题推广精度，正式样本量需基于目标最小效应和预算做功效模拟。','']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({n:{k:v for k,v in d.items() if k not in ('items','subgroups')} for n,d in result.items()},indent=2))
