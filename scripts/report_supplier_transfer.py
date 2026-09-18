"""Render a Chinese summary from frozen pilot artifacts; never calls a model."""
import argparse
import json
from pathlib import Path
from statistics import mean


def render(directory):
    directory = Path(directory)
    rd = lambda name: json.loads((directory / name).read_text(encoding='utf-8'))
    summary, audit, manifest = rd('summary.json'), rd('independent_audit.json'), rd('manifest.json')
    roots, local, groups = rd('roots.json'), rd('local.json'), rd('group_results.json')
    items = {i['id']: i for i in manifest['items']}
    def pct(value):
        return '缺失' if value is None else f'{value * 100:.2f}%'
    def pp(value):
        return '缺失' if value is None else f'{value * 100:+.2f} 个百分点'
    lines = ['# 固定证据下的 confidence 分配：首轮 pilot', '',
             '状态：已完成。' if summary['empirical'] else '状态：模拟结果，不构成模型实验证据。', '',
             '## 设计与范围', '',
             '8 道局部训练题、8 道独立群体验证题，每题 6 个平级 Luna 成员；真实私人材料初答，'
             '更新时完整披露审计事实。只交换一名初答正确者与错误者的 .95/.55，另外四人 .75。'
             '群体第一轮干预分数、第二轮隐藏分数。按完整信息真值标记初答正确性，'
             '私人信息下的事后劣选不自动属于推理错误。', '',
             '冻结协议见 `PROTOCOL.md`。本轮仅检验可核验、完整披露的加法效用任务，'
             '不覆盖自由讨论的信息遗漏、真假证据冲突或人类群体行为。', '',
             '## 调用与独立检查', '',
             f"共 {summary['usage']['requests']} 次调用，{summary['usage']['valid']} 次有效；"
             f"已报告费用 ${summary['usage']['known_cost_usd']:.6f}，"
             f"{summary['usage']['unknown_cost_requests']} 次费用未知。",
             f"完整初始状态 {summary['roots_complete']} 个，其中 {summary['roots_mixed']} 个真实意见分歧。",
             f"全信息单模型对照：{audit['full_information_oracle']['correct']}/{audit['full_information_oracle']['n']} 正确。",
             f"初答符合题目私人信息期望效用规则：{audit['initial_matches_private_expected_utility_rule']['correct']}/"
             f"{audit['initial_matches_private_expected_utility_rule']['n']}。",
             f"独立审计通过：{audit['primary_local_pairs_checked']} 个严格局部配对；"
             f"{audit['synchronous_group_inputs_checked']} 次群体输入；预测文件先于群体调用："
             f"{audit['predictions_predate_group_calls']}。", '',
             '## 局部结果', '', '| 条件 | 有效调用 | 错误数（六名成员全部） |', '|---|---:|---:|']
    for arm in ('aligned', 'misaligned', 'equal', 'hidden'):
        rows = [r for r in local if r['arm'] == arm and r['answer'] is not None]
        lines.append(f"| {arm} | {len(rows)} | {sum(r['answer'] != items[r['item_id']]['truth'] for r in rows)} |")
    lines += ['', '上表为全部成员的描述统计；主要局部比较只用未被选中交换分数的四名成员。',
              f"主比较覆盖 {summary['local_primary']['n_items']} 道完整配对题，错误率差"
              f"（misaligned−aligned）为 {pp(summary['local_primary']['delta'])}。",
              '单题每条件只有一次响应，不能据此断言每道题的效应恒为零。若所有配对差均为零，'
              'bootstrap 得到的零宽区间只是样本退化，不是零效应等效性检验。', '',
              '| 条件 | 初答正确者：由对变错 | 初答错误者：改错 |', '|---|---:|---:|']
    for arm in ('aligned', 'misaligned', 'equal', 'hidden'):
        c = summary['local_transitions'][f'{arm}/initial_correct']
        w = summary['local_transitions'][f'{arm}/initial_wrong']
        lines.append(f"| {arm} | {pct(c['flip_rate'])}（n={c['n_member_responses']}） | {pct(w['flip_rate'])}（n={w['n_member_responses']}） |")
    lines += ['', '## 独立题群体结果', '', '| 轮次 | 正确方高分错误率 | 错误方高分错误率 | 隐藏分数错误率 | 配对差 |', '|---|---:|---:|---:|---:|']
    for t in (1, 2):
        rates = [summary['group_error_rates'].get(f'round{t}/{arm}', {}).get('mean') for arm in ('aligned', 'misaligned', 'hidden')]
        lines.append(f"| {t} | {' | '.join(pct(v) for v in rates)} | {pp(summary['group_primary'][f'round{t}']['delta'])} |")
    lines += ['', '第一轮是固定初始状态的分数干预；第二轮只让首轮答案继续传播。'
              '各条件均不按分数直接选最终答案。原始六人轨迹见 `group_results.json`。', '',
              '## 局部到群体预测', '',
              '预测在测试组调用前固定。两种逻辑回归都可使用完整材料效益差、自身前答、'
              '同伴意见比例及私人材料差值；confidence 模型额外使用显示分数特征。'
              '两轮预测均从初始状态递推，未使用测试首轮实际回答修正第二轮预测。', '',
              '| 轮次 | 含 confidence 的 Brier | 无 confidence 基线 | 差值（负值较好） |', '|---|---:|---:|---:|']
    for t in (1, 2):
        values = [summary['prediction_Brier'].get(f'round{t}/{name}') for name in ('confidence', 'no_confidence')]
        fmt = lambda v: '缺失' if v is None else f'{v:.6f}'
        diff = summary['prediction_Brier_paired_comparison'][f'round{t}']['confidence_minus_baseline']
        lines.append(f"| {t} | {fmt(values[0])} | {fmt(values[1])} | {fmt(diff)} |")
    lines += ['', 'Brier 衡量对 agent 实际选择的预测，不是供应商答案准确率。'
              '由审计事实直接计算最优方案的规则基线另见 `independent_audit.json`。'
              '若这个规则就足以预测全部行为，较高的预测准确度不能证明 confidence 动态已被识别。', '',
              '| 轮次 | confidence 模型预测的群体处理差 | 实测处理差 |', '|---|---:|---:|']
    for t in (1, 2):
        lines.append(f"| {t} | {pp(summary['predicted_treatment_contrasts'][f'round{t}/confidence'])} | {pp(summary['group_primary'][f'round{t}']['delta'])} |")
    lines += ['', '## 解释边界', '',
              '此 pilot 检验流程可运行性与初步响应。独立测试题只有 8 道；同题多个成员和多次调用不增加独立题目数。'
              '第二轮预测还依赖条件独立和一步记忆近似，并可能遇到训练中没有的全体一致状态。',
              '如果局部处理效应为零且更新正确率接近上限，目前可支持的结论是：'
              '在这一完整可核验的任务范围内，没有观察到 confidence 归属改变带来的稳定错误率变化。'
              '不能据此宣称其他任务没有效应，也不能把成功预测普遍纠错当成成功预测非零社会影响。', '',
              '后续设计应先明确需要研究的是证据可核验时的额外分数影响，还是无法直接核验时的建议采纳。'
              '后者需要另立信息结构与合理决策基准，不能与本轮结果合并。']
    if audit.get('round2_condition_triplets', 0) > 0 and audit['round2_identical_request_triplets'] == audit['round2_condition_triplets']:
        pos = lines.index('## 局部到群体预测')
        lines[pos:pos] = ['**第二轮输入核查：同题同成员的三条件请求全部相同。上述第二轮条件差不能作为 confidence 传播证据；逐条哈希核查见文末。**', '']
        lines += ['', '## 第二轮差异的输入核查', '',
                  f"第二轮全部 {audit['round2_condition_triplets']} 个“同题×同成员”组合中，"
                  '三种条件的请求哈希完全相同。第一轮状态已经相同，第二轮分数全部隐藏，'
                  '请求中没有保留条件名称或过去分数。',
                  '因此，第二轮条件间的少量错误数差异属于相同输入下的响应变动，'
                  '不能解释为首轮 confidence 影响的残留或传播。此结论由输入逐字节哈希核对支持，'
                  '不依赖对模型内部过程的猜测。']
    if summary['local_primary']['delta'] == 0 and summary['group_primary']['round1']['delta'] == 0:
        lines[4:4] = ['## 当前结论', '',
            '局部与独立群体首轮均未观察到分数归属造成的错误率差。'
            '完整证据披露后准确率接近上限，当前 pilot 未提供有辨识力的非零 confidence 效应。'
            '加入 confidence 特征的预测是否优于基线见下表；不能把预测普遍纠错当成预测社会影响。', '']
    target = directory / 'RESULTS_ZH.md'
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(str(target.resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    render(parser.parse_args().directory)
