"""Run the frozen new-item replication with the audited no-resend runner."""
import json
from pathlib import Path
from resume_confidence_sweep import main
from confidence_agents.runtime import catalog, save

directory=Path('runs/confidence-gap-replication-luna-20260923')
manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
snapshot=catalog({'luna':manifest['model']})
if not (directory/'catalog.json').exists():
    save(directory/'catalog.json',snapshot)
main(directory)
summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
summary['note']='Independent new-item replication: 40 new balanced tasks; same frozen model settings, prompts, scores, context-generation seed and analysis. Secondary gap intervals unadjusted. Transport failures missing, never resent. Synthetic own and peer answers, single update.'
save(directory/'summary.json',summary)
