# Pearl #5 (f4) + glow light option B — slot runbook (9 Oct)

Gary's choice (relayed by Conductor 5, 9 Oct): pearl variant #5 = `f4_glow012_broadsheen` and light option B
(Drama Pearl Glow at ~15 %, cello swell kept in shape). Editor idle, PIE off, census clean before steps 1-4.

1. MI DRY: `MiScalars/mi_scalars_args.json` (= `mi_scalars_args.PearlF4.json`, mode DRY) via `mi_scalars_request.json`.
   Require `MISCALARS_DRY_OK|label=PearlF4`. Targets: GreenOrange (solid) + Fade + Dither twins; same six scalars
   (IridStrength 0.8, SubsurfaceIrid 0.7, Glow 0.12, GlowIrid 0.6, FresnelExponent 1.2, IridScale 1.6).
   If a twin lacks a parameter or its parent differs, DRY refuses: drop that scalar/twin from the args, re-DRY.
2. Light DRY: `PearlLight_20261008/pearl_glow_scale_args.json` (mode DRY) via `pearl_glow_scale_request.json`.
   Require `PEARLGLOW_DRY_OK|keys=..|peak=..|peak_after=..` — read the DRY JSON's key list before APPLY.
3. MI APPLY: mode APPLY, confirm `APPLY MISCALARS PearlF4` -> `MISCALARS_APPLY_OK`.
4. Light APPLY: mode APPLY, confirm `APPLY PEARLGLOW`, fresh run id -> `PEARLGLOW_APPLY_OK` (saves LS_DevScene_03 only).
5. PIE: conductor_pie_begin; `MiScalars/pvs_scrub_4400_request.json` (PVS_SCRUB_OK); then light PIEREAD
   (args mode PIEREAD, confirm `PIEREAD PEARLGLOW`) -> `PEARLGLOW_PIEREAD_OK|match=1`;
   then `MiScalars/pvs_authored_request.json` (PVSHOT_OK, overrides nothing) -> stills for Gary.
Revert: MI `REVERT MISCALARS PearlF4`; light `REVERT PEARLGLOW` (frame-matched originals from the record).
