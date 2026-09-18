"""Summarize provider-reported cache usage; unknown fields are not zero hits."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.runtime import save

result={}
for folder in Path('runs').iterdir():
    if not folder.is_dir():
        continue
    records=[json.loads(p.read_text(encoding='utf-8')) for p in folder.rglob('calls/*.json')]
    live=[r for r in records if r.get('backend')=='openrouter']
    if not live:
        continue
    usages=[r['response'].get('usage',{}) for r in live if r.get('status')=='complete']
    details=[u.get('prompt_tokens_details') or {} for u in usages]
    known=[d for d in details if d.get('cached_tokens') is not None]
    prompts=[u['prompt_tokens'] for u in usages if u.get('prompt_tokens') is not None]
    prompt_costs=[u.get('cost_details',{}).get('upstream_inference_prompt_cost') for u in usages]
    output_costs=[u.get('cost_details',{}).get('upstream_inference_completions_cost') for u in usages]
    cached=sum(d['cached_tokens'] for d in known)
    hits=sum(d['cached_tokens']>0 for d in known)
    result[folder.name]={'request_records':len(live),'complete_responses':len(usages),
                         'cache_field_known':len(known),'cache_field_unknown':len(live)-len(known),
                         'cache_hit_requests':hits,'hit_rate_known':hits/len(known) if known else None,
                         'prompt_tokens':sum(prompts),'cached_tokens':cached,
                         'input_token_range':[min(prompts),max(prompts)] if prompts else None,
                         'known_input_cost_usd':sum(x for x in prompt_costs if x is not None),
                         'known_output_cost_usd':sum(x for x in output_costs if x is not None)}
save('runs/cache-audit.json',result)
lines=['# API 缓存统计','',
       '统计 OpenRouter 原始响应的 usage.prompt_tokens_details.cached_tokens；缺失字段和未完整返回的请求计为未知，不计为零命中。所有 mock 请求排除。','',
       '| 实验 | 有缓存字段的响应 | 命中请求 | 缓存 token | 输入 token 范围 | 未知请求 |',
       '|---|---:|---:|---:|---|---:|']
for name,r in result.items():
    lines.append(f"| {name} | {r['cache_field_known']} | {r['cache_hit_requests']} | {r['cached_tokens']} | {r['input_token_range']} | {r['cache_field_unknown']} |")
lines.extend(['','旧分差实验每次输入 553–603 tokens，低于 GPT-5.6 系列官方文档所述的 1024 可见输入 token 缓存门槛。该实验已知输入成本 $0.1126826，输出成本 $1.1014116；约 90.7% 为输出成本。',
              '官方说明：https://developers.openai.com/api/docs/guides/prompt-caching',
              '提示缓存复用输入计算，模型仍生成新输出。仓库的断点续跑另有本地结果复用：同一个 call_id 不重复发送；每个条件与重复编号有独立 call_id，不将一次回答复制为多个重复样本。',''])
Path('runs/CACHE_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if 'gap' in k},indent=2))
