# P06 FX cue sheet — offline proposal, 8 Oct 2026

Nothing in this sheet has been applied. Times are seconds relative to the P06
segment, not Master time. Creative values are defaults in
`Saved/CodexConductor/P06FX_20261008/p06_fx_set_args.json`; Gary can change them
before DRY. Preview: `Saved/CodexConductor/P06FX_20261008/p06_fx_preview.png`.

## Proven spine

- **[measured]** P06 is 126.0011 s in the saved segment, while the current audio
  file is 125.0 s. The analysis has no stable tempo candidate, so section
  boundaries—not a guessed beat grid—are the musical anchors.
  (`E:/PussStage/Saved/InfinityStage/MusicAnalysis/Cameron_20261005/P06_P06_Walking6.analysis.json:7-10,940-997`;
  `E:/PussStage/Saved/CodexConductor/Effects_20261007/p06_bee_glints_record.json:140-154`)
- **[measured]** The six-slab left-side domino creaks at 29.790 s, makes its
  final/first registered impact at exactly 37.000 s, and rests at 38.180 s.
  (`E:/PussStage/Saved/CodexFlatV3/topple/topple_plan.json:3482-3483,3551-3558`)
- **[measured]** The sunset is half strength at 37.0 s, effectively dark at
  52.0 s, and fully black by 90.0 s.
  (`E:/PussStage/Saved/CodexConductor/p06_sunset_record.json:65-87`)
- **[measured]** Existing applied events are the 68.55 s car and bee glints at
  80/100/118 s. The FX tool treats them as foreign and never edits them.
  (`E:/PussStage/Saved/CodexConductor/place_p06_car_light_record.json:3-12`;
  `E:/PussStage/Saved/CodexConductor/Effects_20261007/p06_bee_glints_record.json:103-134`)
- **[declaration-proven]** The post-relayout route declares Wing 052 at
  18750 cm, Wing 044 at 24750 cm and Wing 049 at 25950 cm with the GUIDs guarded
  by the args. A later APPLY report reads those labels/GUIDs back from the Show.
  (`Saved/CodexFlatV3/p06relayout/relayout_core.py:183-189`;
  `Saved/CodexConductor/MeshyFixtures_20261007/meshy_swap_report_P06_APPLY_20261007-082927.json:3703-3705,4533-4535,4699-4701`)
- **[declaration-proven]** Effect sources activate all `UFXSystemComponent`s by
  rendered-camera distance, not by a music cue. Wing burn alone progresses by
  camera travel. (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageEffectSource.cpp:509-549`;
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageEffectTypes.h:139-160`)

## Cue proposal

| P06 time | Music / stage event | FX action | Evidence tier and status |
| ---: | --- | --- | --- |
| 0.0–21.85 | low opening; sun still above horizon | No new particles. Let the existing cool/sunset lighting own the opening. | **[inferred]** restraint is a look proposal, not rendered acceptance. |
| 21.85–29.79 | sunset fade begins; quiet section continues | No plume. Preserve silence before the mechanism announces itself. | **[inferred]** musical staging proposal. |
| 29.79–38.18 | chain creak → 37.0 s slam → settle; analysis change at 36.502 s | Domino remains the only event. No fire at the impact: a simultaneous ignition would flatten the mechanism beat. | **[inferred]** timing relationship proposed from the two measured anchors above. |
| 38.18–52.15 | sustained then building section, daylight collapses | Hold particles. Existing lamps and the fallen chain reveal the move into black. | **[inferred]** look proposal. |
| 52.15–68.55 | black; music builds then releases at 62.230 s | No smoke by default. Optional `include_smoke=false` remains available for Gary; P06 smoke was explicitly excluded in the 7 Oct effects plan. | **[declaration-proven]** default is encoded in args; **[inferred]** look remains unjudged. |
| 68.55–82.7 | car drive-by; change points at 68.917, 74.072, 80.295 s | Motes on `P06 Wing 052`, PairCentre, active within 2400 cm; this overlaps the 74/80 s releases and the existing 80 s bee glint. | **[inferred]** spatial/time overlap from saved route positions; requires DRY read-back and rendered acceptance. |
| 86.7–102.7 | late releasing music; bee glints at 80 and 100 s | Burn `P06 Wing 044` Left: start 3000 cm ahead, consume over 4000 cm. Per-flat Front/Flap child MIs isolate `UseBurn`; no shared MI is edited. | **[inferred]** proposed target/window; **[declaration-proven]** travel law and isolation mechanism. |
| 94.6–end | music thins toward silence | One FireBasket at `P06 Wing 049` Left, active radius 2200 cm. ParticleModuleLight defaults OFF through a private duplicated Cascade template; linked rig-light GUID remains unset, so no rig light is driven. | **[inferred]** placement/look; **[declaration-proven]** safe defaults in args/tool. |
| 100 / 118 | existing bee glints grow | Do not add or retime bees. Fire should be a low side source, leaving the bee glints as the only high/floating marks. | **[measured]** bees already authored; **[inferred]** composition. |
| final seconds → S6 | total blackness | Fire must fall out before the boundary by distance gating; no candle by default. The fallen burning drop remains a separate Soft-goods + FX task. | **[declaration-proven]** `include_candle=false`; **[inferred]** rendered falloff unverified. |

## Deliberate holds

- **[measured]** Candle is not restored: Gary removed the S6 candle on 5 Oct.
  `include_candle` is false and the P06 set tool refuses true rather than silently
  reintroducing it. (`Docs/Conductor/EFFECTS_PLAN_2026-10-07.md:85-90`)
- **[measured]** SmokePot and Motes already exist; HazePot, SteamKettle,
  FireBasket and WingBurn were absent in the 7 Oct probe. The new blueprint tool
  verifies existing assets and creates only absent targets.
  (`Saved/CodexConductor/Effects_20261007/fx_content_probe.json:66-81`)
- **[measured]** Cascade Rain2 and Humo_Par rendered in UE 5.8 under a controlled
  particles-off negative control; only one of three still positions was valid, so
  this proves renderer viability, not every placement.
  (`E:/PussStage/Saved/CodexConductor/Effects_20261007/P04RainPIE/P04RAINPIE-20261007-063520/manifest.json:91-117`)
- **[inferred]** No preview image proves the look. Required next evidence is
  BP/material DRY read-back, then Gary-approved APPLY, then PIE stills at 37,
  74, 88, 100 and 118 s. NullRHI or transport success is not acceptance.

## Run and revert order

1. `p06_fx_probe.py` (read-only).
2. `p06_fx_blueprints.py` DRY, then APPLY only after review.
3. `p06_wingburn_mi.py` DRY, then APPLY.
4. `p06_fx_set.py` DRY, then APPLY.
5. Revert in reverse order: set → wing child MIs → blueprints.

Every APPLY/REVERT refuses PIE/SIE, requires the exact world and a zero-dirty
census, writes a record and `Backups/Pre<Thing>-<run>` before mutation, saves
only named packages, reads them back, and emits a run-id success marker.
