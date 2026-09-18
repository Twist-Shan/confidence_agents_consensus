# Luna 输出截断与格式失败：诊断及验证

运行日期：2026-09-18。结论：旧配置的八次截断均发生在隐藏推理阶段；新的 8192 token + medium + strict JSON 配置在本次 48 次压力测试中全部有效。有限样本零失败不能保证以后不截断，且本轮不能分离各项改动的作用。

## 原始失败证据

平衡题库的 240 次调用中有 8 次 finish_reason=length。每次 usage.completion_tokens=2048，completion_tokens_details.reasoning_tokens=2048，message.content=null。不是可见理由太长，而是 2048 的推理与输出共享额度在产生最终答案前耗尽。

另两条 finish_reason=stop 的回答把 p_B 写成了 `1.`，不是合法 JSON；这属于格式错误，与截断分开处理。旧模型目录快照记录 Luna 默认 reasoning effort 为 medium。

## 修改

- 新配置文件：configs/luna-reliable.json，保留原 configs/pilot.json。
- max_tokens 从 2048 增至 8192，给隐藏推理与最终答案留出余量。
- 显式设置 reasoning.effort=medium，固定原目录声明的默认强度；不能保证先前供应商内部每项默认行为完全等同。
- 开启 strict JSON Schema，初始响应必须含 answer、reason、p_B，更新响应仅 answer；限制 A/B 和 p_B 范围，禁止多余属性。发送前校验目录能力，供应商 require_parameters=true，禁止静默忽略。
- 新增逐调用 failure_category，区分 output_token_limit、invalid_answer_format、refusal 和 non_stop_finish。
- 不自动重采样、不拼接截断输出、不把失败视为错误答案。旧日志及旧统计未改写。

20 项自动化测试通过，包括严格 schema 的请求正文及即使截断内容看似可解析也不接受的行为。

## 验证范围及结果

从旧运行中选择所有曾有无效响应的 8 道题，每题全新调用 6 次，共 48 次。选择依据是输出失败，不是正确性；这是有意针对困难输出情形的测试，不代表全部题库的随机样本。

| 指标 | 旧记录：相同八道题 | 新压力测试 |
|---|---:|---:|
| 调用数 | 48 | 48 |
| 有效响应 | 38 | 48 |
| 截断 | 8 | 0 |
| 格式失败 | 2 | 0 |
| 输出 token 最大值（含推理） | 2048 | 1897 |
| 输出 token 中位数 | 1016.5 | 1021.5 |
| API 报告费用 USD | 0.0734568 | 0.0674136 |

新运行约 152.2 秒，48 次响应均报告供应商 OpenAI，全部 finish_reason=stop。

本次新输出没有一条超过 2048 token。因此，虽然旧截断的直接原因确实是额度耗尽，本轮零截断**不能证明**单独提高上限产生了改善；采样随机性、显式推理参数和 schema 都可能影响生成行为。旧八题也是按已发生失败选择的，不应把 8/48→0/48 作为无偏失败率改善估计。费用差异同样不能作为节省费用的证明。

新有效回答中 26/48 正确，6/8 个完整组有分歧。因为题目按旧失败筛选、配置也改变，这些数值仅描述压力测试，不能与整套 40 题的难度指标混算。summary 的通用 recommended_exploratory 标记不构成正式难度复核。

## 建议使用方式

后续小规模实验可优先使用 8192 + medium + strict JSON 这套配置，所有处理组统一设置。在独立新题或完整冻结题库上重新记录成功率和难度；保留 finish_reason、reasoning_tokens 和调用费用，观察 token 尾部需求。若再次接近上限或截断，在新配置中提高预算并统一复核，不针对某个处理组单独追加重试。

8192 只是当前工程上可测试的余量，不是已证实的最小安全上限。max_tokens 是上限，实际 token 使用量与账单另行记录。降低 reasoning effort 虽可能减少推理量，也会改变解题能力及实验难度，不宜只为消除失败而静默调整。

依据：[OpenAI reasoning 文档](https://developers.openai.com/api/docs/guides/reasoning)、[OpenRouter reasoning tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)、[OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)。
