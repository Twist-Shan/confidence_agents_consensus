> Historical workflow reference. Some defaults describe earlier experiments. Use the root README for the current demand task and reproducibility commands.

# Confidence Agents：实验最小仓库

按 [proposal](../Proposal/main.pdf) 实现置信度分配实验。Python 3.11+，运行时无第三方依赖。默认 mock，**不会调用 API**。

## 快速开始

在仓库根目录运行：

```powershell
python -m unittest discover -s tests -v
python -m confidence_agents plan
python -m confidence_agents run --smoke --out runs/mock-smoke
```

`configs/pilot.json` 保留七款模型；默认 pilot 为 `luna glm qwen`。
其他四款暂只登记候选 ID，真实运行时全部按 OpenRouter 目录校验，找不到就停止，不替换模型。
`--models luna` 可以仅选择一种模型。

## 真实调用

先通过交互输入把 key 放入当前 PowerShell 进程的环境变量；不写 `.env` 或其他文件：

```powershell
$secret = Read-Host 'OpenRouter API key' -AsSecureString
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
python -m confidence_agents check-models
python -m confidence_agents run --backend openrouter --smoke --models luna --out runs/live-luna-smoke --max-requests 124
Remove-Item Env:OPENROUTER_API_KEY
```

上面 `run` 会付费。三模型小规模验证最多 372 次；默认完整 pilot 最多 **5,760 次**：每模型初始 144、讨论 1,296、局部重放 480，共 1,920 次。
完整 pilot 命令：

```powershell
python -m confidence_agents run --backend openrouter --out runs/live-pilot
```

`--max-requests` 是当前运行目录的累计请求数上限，**不是美元预算**。max_tokens 默认 2,048，包含模型可能使用的推理 token；若频繁截断，应先调整配置再在新目录重跑。真实费用以供应商账单为准，summary 只汇总返回的 usage.cost，并报告缺失数量。

模型请求使用明确 ID，关闭供应商故障转移。不设置 temperature、seed、reasoning 时使用供应商默认值，相关行为可能不同，**当前配置不声称控制了推理强度**。可在各模型配置增加 `provider` 精确供应商 slug 和 `reasoning_effort`；后者必须通过目录校验。正式比较前应固定供应商、推理设置和可用的模型快照。默认模型别名不是永久版本锁定；每次真实运行保存目录快照、返回的模型/供应商信息及原始 response。账号权限和端点兼容性需小规模真实调用确认。

## 实验定义

- **C：持续展示**。六个同模型 agent，完全图。每个题目、每次重复仅生成一套独立初始回答 `(answer, reason, p_B)`，所有处理组复用。置信度直方图固定为 `[.95,.95,.55,.55,.55,.55]`。aligned / misaligned 分别均匀抽取与初始正确性最正向 / 最负向关联的配置，平局也随机；hidden 不展示分数。可在配置 arms 添加 random。
- 三轮同步更新；仅传任务、自身上轮答案、邻居上轮答案与展示分数。分数固定跟随 agent，不随答案切换重新分配。reason、私有 p_B、真值、历史记录和轮次不进入讨论提示。各 root 的邻居顺序固定，各组执行顺序随机。每组分配随机种子和初始响应均可追溯。
- **L：局部重放**。24 个冻结的合成上下文覆盖自身 A/B、度数 2–5、邻居全 A / 全 B / 平衡或近似平衡。三个高低分数组合、两个立场分配方向，加三个等分组和 hidden，共十个条件；每条件独立调用两次。提示只改变分数。L 的邻居答案是预设的，不是模型初始表现样本。
- 开发题库包含可精确验证的贝叶斯概率比较和模运算状态追踪，随机交换 A/B 选项；真值和验证中间量保存在 manifest，绝不发给模型。**这些题目尚未校准难度；不是正式 benchmark**，六个 agent 可能全对而缺少分歧。暂未实现逻辑蕴含题、P 脉冲实验或图结构对照。

## 输出与统计

每个运行目录包含：

| 文件 | 内容 |
|---|---|
| `manifest.json` | 配置、源码 hash、带真值题库、协议版本 |
| `catalog.json` | 真实运行所选模型的目录元数据 |
| `calls/*.json` | 请求正文、时间、完整响应和 usage、解析状态；无认证头 |
| `roots/*.json` | 冻结初始回答 |
| `group_results.json` | 各组逐轮答案、错误比例、共识、错误多数、反转及失败数 |
| `local_results.json` | 局部重放每次响应 |
| `summary.json` | 配对效应、题目聚类 bootstrap 描述区间、局部选择率、调用费用 |

