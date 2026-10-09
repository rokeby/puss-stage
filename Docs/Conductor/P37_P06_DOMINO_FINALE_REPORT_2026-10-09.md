# P37 — P06 domino finale offline delivery

## Verdict

- **[measured] REFUSED, not silently weakened.** The production DRY plan requested 12 right-side rows but selected 0: every suffix of two or more rows fails the physical/contact eligibility checks; only the final single row is eligible, which is not a domino. The 12-row suffix also contains three over-thick panels (72.0, 96.8, 72.0 cm). `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:68-93,288-302,389-399`
- **[measured] Candidate-only finale geometry/timing:** 122.000 s leaves a 124.001125 s finish limit, but the final row is 307.083 cm behind the camera at the slam. Because Chain B is refused, it has no solved creak/impact/rest times and no production dust burst list. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:303-310`
- **[inferred] Authoring decision required:** either reposition/replace the final right panels so a >=2-row suffix is contactable (the solver uses panel height/contact geometry), or explicitly authorize choreographed non-contact falls. The latter changes the physical premise and should not be inferred from Gary's request.

## Chains and creative plan

- **[measured] Chain A (`A`)** is adopted read-only: six left rows (`P06 Wing 002`, `038`, `047`, `OLD 19`, `050`, `007`), active run `TOPPLE-20261007-114412`; creak 29.790 s, final impact 37.000 s, rest 38.180 s, last row 36.914 m ahead of camera. Restyling is default-off and uses the separate id/record `A_RESTYLE`. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:37-67`
- **[declaration-proven] Chain B (`B`)** is right-side, requested 12, floor-ending, with a 122.0 s slam and >=2.0 s end margin. Conservative args expose gravity exponent 2.35, fall 1.65 s, stagger 0.38 s, settle 0.62 s, one 2.0° rebound with ±0.35° seeded jitter (hard maximum 3°), hesitation <=0.08 s, seed 3706, and `restyle_chain_a=false`. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_args.json:2-17`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_core.py:253-280`
- **[declaration-proven] Dust** defaults to `P_Ambient_Dust`, never auto-activates, never casts shadows, is capped at 12, and gives only B's last impact scale 2.25. The keyed owned emitters are tagged `P37_DOMINO_B` and `P37_SETTLE_DUST`. Production creates none while B is refused. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_args.json:18-23`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:256-275`
- **[binary-proven] Asset inventory** found three present dust/debris candidates with no `ParticleModuleLight` string. Embedded PCM measurement ranks `Collapse01` loudest at -14.662 dBFS RMS (3.918 s), ahead of `Collapse02`, `Explosion01`, and `Explosion02`; it is the default, but Gary's listening choice remains open. `Saved/CodexConductor/P37P06DominoFinale_20261009/asset_inventory.json:6-30,32-92,125-129`

## Safety, P33, and proof

- **[declaration-proven] The one-active-record trap is resolved** with distinct `B` and `A_RESTYLE` registries. APPLY/REVERT take backups and exact dirty censuses, save named packages, read back, and emit run markers; B REVERT checks A remains bit-identical and retains the emptied owned sequence instead of deleting it. The legacy active pointer is archived with `os.replace`, not removed. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_apply.py:342-472`; `Saved/CodexFlatV3/topple/topple_apply.py:1016-1021`
- **[measured] P33 forecast:** proportional relength to 110.6 s moves A impacts non-uniformly from 33.961–37.000 s to 28.852–30.668 s, breaking contact timing; a 122 s B finale would be beyond the new end, while dust/audio seconds would desynchronise. Re-solve both chains after P33. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:340-387`
- **[measured] Offline harness:** 37/37 checks passed, including synthetic valid 12-row positive control and negative controls for overlap, end margin, unsafe dust, and B REVERT preserving A. `Saved/CodexConductor/P37P06DominoFinale_20261009/harness_result.txt:1`; `Saved/CodexConductor/P37P06DominoFinale_20261009/test_domino_finale_offline.py:117-183`
- **[measured] Scope limit:** no Unreal or Blender ran; therefore no saved Unreal read-back, rendered motion/dust, or audible acceptance exists. No commit was created, per brief. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_plan.json:396-399`

## Review/run order

1. Review `Saved/CodexConductor/P37P06DominoFinale_20261009/p06_domino_finale_timeline.png` and `domino_finale_plan.json`.
2. After resolving the layout decision, rerun `make_domino_finale_plan.py`; require `apply_ready=true`.
3. Conductor copies the folder to production `Saved/`, leaves `domino_finale_live_args.json` in `DRY`, and sends `domino_finale_request.json` through `ExecuteProjectPythonFile`. APPLY remains impossible until a valid regenerated plan, explicit confirmation token, floor-intersection acknowledgement, clean census, asset/API probe, and `decided_by` are present. `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_run.py:1-9`; `Saved/CodexConductor/P37P06DominoFinale_20261009/domino_finale_request.json:1-7`
