# P37b - P06 choreographed slow domino offline delivery

## Verdict

- **[measured] APPLY-ready offline plan: 11 of the requested 12 right-side rows.** The 12-row candidate is refused because `P06 Wing 045` would sweep through the still-standing `P06 Wing 007` and `P06 Wing 012`; the next suffix is collision-free, so the planner reduces to 11 without shortening the 1.65 s falls. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:4499-4785,6457-6463,7279-7281`
- **[measured] The post-P33 authored P06 end is 110.600000 s, not 110.561125 s.** 110.561125 s is the selected music interval; P33's declared whole-25-fps-frame ceiling makes the saved target 2,654,400 ticks / 110.6 s. The default slam is therefore 108.600000 s (end minus 2.0 s), and rest completes at 109.220000 s. `Saved/CodexConductor/passages_to_music.py:8-12`; `Saved/CodexConductor/passage_retime_to_music.py:199-204`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:44-53,4330-4339`
- **[measured] Offline harness: 45/45 passed.** It includes the required 12-wing positive fit and negative controls for a standing-panel intersection, slam after end-minus-two, auto-activating dust, and Chain A remaining bit-identical through B APPLY and REVERT. `Saved/CodexConductor/P37P06DominoFinale_20261009/harness_result.txt:1`; `Saved/CodexConductor/P37P06DominoFinale_20261009/test_domino_finale_offline.py:126-141,169-212`
- **[inferred] The motion, dust weight, and Collapse01 slam remain creative candidates.** No Unreal, PIE, MCP, Blender, rendered, or audible acceptance was run; live DRY and rendered review remain mandatory. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:7285-7287`

## Implemented plan

- **[declaration-proven] Chain B now exposes `mode_b: contact|choreographed`, defaulting to `choreographed`.** Defaults are 12 right rows, 1.65 s fall with a 1.4 s hard minimum, 0.35 s shockwave delay with seeded +/-0.08 s jitter, gravity exponent 2.35, one bounded rebound, dust cap 12, final dust scale 2.25, and Collapse01. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_args.json:2-29`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:60-142`
- **[declaration-proven] Every next creak is solved from the preceding impact plus the shockwave delay; one signed jitter draw is used per transition and one rebound draw per row.** If N does not fit, decreasing suffixes are tried; `fall_s` is never compressed below the argument/minimum. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:323-371,413-445`
- **[measured] Fall direction is downstage/negative-route, away from the advancing camera.** Each sweep is tested against every panel still standing at that impact; already-fallen Chain B rows are excluded. This direction makes the selected 11 collision-free while honestly refusing the 12th. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:374-410`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:4345-4485,4776-4785`
- **[measured] Chain A is planned against the same projected post-P33 timing but remains read-only.** Its predicted impacts move to 28.851758, 29.632200, 30.049042, 30.322483, 30.525125, and 30.668567 s. B's live APPLY and REVERT retain explicit before/after A mechanism-hash guards. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:7218-7273`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:393-424,440-464`
- **[binary-proven, inherited from Job 37]** `P_Ambient_Dust` has no recovered particle-light module string, and embedded PCM measurement ranked Collapse01 loudest. **[measured]** This plan passes those inventory gates, keys one shadowless/non-auto dust burst per selected impact, and scales only the last burst to 2.25. `Docs/Conductor/P37_P06_DOMINO_FINALE_REPORT_2026-10-09.md:13-14`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:6465-6685`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:230-275`

## Measured Chain B timing

