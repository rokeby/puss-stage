# Job 110 — P02 car drive-by reach tune (offline report)

**Status: HOLD.** The guarded tool is built and its offline harness is green. No
Unreal, MCP, PIE, level, Show asset, or binary was opened or changed. The
checked-in args are `DRY`; the conductor must not run `APPLY` until Gary says yes
to this look proposal.

## What is live in the records

- **measured:** The placement run `CAR-20261005-092430` wrote and immediately
  read back the actor label, local aim `[0,-2400,0]`, peak 9000 cd, and
  attenuation radius 3200 cm
  (`E:/PussStage/Saved/CodexConductor/place_p02_car_light_record.json:2-41`).
- **measured:** P02 straightening later moved that same labelled actor from
  `(8326.29,85240.71,90)` / yaw `-10.36` to
  `(10009.86,85308.40,90)` / yaw `-43.59`; the record contains transform fields,
  not car-light look fields
  (`Saved/CodexConductor/p02_straighten_followons_record.json:78-116`).
- **measured:** The latest later runtime probe found the labelled spot component
  with outer cone 28 degrees and attenuation radius 3200 cm
  (`E:/PussStage/Saved/CodexConductor/animated_gobo_pie_probe_AGPIE-20261009-02.json:34432-34438`).
  Its instantaneous intensity is envelope phase, so it does not prove the stored
  9000 cd peak.
- **measured search / UNCLEAR:** A filename search and content grep under
  `E:/PussStage/Saved/CodexConductor` found no later P02-car tune record. Therefore
  3200 / `[0,-2400,0]` / 9000 / 28 is the best recorded expected state, but only
  Job 110 `DRY` can verify all four current actor properties together.

## Diagnosis and proposal

- **declaration-proven:** `AimTargetLocal`, `PeakIntensity`,
  `AttenuationRadiusCm`, and `OuterConeDegrees` are editable Sweep Light
  properties (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageSweepLight.h:72-77,122-150`).
  Runtime copies radius and cone to the light components and uses the local aim
  in its sweep parameters
  (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageSweepLight.cpp:261-301,317-325`).
- **inferred:** With the car at local Y `+2400` and wing lines near `+/-1416`,
  the near throw is about 984 cm and the far throw about 3816 cm. Ideal
  inverse-square distance alone gives about a 15:1 near/far ratio; moreover the
  far line is about 616 cm outside the present 3200 cm attenuation radius.
- **inferred / Gary decides:** Default proposal: radius 4600 cm and aim local
  `[0,-3800,0]`. Peak 9000 cd and outer cone 28 degrees remain unchanged unless
  explicitly supplied. The extra reach should let the shadow cross the far
  wings; it may also lift spill, so stills are mandatory.

## Delivered guard

`Saved/CodexConductor/p02_car_light_tune.py` finds exactly one actor by the label
from the placement record and requires class `InfinityStageSweepLight`. It has
DRY/APPLY/REVERT confirmation strings; validates current values against args;
refuses PIE, wrong world, dirty packages, identity drift, target limits, and
REVERT drift; writes old values plus a `Backups/PreP02CarLightTune-<run>` level
copy before mutation; saves only the vertical-slice level; reads back; requires
zero dirty packages; and logs a run-id success marker. REVERT uses the named
originals record and refuses unless current values still equal that APPLY record
(`Saved/CodexConductor/p02_car_light_tune.py:167-260`).

## Conductor run order

1. Import the four `Saved/CodexConductor/p02_car_light_tune*` files, including
   ignored `p02_car_light_tune_args.json`, plus the offline test and this report.
2. Keep args `mode=DRY`, `confirm="DRY P02CAR_TUNE"`; run
   `p02_car_light_tune_request.json` through guarded MCP and require
   `P02_CAR_LIGHT_TUNE_DRY_OK|run=...|mutated=0`.
3. Inspect the generated DRY JSON. If any expected-current drift is reported,
   stop and reconcile it; do not overwrite it.
4. **Wait for Gary's yes.** Then change only args to `mode=APPLY`,
   `confirm="APPLY P02CAR_TUNE"`; rerun the same request and require
   `P02_CAR_LIGHT_TUNE_APPLY_OK`, `level_saved=1`, `readback=1`, `dirty=0`.
5. At one frozen car-pass midpoint (1.75 s into its 3.5 s travel), capture two
   matched-exposure stills: near house-left wing and far house-right wing.
   Accept only if the near shadow stays legible and the moving shadow reaches and
   travels across the far wings. **Gary's eye is visual acceptance.**
6. If rejected, set `mode=REVERT`, `confirm="REVERT P02CAR_TUNE"`, and
   `revert_from` to the APPLY originals filename; rerun and require the REVERT
   success marker, saved read-back, and clean census.

## Offline verification

- **measured:** `python Saved/CodexConductor/test_p02_car_light_tune_offline.py`
  passed 9/9 positive and negative controls on 9 Oct 2026.
- **measured:** `py_compile` and `git diff --check` passed.
- **inferred / pending:** Unreal DRY, APPLY, saved-state read-back, rendered
  near/far stills, and Gary's acceptance remain pending by design.