主要效应为初始有分歧 root 上的 `W_misaligned(T) - W_aligned(T)`，先在每题内平均 eligible roots，再在题目间等权平均；正值表示误配增加错误。另报全 root 效应。全体一致的 root 不人为制造分歧，保留在全 root 描述中。3–3 平票不算错误多数。至少两个 eligible 题目才给 bootstrap 区间；pilot 区间只用于描述，不能支持正式结论或模型排行榜。当前 base_id 与 item_id 相同；若扩展同题多个变体，需先修改汇总按 base_id 聚类。

初始响应非法则整套 root 不进入讨论并计数；更新响应非法/截断则保持上轮答案并计数。该规则会影响估计，必须报告失败率；它不等同于模型主动坚持原答案。不会因为答案错误或格式错误重采样。现阶段 summary 的 L 结果是合并描述，正式拟合应使用逐条记录并控制上下文。

## 断点续跑与限制

重复同一命令会复用已有响应。配置、题库、源码或 backend 改变时拒绝复用目录；仅 CLI `--max-requests` 可提高以继续。mock 输出明确标记 `is_empirical=false`，不可当作模型结果。

网络错误或进程在请求途中退出可能已产生费用，因此保存 pending/unresolved 并停止，**不自动重发**。先核对 OpenRouter 记录再人工处理对应记录；不提供自动删除重试。并发写同一目录由 `.running` 排他锁阻止；异常断电留下锁时，先确认原进程已结束再移除锁。运行结束才生成汇总，中断时逐调用记录仍保留。API 响应缓存依赖本地磁盘，不能保证远端 exactly-once。

采样和组执行均为串行，便于审计；未实现高并发、美元硬限额、供应商专用 API 或真实联网集成测试。mock 用于流程验证，不模拟任何模型的能力。

