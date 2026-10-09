# P29 — S1 rig-light fade

This bundle was authored and tested offline. It has not been run in Unreal and
does not claim rendered acceptance. It audits `LS_DevScene_01` at 25 fps,
prints every target with its live switch frame and mechanism, and changes only
the sequence asset.

## What the evidence says

- **measured (upstream saved record)** — `klara_reveal_record_S1.json` records
  the environment “Ours Off” start at S1-local frame 269 and 24 lattice-bulb
  hide sections starting at frame 282.
- **declaration-proven** — `hangar_build.py:132-140` defines the Lattice Bulbs
  as emissive mesh actors and creates paired `Lattice Glow` lights. For those
  24 visibility targets the tool ramps the paired point-light `Intensity` to
  zero before the existing bulb visibility-off endpoint. It reports the proxy
  relationship on every DRY line.
- **inferred** — the paired-light ramp should remove the illumination jolt, but
  the emissive mesh has no `Intensity` property and still hides at the endpoint.
  Gary must judge whether that last emissive-pixel disappearance is visible.
- **measured (offline)** — `test_s1_rig_fade.py` exercises positive, negative,
  and seeded-mutation controls; `harness_result.json` records the current count.

`preview_timing.png` is an analytical card, not an Unreal render. All creative
timing values are in `s1_rig_fade_args.json`; the default fade is 1.52 seconds
(38 frames), within Gary's requested 1–2 seconds.

## Ordered run

1. With PIE stopped, Sequencer closed, the vertical-slice editor current, and
   the dirty-package census empty, inspect the args and analytical preview.
2. Set a unique `run_id`; keep `mode: "DRY"` and
   `confirm: "DRY S1RIGFADE"`. Send `s1_rig_fade_request.json` through guarded
   `ExecuteProjectPythonFile`. Require `S1_RIG_FADE_DRY_OK`, `apply_ready=1`, a
   clean census, and one `S1_RIG_FADE_TARGET` line per planned light. Inspect
   the DRY JSON; frame 269 and frame 282 mechanisms must be explicit.
3. Without intervening sequence changes, change only mode/confirm/run id to
   `APPLY`, `APPLY S1RIGFADE`, and a fresh unique id. Require
   `S1_RIG_FADE_APPLY_OK`, the `Backups/PreS1RigFade-<run>` path, exact named
   save `/Game/InfinityStage/Dev/Sequences/LS_DevScene_01`, clean census, and
   saved read-back digest.
4. Run `InfinityStage.Editor.SavedMasterMatchesShow` and the relevant sequence
   binding-resolution test. Then render/review S1 across the overall 3:44 cue,
   including at least two seconds before and after the change. Gary owns the
   final fade duration and visual acceptance.

## Revert

With a clean editor and no intervening sequence edit, use a fresh run id plus
`mode: "REVERT"` and `confirm: "REVERT S1RIGFADE"`. REVERT refuses drift,
creates `Backups/PreS1RigFadeRevert-<run>`, removes only recorded new tracks and
bindings (or restores a retimed step key), saves only the named sequence, and
requires the complete pre-APPLY snapshot on saved read-back.

