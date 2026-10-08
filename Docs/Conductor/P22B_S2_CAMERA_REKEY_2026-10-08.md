# P22B — S2 Shrine camera re-key and preview repair

**measured** — Offline delivery on 8 October 2026. No Unreal, MCP, PIE, Blender, `Content/` write, or `E:/PussStage` write was performed.

## Diagnosis

- **measured** — Live DRY `KLARAHOOK-20261008-171230` reports both `CineCameraActor` and `CineCameraActor2` as top-level (`has_parent: false`) actor bindings with their own `MovieScene3DTransformTrack`; the two `CameraComponent` bindings are the children. This rules out an attached-camera or child-component location for `CineCameraActor2` (`E:/PussStage/Saved/CodexConductor/KlaraIngest/klara_hookin_s2_dry.json:412-440`, `:500-528`).
- **binary-proven** — Read-only bytes of `LS_NEW_SHRINE.uasset` contain `CineCameraActor2` at byte 95355 and its GUID-scoped location track `4B2CC95E4863BEFC180159A1D1791D95.MovieScene3DTransformTrack_1.Location` at byte 139468. SHA-256 is `C0AE99592AC2E3892A85B15EE0A42871DAC831BC24F9F6D8662CF8785580AF36`. This proves the serialized actor/track identifiers, not rendered resolution.
- **measured** — The DRY refusal records mismatched X/Y keys for camera 1 (8/8 at different times) and camera 2 (9/7), then `CAMERA_LOCATION_UNRESOLVED` only for camera 2 (`klara_hookin_s2_dry.json:1856-1857`, `:1899-1974`).
- **declaration-proven** — UE 5.8 exposes channel-native `EvaluateKeys(range, frame rate)` (`D:/Unreal Engine/UE_5.8/Engine/Plugins/MovieScene/SequencerScripting/Source/SequencerScripting/Private/KeysAndChannels/MovieSceneScriptingDouble.h:290-299`). **inferred** — The old preview failed because it attempted a non-existent single-frame `evaluate`, then its fallback could resolve only exact keys/endpoints; camera 2's cut frame was between its mismatched keys.

## Built

- **declaration-proven** — A world-space section with mismatched X/Y times now takes the union keyed range, calls the UE channel's own evaluator at every display frame, rigidly rotates/translates X/Y, unwraps/adds yaw, and emits per-frame LINEAR X/Y/yaw keys. Z retains its authored curve plus translation (`Saved/CodexConductor/KlaraIngest/klara_hookin.py:828-895`). Dense replacement and `1e-4` read-back remain confined to the duplicate (`klara_hookin.py:1744-1774`, `:1777-1853`).
- **declaration-proven** — Binding classification explicitly skips child/attached relative transforms; the measured S2 cameras take the world-space path (`klara_hookin.py:407-416`, `:1263-1316`). REVERT still removes the replacement track and deletes the copy only when it has no referencers (`klara_hookin.py:1981-2037`).
- **declaration-proven** — DRY now evaluates and reports both full camera paths, draws each path and its first-key frustum, and draws hangar plus footprint in one rotated world frame (`klara_hookin.py:1320-1408`, `:1411-1516`). Any path sample outside the footprint expanded by 1000 cm adds `PREVIEW_SUSPECT` as a warning (`klara_hookin.py:1433-1447`, `:1553-1555`).

## Offline harness

- **measured** — `python Saved/CodexConductor/KlaraIngest/test_klara_hookin_offline.py` returned `37/37`, failures 0, errors 0. Controls cover mismatched key times/channel evaluation, attached camera classification, rotated preview frame, suspect-path rejection, and PNG output (`test_klara_hookin_offline.py:302-351`, `:376-380`, `:426-452`).
- **measured** — Synthetic quadratic curves sampled at four sub-frames per display-frame interval measured maximum dense-LINEAR deviation `0.279508497 cm` in XY and `0.250000000°` in yaw; the no-subframe negative control refuses (`test_klara_hookin_offline.py:30-35`, `:353-361`). **inferred** — Live S2 deviation requires the next DRY/APPLY read-back; synthetic error is not a claim about Klara's curves.

## Conductor runbook

1. **DRY** — In `klara_hookin_s2_args.json`, keep `mode: "DRY"`, empty `confirm`, and assign a fresh run id. Run `klara_hookin_s2_run.py`. Require `KLARAHOOK_DRY_OK`, `apply_ready=1`, zero dirty packages, bake metadata for both cameras, two resolved full paths, and inspect `klara_hookin_s2_topdown.png`. `PREVIEW_SUSPECT` is a review warning, not silent acceptance.
2. **APPLY_SEQ** — Set only `mode: "APPLY_SEQ"`, `confirm: "APPLY_SEQ KLARAHOOK"`, fresh run id. Require `Backups/PreKlaraHookin-Seq-<run>`, exclusive `klara_hookin_seq_record_S2.json`, exact dirty census, named-package saves only, post-save read-back, and `KLARAHOOK_APPLY_SEQ_OK`. Never save Klara's source level/sequence.
3. **REVERT_SEQ if needed** — Set `mode: "REVERT_SEQ"`, `confirm: "REVERT_SEQ KLARAHOOK"`, fresh run id. The recorded-state drift gate must pass before mutation.
4. **Visual acceptance** — Capture both camera cuts after a clean saved read-back. **rendered pending** — framing, wall cuts, and the ±10 m warning remain Gary's decision.

## Open item

- **measured** — This managed worktree can edit files but cannot create refs or commits in `E:/PussStage/.git` (`Permission denied`). The conductor must commit these three explicit paths after review.
