# P03 dry-run plan

| Passage | Config | Saved read-back rows found offline | Plan status |
| --- | --- | ---: | --- |
| P03 | `run_p03.json` | 0 | **needs live preflight** |

No `P03 Wing ` rows occur in the saved Flat V3 JSON artifacts on disk. The live
agent must first complete the P03 import, then run `preflight.py` and `dry.py`
unchanged with the config above. `P03_LAYOUT_DRAFT.json` supplies the proposed
L/R/C mapping, but it is not a saved Unreal read-back and is not used to invent
old transforms or lateral positions.
