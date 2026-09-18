"""Resume only never-sent requests; preserve unresolved requests as missing."""
import getpass
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.confidence_sweep import ARMS, messages, summarize
from confidence_agents.design import digest, rng
from confidence_agents.experiment import source_hash
from confidence_agents.runtime import Calls, save


def main(directory='runs/confidence-gap-luna-20260918'):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_hash']==source_hash(), 'Source changed'
    assert manifest['protocol']=='confidence-gap-eight-arm-v1'
    assert manifest['arms']==list(ARMS)
    os.environ['OPENROUTER_API_KEY']=getpass.getpass('OpenRouter key: ')
    lock=directory/'.running'
    with lock.open('x'):
        pass
    try:
        before=list((directory/'items').glob('*/calls/*.json'))
        assert len(before)<=960
        save(directory/'continuation.json',{'policy':'Never resend any existing request, including unresolved; all failed requests treated as missing',
                                         'existing_records_before_continuation':len(before),'source_hash':source_hash()})
        stop=threading.Event()
        def sample(context):
            task=context['task']; folder=directory/'items'/task['id']
            calls=Calls(folder,'openrouter',24,manifest['max_tokens'])
            order=[(arm,rep) for arm in ARMS for rep in range(3)]
            rng(manifest['seed'],task['id'],'cell-order').shuffle(order)
            rows=[]
            for arm,rep in order:
                if stop.is_set():
                    break
                call_id=f"local/luna/{task['id']}/{arm}/{rep}"
                path=folder/'calls'/(digest(call_id)+'.json')
                if path.exists() and json.loads(path.read_text(encoding='utf-8'))['status']!='complete':
                    parsed=None
                else:
                    try:
                        parsed=calls.ask(call_id,manifest['model'],messages(context,arm))
                    except Exception:
                        if not path.exists():
                            stop.set()
                            raise
                        record=json.loads(path.read_text(encoding='utf-8'))
                        # Stop on account errors or programming failures. Only transport
                        # failures can be retained as missing while continuing the grid.
                        if record.get('error_type') not in ('IncompleteRead','TimeoutError','URLError','RemoteDisconnected','ConnectionResetError'):
                            stop.set()
                            raise
                        parsed=None
                answer=parsed['answer'] if parsed else None
                rows.append(dict(item_id=task['id'],semantic=context['semantic'],truth=task['truth'],
                                 own=context['own'],own_correct=context['own_correct'],arm=arm,repeat=rep,
                                 answer=answer,wrong=answer!=task['truth'] if answer is not None else None))
                save(folder/'results.json',rows)
            return rows
        order=manifest['contexts'][:]; rng(manifest['seed'],'task-order').shuffle(order)
        rows=[]
        with ThreadPoolExecutor(max_workers=manifest['workers']) as pool:
            for i,future in enumerate(as_completed([pool.submit(sample,c) for c in order]),1):
                rows.extend(future.result())
                save(directory/'progress.json',{'items_completed':i,'items_planned':40,'rows':len(rows)})
                print(f'Completed {i}/40 contexts',flush=True)
        assert len(rows)==960
        rows.sort(key=lambda r:(r['item_id'],r['arm'],r['repeat']))
        save(directory/'results.json',rows)
        result=summarize(rows,3,'openrouter',manifest['seed'])
        records=[json.loads(p.read_text(encoding='utf-8')) for p in (directory/'items').glob('*/calls/*.json')]
        assert len(records)==960
        costs=[r.get('response',{}).get('usage',{}).get('cost') for r in records]
        result['usage']={'requests':len(records),'reported_cost_usd':sum(c for c in costs if c is not None),
                         'requests_without_cost':sum(c is None for c in costs)}
        save(directory/'summary.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='gap_contrasts'},indent=2))
    finally:
        lock.unlink(missing_ok=True)


if __name__=='__main__':
    main()
