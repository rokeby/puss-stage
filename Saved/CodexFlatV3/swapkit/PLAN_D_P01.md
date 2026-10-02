# Slot D / P01 dry-run plan

| Passage | Config | Saved read-back rows found offline | Plan status |
| --- | --- | ---: | --- |
| P01 | `run_d_p01.json` | 0 | **needs live preflight** |

No `P01 Wing ` rows occur in the saved Flat V3 JSON artifacts on disk. The live
agent must run `preflight.py` and then `dry.py` unchanged with the config above.
No occurrence rows or lateral values have been invented offline.
