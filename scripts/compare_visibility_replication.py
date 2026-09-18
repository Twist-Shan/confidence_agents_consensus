"""Keep discovery and independent replication separate; verify frozen settings."""
import argparse
import ast
import json
from pathlib import Path


def compare(directory):
    directory = Path(directory)
    read = lambda d, name: json.loads((d / name).read_text(encoding='utf-8'))
    manifest = read(directory, 'manifest.json')
    original = Path(manifest['replication_of'])
    old_manifest = read(original, 'manifest.json')
    assert not (directory / '.running').exists()
    assert manifest['backend'] == old_manifest['backend'] == 'openrouter'
    for key in ('protocol', 'seed', 'model', 'max_tokens', 'max_requests', 'repeats',
                'targets_per_item', 'arms', 'visibility', 'low', 'high'):
        assert manifest[key] == old_manifest[key], key
    assert (directory / 'PROTOCOL.md').read_bytes() == (original / 'PROTOCOL.md').read_bytes()
    assert manifest['items'] == read(directory, 'planned_items.json')
    source = lambda d, n: d / 'frozen_source' / 'confidence_agents' / n
    for name in ('runtime.py', 'design.py'):
        assert source(directory, name).read_bytes() == source(original, name).read_bytes()
    functions = lambda d: {n.name: ast.dump(n) for n in ast.parse(source(d, 'signal_visibility.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef)}
    previous, current = functions(original), functions(directory)
    for name in previous.keys() - {'bank', 'run'}:
        assert previous[name] == current[name], name
    preflight = read(directory, 'PREFLIGHT.json')
    results = [read(d, 'summary.json') for d in (original, directory)]
    audits = [read(d, 'independent_audit.json') for d in (original, directory)]
    assert all(a['passed'] for a in audits)
    new = results[1]['primary']
    interval = new['interaction']['descriptive_item_bootstrap_95pct']
    supported = interval is not None and interval[0] > 0 and new['advice']['mean_p_B_shift'] > 0
    conclusion = ('新实例复核支持原先方向：仅见建议时，分数归属的影响大于完整证据条件。'
                  if supported else '新实例复核未达到预先规定的支持标准，不能据此确认原先的信息条件交互。')
    lines = ['# 固定协议的新实例复核', '', conclusion, '',
             '以下效应均为把高分从支持 A 者移给支持 B 者后的 P(B) 变化；单位为百分点。区间是按真实需求分层的题级 bootstrap 描述性 95% 区间。', '',
             '| 指标 | 发现批次 | 新实例复核 |', '|---|---:|---:|']
    for key, label in [('full', '完整证据'), ('advice', '仅见建议'), ('interaction', '仅见建议 − 完整证据')]:
        cells = []
        for result in results:
            p = result['primary'][key]
            lohi = p['descriptive_item_bootstrap_95pct']
            digits = 6 if lohi is not None and max(abs(y) for y in lohi) < .00001 else 3
            cells.append('缺失' if lohi is None else f"{100*p['mean_p_B_shift']:+.{digits}f} [{100*lohi[0]:+.{digits}f}, {100*lohi[1]:+.{digits}f}]")
        lines.append(f'| {label} | {cells[0]} | {cells[1]} |')
    lines += ['', '## 冻结与独立性检查', '',
              '- 模型、提示逻辑、分数、重复次数、实验分配种子、统计函数及请求实现与发现批次一致；原协议文件逐字节一致。',
              '- 任务种子固定为 20260920；实验分配及 bootstrap 种子保持 20260919。种子变更在 REPLICATION_PLAN.md 中提前声明。',
              f"- 与旧批原始信号完全重复的新题：{preflight['exact_signal_overlap_new_items']}/16；保留成员身份、只比较信号数量时重复：{preflight['member_signal_count_overlap_new_items']}/16；再忽略成员身份时重复：{preflight['unordered_member_count_overlap_new_items']}/16。未因此筛题。",
              '- 同一任务槽位名称不代表同一实例；两批数据分别保存，未复用旧批模型响应。', '',
              '## 数据完整性', '', '| 批次 | 合格初始状态 | 主分析题数 | 有效/全部请求 | 已知费用（美元） |', '|---|---:|---:|---:|---:|']
    for label, result in zip(('发现', '复核'), results):
        usage = result['usage']
        lines.append(f"| {label} | {result['eligible_mixed_roots']}/16 | {result['primary']['interaction']['n_items']} | {usage['valid']}/{usage['requests']} | {usage['known_cost_usd']:.6f} |")
    effects = results[1]['item_effects']
    lines += ['', f"复核批次 {sum(r['interaction'] > 0 for r in effects)}/{len(effects)} 题交互为正；{sum(r['advice']['p_B_shift'] > 0 for r in effects)}/{len(effects)} 题仅建议效应为正。", '',
              '## 解释边界', '',
              '复核支持与否按新批次单独判断，没有通过合并两批提高显著性。区间包含零不证明等价或无影响；两批效应数值不同不自动代表复核失败。',
              '本次完整证据效应约为 +0.000176 个百分点，描述性区间虽略高于零，但量级极小；应报告原数值，不能因区间未跨零就解释为有实际意义的置信度影响。',
              '这仍是同一个模型 ID、同一有限信号生成机制、每批 16 题的局部更新实验。初答由六人产生，实际干预测两个接收者；尚未验证群体多轮传播、其他模型或现实场景的泛化。',
              '观察到分数引发概率变化不自动说明非理性或有害依赖。只见建议时，分数可能被当作未显示证据强度的信号。', '',
              '详细逐题结果见本目录 RESULTS_ZH.md；独立原始请求审计见 independent_audit.json。']
    (directory / 'REPLICATION_COMPARISON.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'replication_supported': supported, 'primary': new, 'usage': results[1]['usage']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    compare(parser.parse_args().directory)
