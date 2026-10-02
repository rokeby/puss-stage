# Slot C / P05 dry-run plan

| Passage | Config | Saved read-back rows found offline | Plan status |
| --- | --- | ---: | --- |
| P05 | `run_c_p05.json` | 0 | **needs live preflight** |

No `P05 Wing ` rows occur in the saved Flat V3 JSON artifacts on disk. The live
agent must run `preflight.py` and then `dry.py` unchanged with the config above.
The dry plan must report every occurrence using the excluded
`SM_FlatV3_P05_CloudRef02_L_L` mapping as `excluded_rows_kept_old`; its old mesh
must remain assigned.
