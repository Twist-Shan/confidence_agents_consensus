"""Offline independent bank and frozen exact-protocol replication manifest."""
import json
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from confidence_agents.balanced_bank import build
from confidence_agents.calibration import load_frozen_bank
from confidence_agents.design import digest
from confidence_agents.experiment import source_hash
from confidence_agents.local_replay import contexts
from confidence_agents.runtime import save

directory=Path('runs/confidence-gap-replication-luna-20260923')
bank_path=Path('data/logic-l2-gap-replication-20260923.json')
assert not directory.exists() and not bank_path.exists(), 'Refuse overwrite'
def fingerprint(task):
    p=task['problem']
    if p['kind']!='logic':
        return digest(p)
    return digest([p['variables'],p['query'],sorted(set(tuple(sorted(set(c))) for c in p['clauses']))])
old=[]
for path in Path('data').glob('*.json'):
    doc=json.loads(path.read_text(encoding='utf-8'))
    old.extend(doc.get('tasks',[]))
for path in Path('runs').glob('*/manifest.json'):
    doc=json.loads(path.read_text(encoding='utf-8'))
    old.extend(t for t in doc.get('tasks',[]) if isinstance(t,dict) and 'problem' in t)
    old.extend(c['task'] for c in doc.get('contexts',[]) if 'task' in c)
seen={fingerprint(t) for t in old if 'problem' in t}
document=build(seed=20260923)
assert all(fingerprint(t) not in seen for t in document['tasks']), 'Overlap: do not silently change seed'
assert len({fingerprint(t) for t in document['tasks']})==40
# Independent bit-mask implementation verifies every truth against the generator.
for t in document['tasks']:
    p=t['problem']; satisfying=[]
    for mask in range(1<<p['variables']):
        lit=lambda x: bool(mask & (1<<(abs(x)-1))) == (x>0)
        if all(any(lit(x) for x in clause) for clause in p['clauses']):
            satisfying.append(lit(p['query']))
    assert satisfying
    assert ('Yes' if all(satisfying) else 'No')==t['options']['AB'.index(t['truth'])]
document['status']='frozen-independent-replication'
document['sampling_plan']={'conditions':8,'repeats_per_condition':3,'maximum_calls':960,
                           'model':'openai/gpt-5.6-luna','max_tokens':8192,'reasoning_effort':'medium',
                           'workers':4,'selection':'Exact truth quotas only, no model outcomes'}
document['nonoverlap_audit']={'previous_unique_problem_fingerprints':len(seen),'overlaps':0,
                             'canonicalization':'Sorted literals and unique sorted clauses; variable names and query preserved',
                             'independent_bitmask_truth_checks':40}
save(bank_path,document)
bank,_,bank_hash=load_frozen_bank(bank_path)
manifest=json.loads(Path('runs/confidence-gap-luna-20260918/manifest.json').read_text(encoding='utf-8'))
manifest.update(source_hash=source_hash(),bank_hash=bank_hash,contexts=contexts(bank,manifest['seed']),
                study_role='Independent new-item replication of frozen eight-condition design',
                replication_of='runs/confidence-gap-luna-20260918',bank_file=str(bank_path),
                missing_policy='Transport failures retained as missing; never resend; account errors stop run',
                fixed_maximum_calls=960)
save(directory/'manifest.json',manifest)
print(json.dumps({'directory':str(directory),'bank':str(bank_path),
                  'counts':dict(Counter(t['options']['AB'.index(t['truth'])]+'/'+t['truth'] for t in bank)),
                  'audit':document['nonoverlap_audit']},indent=2))
