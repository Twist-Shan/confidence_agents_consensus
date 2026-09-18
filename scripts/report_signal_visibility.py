"""Chinese report and deterministic examples from frozen noisy-demand artifacts."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
from statistics import mean


def render(directory):
    directory = Path(directory)
    rd = lambda n: json.loads((directory / n).read_text(encoding='utf-8'))
    summary, audit, manifest = rd('summary.json'), rd('independent_audit.json'), rd('manifest.json')
    roots, rows = rd('roots.json'), rd('updates.json')
    items = {i['id']: i for i in manifest['items']}
    def pp(x):
        return '缺失' if x is None else (f'{100*x:+.6f}' if 0 < abs(100*x) < .001 else f'{100*x:+.2f}')
    def interval(x):
        if x is None:
            return '缺失'
        digits = 6 if max(abs(y) for y in x) < .00001 else 3
        return f'[{100*x[0]:+.{digits}f}, {100*x[1]:+.{digits}f}]'
    def number(x):
        return '缺失' if x is None else f'{x:.6f}'
    def percent(x):
        return '缺失' if x is None else f'{100*x:.2f}%'
    primary = summary['primary']
    interaction = primary['interaction']
    ci = interaction['descriptive_item_bootstrap_95pct']
    if ci is None:
        conclusion = '有效配对题不足，尚不能判断信息条件差异。'
    elif ci[0] > 0:
        conclusion = '本 pilot 中，仅见建议时的分数归属效应更大；交互的描述性题级区间位于零以上。独立新题复核尚未完成。'
    elif ci[1] < 0:
        conclusion = '本 pilot 中，仅见建议时的分数归属效应反而更小；交互的描述性题级区间位于零以下。原因未查明，独立新题复核尚未完成。'
    else:
        conclusion = '两种信息条件的分数归属效应差异尚不明确；交互的描述性题级区间包含零。'
    if manifest.get('replication_of'):
        conclusion = conclusion.replace('本 pilot 中', '本次固定协议的新实例复核中').replace('独立新题复核尚未完成。', '')
    lines = ['# 带噪声需求预测：证据可见性与 confidence 分配', '',
             '**真实模型实验。**' if manifest['backend'] == 'openrouter' else '**模拟结果，不构成模型证据。**', '',
             '## 当前结论', '', conclusion,
             '主指标衡量自报概率的定向变化，不能直接解释为内部信任、非理性或性能改善。', '',
             '## 设计', '',
             '16 个市场实例，真实高/低需求各 8 个。六名平级 Luna 分析员每人获得 3 条准确率 60% 的私人信号，'
             '先独立输出真实初答及 p_B。固定初答后，选定一名支持 A（低需求）者和一名支持 B（高需求）者交换 .60/.771429。'
             '从另外四人中预先抽两人作为接收者，每条件重复两次。',
             'full 显示全部原始信号；advice 只显示自己的信号与同伴建议。两信息条件共用相同初答，'
             '分数交换的两个条件共用同一分数集合。其他人的显示分数保持初答隐含置信度不变。'
             '另设选定两人等分、全体隐藏分数对照。',
             '本轮检验局部更新，共有六人真实初答，但不包含完整六人群体 rollout。冻结细节见 `PROTOCOL.md`。', '',
             '## 主要结果', '',
             '效应定义：把高分从支持 A 者移到支持 B 者后，P(B) 的平均变化。正值表示预测向高分建议移动。'
             '先在题内对两接收者、两重复平均，再题间等权；区间按 H/L 分层、以题配对 bootstrap 2000 次。', '',
             '| 比较 | 概率移动（百分点） | 描述性 95% 区间（百分点） | 完整配对题数 |',
             '|---|---:|---:|---:|']
    labels = {'full': '完整证据', 'advice': '仅见建议', 'interaction': '仅见建议减完整证据'}
    for key in ('full', 'advice', 'interaction'):
        p = primary[key]
        lines.append(f"| {labels[key]} | {pp(p['mean_p_B_shift'])} | {interval(p['descriptive_item_bootstrap_95pct'])} | {p['n_items']} |")
    lines += ['', '| 信息条件 | 选择 B 的比例变化（百分点） | 相同输入两次回答的平均概率绝对差 |', '|---|---:|---:|']
    for v in ('full', 'advice'):
        lines.append(f"| {labels[v]} | {pp(primary[v]['choose_B_shift'])} | {percent(summary['mean_absolute_same_input_repeat_difference'][v])} |")
    lines += ['', '重复间差异仅描述响应波动，不能直接当作处理效应的标准误。'
              '概率移动与是否跨过 0.5 决策阈值是不同指标。', '',
              '## 概率预测质量（次要描述）', '',
              '| 信息条件 | 分数组 | 有效响应 | 实际状态 Brier（越低越好） | 距完整后验 MSE | 实际状态分类准确率 |',
              '|---|---|---:|---:|---:|---:|']
    for v in ('full', 'advice'):
        for arm in ('B_high', 'A_high', 'pair_equal', 'hidden'):
            c = summary['cells'][f'{v}/{arm}']
            lines.append(f"| {labels[v]} | {arm} | {c['n_valid']} | {number(c['Brier_realized_state'])} | {number(c['MSE_full_information_posterior'])} | {percent(c['accuracy_realized_state'])} |")
    lines += ['', '完整后验是 full 条件的概率基准。advice 距完整后验的差异还包含信息缺失，'
              '不能全部称为推理错误。有限样本里，合理的概率预测也可能没有猜中实际需求；'
              '表中 Brier 差异未单独作确认性检验。', '', '## 逐题结果', '',
              '| 题号 | 完整证据效应（百分点） | 仅建议效应（百分点） | 交互（百分点） |', '|---|---:|---:|---:|']
    for row in summary['item_effects']:
        lines.append(f"| {row['item_id']} | {pp(row['full']['p_B_shift'])} | {pp(row['advice']['p_B_shift'])} | {pp(row['interaction'])} |")
    if roots:
        # Always choose the first eligible item and first preselected receiver, never the largest effect.
        item_id = sorted(roots)[0]
        root, item = roots[item_id], items[item_id]
        j = root['targets'][0]
        a, b = root['pair_A_B']
        high_count = item['signals'][j].count('high')
        advice_odds = Fraction(3, 2) ** (2 * high_count - 3)
        for k, forecast in enumerate(root['initial']):
            if k != j:
                advice_odds *= Fraction(81, 44) if forecast['answer'] == 'B' else Fraction(44, 81)
        advice_probability = float(advice_odds / (1 + advice_odds))
        lines += ['', '## 固定选取的实际例子', '',
                  f'按题号取首个纳入题 {item_id}，按预先记录顺序取接收者 member-{j}，不按效应大小选择例子。',
                  f"目标私人信号：{item['signals'][j]}；真实初答 {root['initial'][j]['answer']}，p_B={root['initial'][j]['p_B']:.4f}。",
                  f'分数在支持 A 的 member-{a} 与支持 B 的 member-{b} 之间交换。',
                  f"完整信息后验 P(B)={item['posterior_full']:.6f}；最终真实状态为 {item['state']}。", '',
                  f'若只看建议、忽略显示分数并假定所有同伴按三信号多数报告，参考 P(B)={advice_probability:.6f}。'
                  '这是已声明策略假设下的参考，不是对未知 LLM 通信策略的唯一规范答案。', '',
                  '| 信息条件 | A 获高分时平均 p_B | B 获高分时平均 p_B |', '|---|---:|---:|']
        for v in ('full', 'advice'):
            values = []
            for arm in ('A_high', 'B_high'):
                sub = [r['parsed']['p_B'] for r in rows if r['item_id'] == item_id and r['member'] == j and r['visibility'] == v and r['arm'] == arm and r['parsed'] is not None]
                values.append(mean(sub) if sub else None)
            lines.append(f"| {labels[v]} | {number(values[0])} | {number(values[1])} |")
    lines += ['', '## 数据完整性与边界', '',
              f"- {summary['eligible_mixed_roots']}/16 个初始状态有真实意见分歧；未补抽。",
              f"- {summary['usage']['requests']} 次请求，{summary['usage']['valid']} 次有效；已知费用 ${summary['usage']['known_cost_usd']:.6f}，{summary['usage']['unknown_cost_requests']} 次费用未知。",
              f"- 初答符合三信号多数策略：{audit['initial_majority_rule']['matches']}/{audit['initial_majority_rule']['valid']}；自报概率与私人后验平均绝对差 {audit['initial_private_posterior_mean_absolute_error']:.6f}。",
              f"- answer 与 p_B 阈值不一致的响应：{summary['answer_probability_inconsistencies']} 次，未在主分析中事后删除。",
              f"- 独立核对 {audit['score_swap_pairs']} 个分数交换配对、{audit['visibility_pairs']} 个信息可见性配对、{audit['identical_repeat_pairs']} 个重复请求配对。",
              '- 主效应已直接从原始 JSON 响应独立重算；真值未进入请求，原始源码哈希核对通过。',
              '- 仅使用一个模型、16 个任务和每条件两次重复。对新题和其他模型的泛化未验证。',
              '- 本设置是在前期探索后选定的发现性 pilot。即使本轮区间不含零，也应固定协议后在未见题上独立复核。',
              '- 显示 confidence 是受控报告分数；观察到响应不自动证明有害依赖。',
              '- 主要信息条件交互是预先规定的；逐题和预测质量表仅作解释与诊断。']
    target = directory / 'RESULTS_ZH.md'
    if manifest.get('replication_of'):
        lines = [line.replace('对新题和其他模型的泛化未验证。', '本轮只复核同一生成机制的新实例；其他任务机制及模型未验证。')
                 .replace('本设置是在前期探索后选定的发现性 pilot。即使本轮区间不含零，也应固定协议后在未见题上独立复核。',
                          '本批次按运行前固定的 REPLICATION_PLAN.md 独立复核；与发现批次分别报告，仍只有 16 个独立任务。')
                 for line in lines]
    target.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(str(target.resolve()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    render(parser.parse_args().directory)
