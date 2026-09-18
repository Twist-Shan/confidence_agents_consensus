# Documentation map

Start with the [repository README](../README.md) and the current [English notes](../Proposal/notes/main.pdf).

## Current experiment

- [Frozen demand protocol](../SIGNAL_VISIBILITY_PROTOCOL.md)
- [New-instance replication plan](../REPLICATION_PLAN_20260920.md)
- [Evidence inventory](../runs/README.md)
- [Exact prompt examples](../Proposal/notes/prompt_examples.json)
- [Detailed Chinese explanation](../output/html/confidence_agents_experiment_report_zh.html) — download the HTML to read it offline.

## Earlier design and task selection

- [Supplier protocol](../TRANSFER_PROTOCOL.md)
- [Supplier worked example](../SUPPLIER_TASK_EXAMPLE.md)
- [Literature and controlled-task design](../RELATED_WORK_AND_CLEAN_TASK.md)
- [Task-design alternatives](../TASK_DESIGN_OPTIONS.md)
- [Original proposal](../Proposal/main.pdf) — historical version, not the current status report.
- [Historical commands and settings](legacy_workflows_zh.md) — preserves the previous README; use the root README for current defaults.

## Script guide

| Purpose | Entry point | Makes API calls? |
|---|---|---|
| Current demand experiment | `python -m confidence_agents.signal_visibility` | Only with explicit `--backend openrouter` |
| Audit main evidence | `scripts/audit_signal_visibility.py` | No |
| Compare discovery and replication | `scripts/compare_visibility_replication.py` | No |
| Check new-bank generation against frozen source | `scripts/check_visibility_replication.py` | No |
| Regenerate per-run Chinese reports | `scripts/report_signal_visibility.py` | No |
| Generate English figures and exact prompts | `scripts/build_notes_assets.py` | No |
| Generate the full Chinese HTML report | `scripts/build_narrative_report_html.py` | No |
| Earlier calibration / local replay / score-gap tests | `confidence_agents.calibration`, `local_replay`, `confidence_sweep` | Backend-dependent; mock is default |
| Earlier supplier experiment | `confidence_agents.confidence_transfer` | Backend-dependent; mock is default |
| Historical live-run recovery helpers | `scripts/run_gap_replication.py`, `resume_confidence_sweep.py`, `recover_local_replay.py` | May make paid calls; not report generators |

Run commands from the repository root. Historical report builders are retained for provenance; `build_integrated_proposal.py` produces the superseded Chinese presentation draft, while `build_experiment_report.py` and `build_experiment_report_html.py` produce earlier report layouts. The current manuscript is `Proposal/notes/main.tex`.
