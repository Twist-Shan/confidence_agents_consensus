# Saved experimental evidence

These twelve real runs support the current notes. Raw requests/responses, manifests, derived results, and available frozen sources are included. Use a new directory for any new model calls.

| ID | Run directory | Valid / requests |
|---|---|---:|
| E01 | [live-luna-smoke-20260918-account3](live-luna-smoke-20260918-account3/) | 124 / 124 |
| E02 | [calibration-luna-20260918](calibration-luna-20260918/) | 139 / 144 |
| E03 | [validation-luna-logic-20260918](validation-luna-logic-20260918/) | 24 / 24 |
| E04 | [expansion-luna-logic-l2-20260920](expansion-luna-logic-l2-20260920/) | 120 / 120 |
| E05 | [balanced-luna-logic-l2-20260921](balanced-luna-logic-l2-20260921/) | 230 / 240 |
| E06 | [reliability-luna-8192-json-20260921](reliability-luna-8192-json-20260921/) | 48 / 48 |
| E07 | [local-four-arm-luna-20260922](local-four-arm-luna-20260922/) | 479 / 480 |
| E08 | [confidence-gap-luna-20260918](confidence-gap-luna-20260918/) | 954 / 960 |
| E09 | [confidence-gap-replication-luna-20260923](confidence-gap-replication-luna-20260923/) | 952 / 960 |
| E10 | [supplier-transfer-luna-20260918](supplier-transfer-luna-20260918/) | 592 / 592 |
| E11 | [signal-visibility-luna-20260919](signal-visibility-luna-20260919/) | 608 / 608 |
| E12 | [signal-visibility-replication-20260920](signal-visibility-replication-20260920/) | 576 / 576 |

Total: **4876 recorded requests**, **4846 valid responses**, **$4.826184 known cost**, and **15 unknown costs**.

[inventory.json](inventory.json) records purposes, counts, and hashes of each manifest and summary. E11 and E12 are the current demand experiments. Earlier null and unreplicated results remain included. Several runs reuse task banks, so calls are not independent task counts.

## Archive policy

- Included: twelve allowlisted real runs, raw API request bodies/responses, manifests, summaries, available reports and frozen source. Requests contain no authentication headers.
- Excluded: mock runs, two failed account-start attempts, temporary renders, locks, and new future run directories. These remain local.
- Failed or unresolved calls within the selected runs remain included; outcomes were not filtered by whether they support an effect.
- Some responses contain provider-issued encrypted reasoning payloads, preserved as opaque response data.
- Directory dates often identify seeds, not execution chronology.

## Offline verification

Run from the repository root. These checks read saved calls and regenerate derived reports without calling a model.

```sh
python scripts/audit_signal_visibility.py runs/signal-visibility-luna-20260919
python scripts/audit_signal_visibility.py runs/signal-visibility-replication-20260920
python scripts/compare_visibility_replication.py runs/signal-visibility-replication-20260920
```

New run directories stay ignored until deliberately reviewed and allowlisted.
