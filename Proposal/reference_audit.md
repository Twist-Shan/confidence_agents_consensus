# Reference-use audit

Prepared 17 September 2026. This is a targeted primary-source review supporting the proposal, not an exhaustive systematic review or a guarantee of novelty. Bibliographic metadata and the closely related experimental designs were checked against original paper records and available paper text. Version-specific links below are intentional. The bibliography contains 25 references; the entries here document the closest comparisons and the methodological foundations.

## Closest contemporary comparisons

| Reference | Primary source / location | How the proposal uses it | Boundary |
|---|---|---|---|
| El et al., *Physics of Agents* | https://arxiv.org/html/2608.16578v2 ; setup, predictive model, appendix | Local-to-global research structure; refreshed inbox protocol | Their sampled opinion strength is not the same as a displayed confidence number. |
| Okawa, *Emergence of Biased Consensus* | https://arxiv.org/html/2608.02827v1 ; synthetic setup and prompt appendix | Closest overlap in confidence and collective dynamics | Its described synthetic score manipulation gives every member the same score within a condition; our primary manipulation preserves a heterogeneous histogram and changes its allocation. This distinction is not an exhaustive novelty claim. |
| Probine et al., *Characterizing Opinion Evolution* | https://arxiv.org/html/2606.18276v1 ; model comparisons and held-out evaluation | Competing low-dimensional predictors and graph-transfer tests | Successful fitting of another protocol does not establish our surrogate's validity. |
| De Nobili, *Collective Alignment* | https://arxiv.org/html/2605.10528v1 ; bias/coupling diagnostics | Shared predispositions must be separated from peer effects | Findings remain conditional on the paper's tested models and protocol. |
| Kumaran et al., *How Overconfidence...* | https://arxiv.org/html/2507.03120v1 ; controlled advice procedure | A close predecessor for local replay and initial-answer visibility | Stated adviser accuracy is source reliability, not the same object as current-answer self-confidence. |
| Lin and Hooi, *ConfMAD* | https://arxiv.org/html/2509.14034v1 ; final selection rule | Fix aggregation across all primary treatment arms | No-confidence conditions and confidence-aware conditions use different final selection rules. This does not imply that all reported benefits are caused only by aggregation. |
| Zhu et al., *Demystifying Multi-Agent Debate* | https://arxiv.org/html/2601.19921v3 ; training setup | Confidence expression and use are already studied | The confidence intervention involves training; it is not a pure inference-only numerical-label intervention. |
| Jin et al., *Remember and Reweight* | https://arxiv.org/abs/2609.03619v1 | Distinguish experience-based reliability from a currently displayed number | Historical evidence is not simply a speaker's unsupported self-report. |
| Zhao et al., *Reasoning or Rambling?* | https://arxiv.org/html/2509.21054v3 ; control experiments and multi-hop extension | Content/length controls; indirect propagation is not new in itself | The proposal tests propagation of a specific randomized confidence intervention, not just the existence of multi-hop persuasion. |

## Other direct agent predecessors

| Reference | Verified original record | Relevance |
|---|---|---|
| Weng et al., BenchForm | https://arxiv.org/abs/2501.13381v2 | Controlled conformity and correct-to-incorrect switching. |
| Zhang et al., collaboration mechanisms | https://aclanthology.org/2024.acl-long.782/ | Overconfident/easy-going personas and debate/reflection protocols already exist. |
| Amayuelas et al., collaboration attack | https://aclanthology.org/2024.findings-emnlp.407/ | A malicious member can be studied separately from normal collaboration. |
| Yoffe et al., DebUnc | https://arxiv.org/abs/2407.06426v2 | Uncertainty transmission; attention modification requires model access not assumed here. |
| Chen et al., ReConcile | https://arxiv.org/abs/2309.13007v3 | Confidence-aware communication and aggregation. |

## Behavioral and statistical foundations

Zarnoth and Sniezek (1997), DOI `10.1006/jesp.1997.1326`, motivates confidence and influence; Price and Stone (2004), DOI `10.1002/bdm.460`, motivates the confidence heuristic. Lorenz et al. (2011), DOI `10.1073/pnas.1008636108`, motivates separating agreement from accuracy. None of these establishes a human-like psychological mechanism in LLMs.

DeGroot (1974) and Brock and Durlauf (2001) provide averaging and stochastic social-choice precedents. Tian et al. (arXiv:2204.13610v2) and Almaatouq et al. (arXiv:2006.12471) make the older influence-allocation literature explicit, preventing a claim that influence should track accuracy is itself a new general principle.

Hudgens and Halloran (2008), DOI `10.1198/016214508000000292`, supports reasoning about interference. Gneiting and Raftery (2007), DOI `10.1198/016214506000001437`, supports probabilistic evaluation with proper scores. These references do not certify the API isolation, sampling, stationarity, or model-correctness assumptions in this particular project.

Cobbe et al. (arXiv:2110.14168v2) and Suzgun et al. (arXiv:2210.09261v1) document GSM8K and BIG-Bench Hard. Any binary adaptation in the proposed experiment must be recorded as an adaptation rather than presented as an official benchmark score.

## Specific boundaries preserved in the proposal

- Displayed confidence, historical accuracy, self-reported probability, and repeated-sampling consistency remain distinct.
- Constant confidence attached to an identity over multiple updates is an experimental display policy, not evidence of an internally persistent belief.
- Fixed-content identification occurs at replay/first exposure. Later freely generated message differences are downstream consequences.
- A global histogram-preserving assignment does not preserve every leave-one-out inbox histogram; the group contrast is a policy effect, while the local replay isolates a visible-inbox swap.
- A local social-weight boundary is not a theorem of eventual group takeover.
- A state-closed answer-only predictor and a projected natural-language process have different approximation requirements.
- No empirical outcomes, effect sizes, calibration quality, or model-specific costs have been fabricated.
