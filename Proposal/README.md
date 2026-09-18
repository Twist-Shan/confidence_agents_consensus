# From Confidence to Consensus
## Collective Decision Dynamics of LLM Agents

English research proposal, prepared 17 September 2026.

### Files
- `main.tex`: standalone, plain single-column LaTeX article.
- `references.bib`: 25 primary references, with version-pinned arXiv records where relevant.
- `main.bbl`: prebuilt bibliography for convenient compilation.
- `main.pdf`: compiled proposal (18 pages, including proofs, prompts, and references).
- `reference_audit.md`: source-use notes and the boundaries of the literature comparison.

Only `main.tex` and `references.bib` are needed to rebuild from source. No custom template, external figures, or bundled fonts are required.

### Compile
Use pdfLaTeX on Overleaf, with `main.tex` as the main document. Locally:

```sh
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

The included `main.bbl` also allows an initial PDF build without rerunning BibTeX. Rebuild the bibliography after changing citations or the `.bib` file.

### Scope and status
This is a prospective research and experimental design, not an empirical paper reporting completed API experiments. The three propositions concern the stated surrogate model. Numerical checks of assignment rules, mathematical identities, graph properties, and budget arithmetic are not LLM results.

The main design keeps the initial answer/message bank and confidence histogram fixed while varying confidence allocation. It deliberately separates local replay, a state-closed sustained-display protocol, and natural-language pulse experiments. Sample sizes are provisional; effect sizes are not known. Model/provider IDs and account-specific settings remain to be entered before running the pilot. Do not put API keys in this project.
