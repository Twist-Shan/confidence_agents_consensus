# From Confidence to Collective Judgment

English research notes integrating the original research question with all twelve completed pilot runs. This is the current reader-facing revision. It uses a plain, single-column article format and starts from the task rather than assuming multi-agent experience.

## Read

- `main.pdf`: compiled notes.
- `main.tex`: editable LaTeX manuscript.
- `figures/`: five vector PDF figures, including actual data plots.
- `prompts/`: literal saved prompt examples and outputs used in the manuscript.
- `prompt_examples.json`: five complete request objects with parsed outputs and source paths; no credentials.

The main text explains the demand task, one real item, the intervention, prompts, numerical results, limitations, and the remaining local-to-group test. Earlier logic and supplier task selection is in Appendix A; the run inventory, complete prompts, and revision decisions follow.

## Compile

From this directory, with TeX Live or a standard Overleaf project:

```sh
latexmk -pdf main.tex
```

Alternatively run `pdflatex main.tex` twice. Bibliography entries are included directly; no BibTeX step or custom class is required. Upload `main.tex`, `figures/`, and `prompts/` together to Overleaf.

## Regenerate figures and prompt examples

From the repository root:

```sh
python scripts/build_notes_assets.py
```

This reads saved experiment records, checks paired input changes, and writes the figures and prompt files. It uses ReportLab and does not make model requests. Numerical source records are in the two `runs/signal-visibility-*` directories named in the paper.

The original `Proposal/main.tex` and `Proposal/main.pdf` are retained for provenance. Superseded theory and old sample-size/budget commitments are not appended to these notes. The Chinese HTML/PDF draft in `Proposal/integrated` is an earlier presentation draft, not the final English manuscript.
