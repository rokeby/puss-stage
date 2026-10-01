# S3 blocking probe — READ-ONLY (Conductor 3, 1 Oct)

Gary, PIE: the Scene 3 cast stands "right up close to the camera"; he wants the centre of
the diorama "about 10 m in front of camera". He also asks whether the hangar has a roof/lid
(he sees only the lattice ceiling). Measure; change NOTHING.

Write ONE script `Saved/CodexConductor/s3_blocking_probe.py` plus its request json
(same shape as `Saved/CodexStructure/s3_pit_deck_dryrun_run_request.json`), run it once
through `Saved/CodexMocap/mcp_request.py`, and read the result from `Saved/Logs/PussStage.log`
by marker + run id (`run=<HHMMSS>`), never `tail -1`.

## Report, all in WORLD cm (and also in the S3 dock frame the pit tool uses, if you can reuse its helper read-only)
1. The Scene 3 camera at the arrival/stop: the cat camera's stop for Scene 3 as the Show/
   transport define it (InfinityStage Show asset: Scene 3's dock / the preceding Passage's end
   transform). Say exactly which property you read.
2. Every camera in `LS_Clams` (and any other sequence nested in Scene 3's sequence): binding
   name, the bound/spawnable camera's transform keys (first and last key per channel) read from
   the ASSET's channels, and the cut-track ranges. Root and nested.
3. Current world location + bounds of: Shore01..06 Clam, Clam_with_Pearl_Clam_with_Pearl_0,
   PointLight, S3 Ghost Light (+Stand), the S3 Strike lights, the S3 deck, S3 Hangar Far/Left/
   Right Wall, S3 Hangar Roof, lattice beams 01 and 14.
4. `LS_S3_HangarRise`: for S3 Hangar Roof and the lattice, the transform keys (time, value)
   — i.e. where the roof ends up after landing, and when. Is the roof ABOVE the lattice
   (would the lattice hide it from the camera)?
5. Derived: horizontal distance camera -> cast centroid, camera -> far wall, and the box's
   depth along the camera's forward axis.

Marker: `S3_BLOCKING_PROBE|run=<id>|...` with a JSON payload, ending with
`S3_BLOCKING_PROBE_DONE|run=<id>|census=<dirty maps/content after>`. The census must be
empty both before and after; if it isn't, say so first.

## Crash and dirt rules (each has crashed or dirtied this editor before)
- NEVER open Sequencer, scrub, play, or evaluate any sequence; read channels from the asset only.
- NEVER call `get_bound_objects` / `locate_bound_objects` with an open range, nor any
  `SequencerTools` helper. Read bindings by GUID and possessable/spawnable templates.
- No `unreal` wrapper objects held in module globals; everything inside a function.
- Never reload a level or package. No PIE. No save of any kind. No Modify(), no setters.
- If PIE is running (last `Bringing World ... UEDPIE` not followed by `Shutting down PIE`): STOP.
- One run. If it errors, report the traceback; you may fix the PROBE SCRIPT and run once more.

## Final message
Each number tagged **measured** (read back) or **inferred** (and why). Name anything you
searched for and did not find. Short.