API 实现依据：[OpenRouter API](https://openrouter.ai/docs/api_reference/overview)、[供应商路由](https://openrouter.ai/docs/guides/routing/provider-selection)、[推理参数](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)。

## 难度校准

```powershell
python -m confidence_agents.calibration --out runs/calibration-mock
python -m confidence_agents.calibration --backend openrouter --model luna --out runs/calibration-live-luna
```

真实运行仍从 OPENROUTER_API_KEY 读取密钥。默认 3 类题（模运算状态追踪、多假设贝叶斯更新、命题逻辑蕴含）× 4 个生成难度等级 × 2 个题目，每题独立采样 6 次，总计最多 144 次调用，最多 4 个题目并发。等级表示生成复杂度，并非已经验证的模型难度。真值由精确有理数运算或穷举求解，无模型裁判。

预先规定探索性推荐条件：在“题型×等级”层面，有效回答正确率 30%–85%、无效响应比例不超过 10%，且至少一题的六次有效回答存在对错分歧。只根据独立初始回答校准，不观察置信度处理效果；不重采样直到满意。无效响应不当成错误或分歧，单独计数。

每层只有两个题，结果只能用于探索。输出的 `holdout_candidates.json` 使用新 seed 生成推荐层的新题，状态为未验证；不能直接称为已校准正式题库。需在新题及全新初始采样上复核，并固定正式题库后再做 confidence 干预。校准按模型分别成立，Luna 的难度结果不能直接推广到 GLM/Qwen。当前 `run` 仍使用原开发题库，不会自动替换为候选题。

复核已冻结的独立题库（先精确检查题目、真值及验证信息，仅运行文件中的题）：

```powershell
python -m confidence_agents.calibration --backend openrouter --model luna --bank runs/calibration-luna-20260918/holdout_candidates.json --out runs/validation-luna-logic-20260918 --max-requests 24
```

这个文件包含 L1、L2 各两题，每题仍回答六次。复核不改写原候选文件，不因复核结果继续自动生成或调用下一批题；统计阈值保持与首次校准一致。

已冻结的 20 题 L2 扩样题库为 `data/logic-l2-expansion-20260920.json`（20260920 是 seed）。按同一流程运行：

```powershell
python -m confidence_agents.calibration --backend openrouter --model luna --bank data/logic-l2-expansion-20260920.json --out runs/expansion-luna-logic-l2-20260920 --max-requests 120
```

该题库未按模型表现筛选，包含 3 道“蕴含”、17 道“不蕴含”；报告应按语义答案分层，不仅给出总正确率。已有运行结果的目录受 manifest 校验保护，换参数或代码版本时使用新输出目录。

### 平衡题库

`balanced_bank` 仅使用精确真值构建题库，不读取任何模型响应。从固定 seed 的候选序列中按顺序填满两类配额，再在每类内随机平衡正确选项 A/B。冻结文件保存候选取舍审计记录，已存在时拒绝覆盖。

```powershell
python -m confidence_agents.balanced_bank --out data/logic-l2-balanced-20260921.json
python -m confidence_agents.calibration --backend openrouter --model luna --bank data/logic-l2-balanced-20260921.json --out runs/balanced-luna-logic-l2-20260921 --max-requests 240
```

默认共 40 道 L2 独立题：“蕴含/不蕴含”各 20 道，每类 A/B 正确选项各 10 道，每题 6 次回答。仍沿用原来的模型设置、提示词和 2,048 token 上限。平衡的是题库，不是六个 agent 的答案。目标分布从原来的自然生成分布改为两类等权；分析应分层报告，不能把总体正确率变化直接解释成模型能力变化。

### 输出可靠性配置

`configs/luna-reliable.json` 提供 Luna 的新配置：8,192 token 上限、显式 medium 推理强度、严格 JSON Schema。原配置和历史结果不变。曾发生输出失败的八道题保存在 `data/luna-reliability-stress-20260921.json`：

```powershell
python -m confidence_agents.calibration --config configs/luna-reliable.json --backend openrouter --model luna --bank data/luna-reliability-stress-20260921.json --out runs/reliability-luna-8192-json-20260921 --max-requests 48
```

该配置在这轮 48 次压力测试中没有截断或格式错误，不保证以后不失败。新请求没有超过旧 2048 上限，因此不能将零截断归因于单独增加预算。它是配置组合的可用性验证，不是修补旧实验，也不是无偏的难度比较。若用新配置跑完整题库，指定新输出目录及对应调用上限（40×6 为 240）。各处理组必须统一配置。

## 四组局部 confidence 对照

```powershell
python -m confidence_agents.local_replay --out runs/local-four-arm-mock
python -m confidence_agents.local_replay --backend openrouter --out runs/local-four-arm-luna-20260922 --max-requests 480
```

默认使用冻结的 40 题平衡题库和 luna-reliable 配置，每题四组、每组三次，共 480 调用。每题只有一个实际接收者调用，四条同伴报告和自身上一轮答案均为预设；不是六个真实 agent 互相讨论。本地 degree=4，固定两条正确和两条错误报告，在每个语义真值×A/B 正确选项层内平衡自身初始正确/错误。

`correct_high` 给正确报告 .95、错误报告 .55；`wrong_high` 对调分数；`equal` 全部 .75；`hidden` 隐藏分数。题目、报告内容、身份、顺序及自身答案在组间固定，每题十二次请求的组别及重复顺序预先打乱。预先固定的上下文和分析规则写入 manifest，再开始调用。

主要效应是 wrong_high 与 correct_high 的错误选择概率差，在两组各三次回答均有效的题内配对、题间等权。另报逐组失败率、所有完成题的缺失响应最坏/最好情况界限，以及语义答案、自身初始正确性和正确选项的分层描述。区间为按题聚类且保持语义/选项/自身状态分层的配对 bootstrap（2000 次），只作探索性描述。不同组的重复调用不是配对随机种子，配对单位是冻结题目上下文。

`equal` 与 `hidden` 为次要描述性对照，不作多重未经校正的确认性结论。两条正确/两条错误使答案票数持平，因此主要比较不会把票数变化误当 confidence 变化。当前提示明确告知报告可能出错，分数不是保证；结论只对应此提示。不会根据干预效果筛题或追加采样。

## 八组 confidence 分差探索

```powershell
python -m confidence_agents.confidence_sweep --out runs/confidence-gap-mock
python -m confidence_agents.confidence_sweep --backend openrouter --out runs/confidence-gap-luna-20260918 --max-requests 960
```

固定 40 题、每组 3 次，共 960 调用。三组高低分为 .80/.70、.90/.60、.95/.55，每组均交换正确方与错误方的高分身份；另有全部 .75 和隐藏分数，共八组。分数均值固定为 .75。上下文沿用四组实验的 seed 20260922，日期样式 seed 不代表运行日期。所有条件统一增加定义：confidence 表示同伴对自己所选答案正确的报告概率。新旧实验提示不同，结果不直接合并。

主要指标为每题三个分差下的“错误方高分减正确方高分”的错误率差对分差的最小二乘斜率，再按题等权平均。仅纳入六个相关条件均有三次有效回答的题；单位为每增加 1.0 分差的错误概率变化。使用按语义真值、正确选项和预设自身正确性分层的题级 bootstrap 2000 次给出描述性区间。等分条件不作为人为零效应点塞入回归。

三个分差的成对效应、缺失响应界限及 equal/hidden 对照全部报告，各分差区间未进行多重比较校正。题库已用于探索，本轮也属于探索性实验，不以出现显著结果为停止条件。失败请求保留记录，不自动重发。运行前冻结 manifest 和源码哈希；模拟结果仅用于验证管线。

## 真实初答、分散信息与局部到群体预测

协议见 [TRANSFER_PROTOCOL.md](../TRANSFER_PROTOCOL.md)，文献区别见 [RELATED_WORK_AND_CLEAN_TASK.md](../RELATED_WORK_AND_CLEAN_TASK.md)。此版本与之前预设自身/同伴答案的逻辑题实验分别分析。

```powershell
python -m confidence_agents.confidence_transfer --directory runs/transfer-mock-example --backend mock
python -m confidence_agents.confidence_transfer --directory runs/supplier-transfer-new --backend openrouter
python scripts/audit_supplier_transfer.py runs/supplier-transfer-luna-20260918
```

固定 8 道训练题、8 道测试题，每题六个平级成员。初答由真实私人材料调用产生；更新时完整披露固定审计事实，在一名正确同伴和一名错误同伴间交换 .95/.55，另外四名保持 .75。局部四条件、群体三条件两轮，总计最多 592 次；第二轮不显示分数。预测模型只使用训练题，独立测试组的两轮预测在群体调用前保存。无 confidence 预测基线使用相同训练回答。

API key 可通过隐藏交互输入或 OPENROUTER_API_KEY 环境变量提供，不写入实验文件。源码、题目及配置哈希被冻结；同目录续跑复用已完成记录，失败或状态未明请求不自动重发。确认不存在活跃运行进程后，才可处理意外中断留下的 `.running` 锁。缺失初答或更新不以旧答案填补。

独立审计从原始请求核对证据、真实初答、分数交换、同步更新及预测保存时间，并独立解码响应重算群体错误率。模拟结果仅用于验证管线。当前任务完整材料可核验，不能代表自由讨论中的信息遗漏或人类群体行为。

已完成的首轮结果位于 `runs/supplier-transfer-luna-20260918/RESULTS_ZH.md`；对应原始源码保存在该目录的 `frozen_source`。后续修复了并发返回顺序引起的浮点累加差异，原始预测保持不变，检查记录在 `maintenance_note.json`。源码版本不同会拒绝复用原运行目录；新实验应使用新目录。中文报告可用 `python scripts/report_supplier_transfer.py runs/supplier-transfer-luna-20260918` 从保存结果重新生成，无 API 调用。

## 带噪声需求预测与证据可见性

协议见 [SIGNAL_VISIBILITY_PROTOCOL.md](../SIGNAL_VISIBILITY_PROTOCOL.md)。16 道预先平衡实际高/低需求的任务，每人三条 60% 准确信号；比较完整原始证据与仅见建议。每题从六名真实初答成员中，选两名意见相反者交换 .60/.771429，再对另外两名接收者做局部重放。四个分数组、两信息条件、两重复，最多 608 次请求。

```powershell
python -m confidence_agents.signal_visibility --directory runs/signal-visibility-mock-example --backend mock
python -m confidence_agents.signal_visibility --directory runs/signal-visibility-new --backend openrouter
python scripts/audit_signal_visibility.py runs/signal-visibility-luna-20260919
python scripts/report_signal_visibility.py runs/signal-visibility-luna-20260919
```

主指标为高分从 A 方移向 B 方时自报 P(B) 的变化，以及该变化在 advice 与 full 条件之间的差值。按题配对、在实际需求层内 bootstrap。初答理由不传播，同伴自报原始 p_B 不单独泄漏；两条件仅差原始信号字段。两名接收者都不属于分数交换对象，其可见分数集合保持固定。真实状态不进入提示。

后验采用精确分数计算。Brier 针对实际状态；与完整信息后验的距离在 advice 条件下还包含信息缺失。自报概率不等同于内部信念，响应分数不自动说明有害依赖。此版本只测局部更新，不包含六人完整多轮讨论。原始源码和协议随运行冻结，凭据不保存；模拟数据与真实数据独立存储。

## 逻辑题新题复核与缓存统计

`scripts/prepare_gap_replication.py` 离线构建 seed 20260923 的 40 道新题，独立枚举复核真值，并核对已有题库和 manifest 中的规范化子句/查询组合无重复。保留旧分差实验的模型、提示、分数、上下文生成种子和分析方法，仅替换题库；冻结结果到 `runs/confidence-gap-replication-luna-20260923/manifest.json`。准备脚本拒绝覆盖已有题库。

```powershell
python scripts/prepare_gap_replication.py
python scripts/run_gap_replication.py
python scripts/report_gap_replication.py
python scripts/audit_cache.py
```

运行脚本交互式读取 API key，仅存于进程环境。固定最多 960 个不同请求，连接失败保留为缺失且不重发；账户错误停止运行。已完成请求复用原始记录，不增加重复样本。新旧题结果单独报告，不合并替代独立复核。缓存报告汇总所有真实请求的 `cached_tokens`，缺失字段单列未知；模拟请求排除。报告写入 `runs/CACHE_REPORT.md` 和各实验目录。
