# Confidence Agents Consensus

Controlled experiments on **who receives displayed confidence**, and how access to peer evidence changes a language model's response.

**Start here:** [English research notes (PDF)](Proposal/notes/main.pdf) · [LaTeX source](Proposal/notes/main.tex) · [Exact prompt examples](Proposal/notes/prompt_examples.json) · [Evidence inventory](runs/README.md)

## What the experiment does

Six separately queried instances of the same model forecast demand for one market. Each initially sees three private noisy surveys. We save their real initial responses, exchange two confidence scores between opposing recommendations, and ask two other agents to update. Their evidence, initial opinions, identities, message order, and visible score collection stay fixed across the score swap.

We compare two information conditions:

- **Full evidence:** the recipient sees all peers' original surveys.
- **Advice only:** the recipient sees peers' recommendations and scores, but not their surveys.

The main outcome is the change in reported probability of high demand when the higher score moves from an A supporter to a B supporter. These are one-step updates, not a completed six-agent multi-round conversation. The longer-term question is whether local responses can predict collective outcomes on new items.

## Current evidence

| Saved batch | Eligible / planned markets | Valid / scheduled calls | Advice-only shift | Full-evidence shift |
|---|---:|---:|---:|---:|
| Discovery | 16 / 16 | 608 / 608 | +14.81 pp | -0.06715 pp |
| New-instance replication | 15 / 16 | 576 / 576 | +22.48 pp | +0.000176 pp |

`pp` means percentage points in reported P(high demand), **not accuracy**. One unanimous replication item was excluded under the frozen rule, without replacement. The records use `openai/gpt-5.6-luna`; other model families have not been tested in this evidence set. Model availability and pricing are not guaranteed by the historical configuration files.

The direction repeated within the same task generator. This does not establish irrationality, consistent harm, internal trust, or predictive multi-round group dynamics. The [notes](Proposal/notes/main.pdf) explain the design, worked example, uncertainty intervals, unsuccessful earlier experiments, and remaining tests.

## Layout

```text
confidence_agents/     Experiment runners, prompts, exact task verifiers, API adapter
configs/               Current reliable configuration and historical model candidates
data/                  Frozen task banks
runs/                  Twelve selected real runs, raw requests/responses and frozen sources
Proposal/notes/        Current English notes, figures, prompts and PDF
Proposal/              Original proposal, retained as a historical version
output/html/           Detailed Chinese HTML report
scripts/               Offline audits, reports, figure generation and historical utilities
tests/                 Offline unit tests
docs/                 Documentation map and historical workflows
```

The protocol Markdown files remain at the repository root because existing runners freeze copies of them. See the [documentation map](docs/README.md) for their roles. New runs, mock outputs, failed account-start attempts, temporary renders, duplicate exports, and LaTeX build caches are ignored by Git. The twelve included evidence directories are an explicit allowlist; their original records are retained.

## Install and verify offline

Python 3.11 or later. The experiment runtime and unit tests use only the standard library.

```sh
python -m pip install --no-deps -e .
python -m unittest discover -s tests -v
python scripts/audit_signal_visibility.py runs/signal-visibility-luna-20260919
python scripts/audit_signal_visibility.py runs/signal-visibility-replication-20260920
python scripts/compare_visibility_replication.py runs/signal-visibility-replication-20260920
```

These commands do not call a model. Audits independently decode saved responses, verify paired inputs and source hashes, and recompute effects and intervals. Some audit/report scripts rewrite their derived JSON or Markdown reports; raw requests are not overwritten. GitHub Actions runs these offline checks without API credentials.

To exercise the current runner with synthetic mock responses:

```sh
python -m confidence_agents.signal_visibility --backend mock --directory runs/demo-demand-mock
```

Mock responses test the pipeline only and must not be treated as empirical model results. Repeating a completed run command reuses its saved call records; use a fresh directory if the configuration or source has changed.

## Run a new paid experiment

Only `--backend openrouter` makes real model calls. It checks the configured model against the provider catalog and does not silently substitute another model. If `OPENROUTER_API_KEY` is unset, the runner requests it using hidden terminal input. Do not put credentials in source files or commits.

```sh
python -m confidence_agents.signal_visibility --backend openrouter --directory runs/my-demand-discovery
python -m confidence_agents.signal_visibility --backend openrouter --bank-seed 20260920 --replication-of runs/my-demand-discovery --directory runs/my-demand-replication
```

Each command schedules at most **608 requests**: 96 initial calls and up to 512 updates. Current settings are six initial agents, two recipients per eligible item, two evidence conditions, four score conditions, two samples per input, medium reasoning, strict JSON, and an 8192-token output cap. See [the protocol](SIGNAL_VISIBILITY_PROTOCOL.md).

The request cap is not a dollar spending cap. Network failures can occur after a charge; unresolved requests are preserved rather than automatically resent. Existing run directories enforce frozen manifests/source hashes. Do not run paid commands against the versioned evidence directories, remove locks while a process is active, or replace missing responses to obtain a preferred result.

`python -m confidence_agents run` and `configs/pilot.json` belong to the **earlier generic pilot**; they are not the current demand experiment. The [historical workflow reference](docs/legacy_workflows_zh.md) documents calibration, logic-score sweeps, and supplier experiments separately.

## Rebuild reports and manuscript

The detailed Chinese HTML uses saved records and standard-library Python:

```sh
python scripts/build_narrative_report_html.py
```

For English figures and literal prompt examples, install the optional report dependencies and regenerate assets:

```sh
python -m pip install -e ".[reports]"
python scripts/build_notes_assets.py
```

Then compile `Proposal/notes/main.tex` with a standard TeX Live installation, or upload `main.tex`, `figures/`, and `prompts/` to Overleaf:

```sh
cd Proposal/notes
latexmk -pdf main.tex
```

There is no custom LaTeX class or BibTeX step. Prebuilt vector figures and the PDF are included. The [notes README](Proposal/notes/README.md) explains the source bundle. Legacy Chinese PDF builders use local Windows fonts; the English notes and their asset builder do not require those fonts.

## Reproducibility boundaries

- New-instance replication is within one generator and one model ID. An API alias does not permanently pin a provider's implementation.
- Private probability, displayed confidence, realized-state accuracy, and group agreement are distinct quantities.
- The statistical unit is the market item; repeated calls and members are averaged within items.
- Real calls, mock calls, missing responses, and account failures are kept distinct.
- Initial states are reused across intervention branches. This is different from provider prompt-cache billing and does not replace independent repeated responses.
- Raw responses and frozen source snapshots are included so that reports can be checked without paying for new calls.

No license is assigned in this initial repository. The original proposal and early failures remain available for provenance; the current research narrative is the English notes.