**[measured]** Times are P06-relative. Camera route is distance travelled along the compiled route; panel-camera is negative when the panel is behind the camera. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:7117-7216`

| # | Right row | Creak s | Impact s | Shockwave s | Camera route m | Panel-camera m |
|---:|---|---:|---:|---:|---:|---:|
| 1 | P06 Wing 046 | 86.956733 | 88.606733 | - | 252.363 | -100.863 |
| 2 | P06 Wing 016 | 88.887114 | 90.537114 | 0.280381 | 257.861 | -94.241 |
| 3 | P06 Wing 053 | 90.960402 | 92.610402 | 0.423288 | 263.766 | -88.266 |
| 4 | P06 Wing 052 | 92.885582 | 94.535582 | 0.275180 | 269.249 | -81.749 |
| 5 | P06 Wing 022 | 94.812607 | 96.462607 | 0.277025 | 272.705 | -73.226 |
| 6 | P06 Wing 048 | 96.791844 | 98.441844 | 0.329237 | 273.223 | -61.723 |
| 7 | P06 OLD 23 - steel_scaffold | 98.842073 | 100.492073 | 0.400229 | 273.759 | -50.259 |
| 8 | P06 Wing 025 | 100.890123 | 102.540123 | 0.398050 | 274.295 | -38.675 |
| 9 | P06 Wing 044 | 102.940839 | 104.590839 | 0.400716 | 274.831 | -27.331 |
| 10 | P06 Wing 049 | 104.952100 | 106.602100 | 0.361261 | 275.357 | -15.857 |
| 11 | P06 Wing 055 | 106.950000 | 108.600000 | 0.347900 | 275.880 | -3.466 |

`Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:7117-7216`

## Refusals and proof boundary

- **[measured] Required negative controls refuse:** fall through standing geometry, slam later than end-minus-two, `dust_auto_activate=true`, and B mutation of Chain A on either APPLY or REVERT. `Saved/CodexConductor/P37P06DominoFinale_20261009/test_domino_finale_offline.py:169-212`
- **[declaration-proven] Live mutation remains guarded:** backup and record precede changes; exact named packages are saved; read-back and clean-census gates remain; no Save All or asset deletion path was added. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:87-136,291-329,393-471`
- **[inferred] Eleven is the safe count for the current measured geometry, not a permanent creative mandate.** Repositioning the two earlier standing panels, changing direction with a new geometric proof, or accepting contact could allow 12, but none is authorized here. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:4776-4785`
- **[declaration-proven] No commit was created.** The stream brief says the conductor reviews and commits. `Docs/Conductor/codex_briefs/p37b_p06_choreographed_domino.md:25`

## Conductor run order

1. **[declaration-proven]** Apply P33 first and require its saved/read-back P06 end to be 2,654,400 ticks (110.6 s); any mismatch makes this plan stale. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:279-320,743-770`
2. **[measured]** Review `p06_domino_finale_timeline.png`, `domino_finale_plan.json`, the 11/12 reduction, and the exact timing table above. `Saved/CodexConductor/P37P06DominoFinale_20261009/make_domino_finale_plan.py:124-201`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:6457-6463,7117-7216`
3. **[declaration-proven]** Run `domino_finale_run.py` in DRY through `ExecuteProjectPythonFile`; require its run-id marker, exact clean dirty-package census, and live asset/API probes. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:342-359`
4. **[declaration-proven]** If Gary authorizes the candidate, APPLY requires the exact confirm token and remeasures the live P06 inputs through the legacy stale-plan hash gate before mutation. **[inferred]** Gary must then judge slow-fall motion, dust weight, and Collapse01 by eye/ear. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:393-437`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_args.json:12-29`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:7285-7287`

## Delivered files

- **[measured] Code/harness:** `domino_finale_core.py`, `make_domino_finale_plan.py`, `test_domino_finale_offline.py`, and the unchanged guarded `domino_finale_apply.py` in `Saved/CodexConductor/P37P06DominoFinale_20261009/`. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:279-445,504-615,743-840`; `Saved/CodexConductor/P37P06DominoFinale_20261009/test_domino_finale_offline.py:90-255`
- **[measured] Plan/artifacts:** `domino_finale_args.json`, `domino_finale_live_args.json`, `domino_finale_plan.json`, `p06_domino_finale_timeline.png`, and `harness_result.txt` in that folder. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_args.json:1-32`; `Saved/CodexConductor/P37P06DominoFinale_20261009/make_domino_finale_plan.py:124-225`; `Saved/CodexConductor/P37P06DominoFinale_20261009/harness_result.txt:1`
