# P28 — S3 polish

This bundle is offline-authored and has not been run in Unreal. It is one
DRY/APPLY/REVERT tool with four independently selectable parts:

- `fires_together`: re-times Fire B and C to the same args ignition and applies
  a slow 0→1 envelope; Fire A and the ghost flame are excluded.
- `b11_dim`: reads the live B11 cut/camera, projects Ground Rows 2/3/4 into that
  camera, and dims the selected cold light only during B11.
- `dune_shadow`: reports the dune's supported shadow/VSM fields and enables
  `cast_shadow` plus `cast_dynamic_shadow`.
- `stylish_fire`: inventories `NS_Stylish_Fire_1..4` and plans same-transform
  Niagara replacements. It remains DRY-only unless `stylish_apply` is true;
  APPLY hides but never deletes the P_Fire actors.

## Evidence boundary

- **declaration-proven** — the four parts, default common ignition 230, slow
  ramp 72, B11 factor 0.25/ramp 24, stylish-fire opt-in, and map/Scene-3-only
  save boundary are the brief's explicit contract
  (`Docs/Conductor/codex_briefs/p28_s3_polish.md:20-29`).
- **measured (upstream, not re-measured here)** — the brief records the existing
  B/C ignition frames 260/290, B11 `[5181,6253]`, named 9000 K row lights, and
  tagged dune (`p28_s3_polish.md:8-19`). DRY reads those live and refuses drift.
- **measured (offline)** — `test_s3_polish.py` passes 49/49 controls: 31 positive
  and 18 negative. `harness_result.json` contains each result.
- **inferred** — the default `second_left` selector means the second forward
  candidate among camera-left Ground Rows 2/3/4. This is a deterministic reading
  of Gary's words, not visual acceptance. Set `b11_dim_labels` explicitly after
  inspecting DRY if the rendered B11 frame points to another row.
- **inferred** — enabling the dune's two dynamic-shadow flags should stop figures'
  shadows reaching the wall through it. Only a rendered B11 review can prove the
  result.

The PNGs are analytical cards, not scene renders:
`preview_timing.png` and `preview_b11_candidates.png`.

## Files

- `s3_polish.py` — guarded authoring and exact REVERT.
- `s3_polish_args.json` — all timing, selection and Niagara look choices.
- `s3_polish_run.py` / `s3_polish_request.json` — project-Python route.
- `test_s3_polish.py` / `harness_result.json` — offline +/- controls.
- `make_previews.py` / `preview_*.png` — regenerate analytical look cards.

## Conductor run order

1. Keep PIE/SIE stopped and Sequencer closed; load the vertical-slice map and
   require an empty content+map dirty census. Inspect `s3_polish_args.json`.
2. Set a fresh `run_id`, `mode: "DRY"`, `confirm: "DRY S3POLISH"`; send
   `s3_polish_request.json`. Require `S3_POLISH_DRY_OK` and `mutated=0`.
3. Inspect `s3_polish_dry_<run>.json`:
   - B and C each have one `bHidden` visibility channel (False=hidden,
     True=shown), and every moved light/visibility key is listed;
   - B11 is exactly `[5181,6253]`, camera evaluation reports one value per
     channel from `sequence.make_range(frame,1)`, and the row ranking matches
     Gary's frame; set `b11_dim_labels` if `second_left` is not the intended row;
   - dune reports both required flags plus supported VSM-adjacent fields;
   - each Niagara asset reports its exposed-parameter store/API result. Choose
     the system mapping before opting into the swap.
4. Rerun DRY after any args edit. With no intervening asset edit, change only to
   `mode: "APPLY"`, `confirm: "APPLY S3POLISH"`, and a fresh run id. Keep
   `stylish_apply: false` unless Gary has made the look call. Require
   `S3_POLISH_APPLY_OK`, the exact named saves, backup path, record path, and an
   empty final census.
5. Read the record back, then run the project's focused Scene 3 sequence/cut
   checks before PIE. Capture B11 and the fire ignition for Gary. Saved read-back
   is not rendered acceptance.

## Revert

With no intervening target edit, set a fresh run id plus `mode: "REVERT"` and
`confirm: "REVERT S3POLISH"`. REVERT refuses any numeric/key/actor drift, makes
`Backups/PreS3PolishRevert-<run>`, restores exact recorded keys and dune flags,
removes only bindings it created, destroys only actors tagged
`S3PolishStylishFire`, saves only the packages recorded by APPLY, reads back,
and emits `S3_POLISH_REVERT_OK`.
