# Job 127 conductor order

Offline-authored only; Unreal has not run this tool.

1. Keep `job127_args.json` in DRY mode and run `job127_request.json`.
2. Require `JOB127_P04_SMOKE_PROP_HIDE_DRY_OK`; inspect the JSON report and copy its `plan.plan_sha256` into the args.
3. Set mode `APPLY`, confirm `APPLY JOB127 HIDE P04 SMOKE PROP`, and `ack_clear_apparatus_mesh_for_pie=true`.
4. Require `JOB127_P04_SMOKE_PROP_HIDE_APPLY_OK`, `show_saved=0`, `plume_unchanged=1`, and an empty final census.
5. For rollback set mode `REVERT`, confirm `REVERT JOB127 RESTORE P04 SMOKE PROP`; require the REVERT marker and archived record.

Why the mesh is cleared as well as hidden: `AInfinityStageEffectSource::BeginPlay()` calls `ApplySettings()`, which makes a smoke apparatus visible again. Nulling only the recorded `Apparatus` instance mesh keeps it absent in PIE; REVERT restores that mesh and both visibility flags. Actor `bHidden` is deliberately unchanged because the actor also owns `PlumeFX`.
