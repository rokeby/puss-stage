# P45 — authored breath insertion

Offline-authored bundle for inserting an approved breath inside one Passage. It
plans one exact timing-span extension, stops the route with
`Camera.SpeedMultiplier`, adds Gary's yaw/pitch look, ripples only the changed
Passage's local content, and leaves later-Passage carry to the managed rebuild.
It was **not run live**.

## Proof boundary

- **declaration-proven** — the 13 Passage channels are declared at
  `Plugins/InfinityStage/Source/InfinityStage/Public/MovieSceneInfinityPassageTrack.h:13-43`;
  Passage timing fields are declared at
  `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h:740-744,982-1001`.
- **measured-upstream** — DRY re-reads and hashes the named `breath_audio.py`
  APPLY record and requires its exact sample delta to equal D in Show ticks.
- **measured-offline** — `harness_result.json` covers a fake-backend round trip,
  nine refusal controls, and the requested 90 s / 40% / 6 s synthetic case.
  `breath_insert_preview_synthetic_90s_40pct_6s.png` is that analytical
  timeline preview, not a scene render.
- **inferred** — the edit list implements the design in
  `Docs/Conductor/P36_BREATH_INSERT_TIME_REPORT.md:102-137`. Saved-Unreal,
  audible, visual and rehearsal acceptance remain open.

## Rehearsal-slot order

1. Gary/Klara choose the production music track, F inside the Passage, D from
   the approved audio APPLY record, wind-down W, and the look shape
   (yaw/pitch/ease). Listen to the rendered WAV and inspect its waveform and
   spectrogram previews first.
2. Import the rendered WAV through the guarded audio-import route and regenerate
   its music analysis. Put the exact asset paths, Passage GUID, F, D and named
   packages in `breath_insert_args.json`. D must be the renderer's exact output
   delta, not merely its silence N.
3. With the expected level open, PIE/SIE stopped, Sequencer closed and the exact
   dirty-package census empty, run DRY via `breath_insert_request.json`. Require
   `P36_BREATH_DRY_OK|run=<id>`, inspect the full holder/edit census and the
   analytical timeline PNG. DRY changes no Unreal asset.
4. The runner injects `breath_insert_live.py` behind the pure planner/backend
   boundary. Change only mode/run/confirm to APPLY and
   `APPLY BREATH <run>`. APPLY records and backs up every named package to
   `Backups/PreBreathInsert-<run>` before mutation, rebuilds the Master,
   materializes only the changed Passage, checks handoffs, saves only the named
   packages, reloads/read-backs every holder, and requires
   `P36_BREATH_APPLY_OK|run=<id>`.
5. In the conductor-owned rehearsal slot, verify by eye/ear: Puss stops and
   looks; Wings, squeaks and time-driven flicker continue; music tape-stops,
   stays silent and resumes at the recorded source sample; the first later cue
   is delayed by exactly D. Offline green is not this acceptance.

## Revert

With a clean editor and no intervening edit, use a fresh run id,
`source_run_id: <apply-run>`, mode REVERT, and exact confirm
`REVERT BREATH <apply-run>`. REVERT first creates
`Backups/PreBreathInsertRevert-<run>`, restores the recorded pre-state, saves
only the same named packages, reads it back, archives the APPLY record and emits
`P36_BREATH_REVERT_OK|run=<id>`.

## Offline harness

Run `python test_breath_insert.py`. The result is tool behavior only; it makes
no claim about a saved Show, rendered camera, or audible transition.

## After APPLY: companion steps (added on review, 9 Oct)

1. **Cue sheet / Cue Book times:** run the Cueing stream's shift for the same Passage, F and D, so At/GO and surtitle
   times after the breath move by D: `python Tools/CueSheet/breath_shift.py shift DRY "<passage>" <F> <D>`, then
   `APPLY ... --confirm APPLY_BREATH_SHIFT` (revert: `revert <record> --confirm REVERT_BREATH_SHIFT`). Candidate
   insert points come from `breath_shift.py candidates` (the Cue Book "Pause possible" flags).
2. **Shadow-cat actions (only once held patch `Scripts/patches/2026-10-09_shadow_cat_actions.patch` is built):**
   actions are stored Passage-relative in the Show (`FInfinityShadowCatAction::StartFrame`). Any action in the
   breathed Passage with StartFrame >= F must also move by D; this tool does not do that yet (it predates P46). Add
   it as a classified holder before the first breath that coexists with cat actions.
