# Job 118: S2 floor reflection diagnosis

Offline-built; the conductor runs it later. No Unreal or MCP call was made while authoring.

1. Run `j118_floor_reflection_probe_request.json` through the PussStage MCP endpoint.
2. Require `J118_S2_FLOOR_REFLECTION_PROBE_OK`, `census_before==after=1`, `saved=0`.
3. Review the emitted `j118_probe_J118PROBE-*.json`; choose a persistent P01 PPV label.
4. Put that label into `j118_ppv_fix_args.json`; leave mode `DRY`; run the fix request.
5. Review bounds, copied settings, priority and the sole save allowlist (the persistent map).
6. Gary approves the look. Then set `mode=APPLY`, `confirm=APPLY J118S2PPV`, run once.
7. Visually compare P01/S2. To undo, set `mode=REVERT`, `confirm=REVERT J118S2PPV`, run once.

The fix duplicates a selected persistent-level P01 post-process volume, bounds the duplicate around
S2 Hangar Floor 1-3 + Apron, and raises its priority above other volumes at S2. It neither edits nor
saves `L_Animals`, `L_KK_children`, `Japanese_Alley`, or `L_KK_Void`.
