# Codex job 96 — P04 -> S4 total-dark hard cut (offline, 9 Oct 2026)

Nothing ran in Unreal, MCP, PIE, or Blender. No `.uasset`/`.umap` was changed. The
conductor owns live execution and commit.

## Outcome

- **declaration-proven:** The delivered DRY/APPLY/REVERT tool changes only
  `LS_DevScene_04`: it extends the existing Entry Handoff cut to frame 405,
  deactivates (does not delete) the v4 glide cut, and leaves the existing Klara
  nested slot and exit cut unchanged
  (`Saved/CodexConductor/P96S4DarkCut_20261009/p96_core.py:94-180`).
- **declaration-proven:** At the hard cut, the tool requires exactly one resolved
  root entry camera, root exit camera, and Klara nested camera in the currently
  loaded show world. APPLY refuses if any binding is unresolved
  (`p96_editor.py:163-193`; `p96_core.py:120-130`).
- **declaration-proven:** The live DRY performs the exact census requested. It
  enumerates materialized P04 child light actors, S4-hangar light/emissive actors,
  Klara pre-cut light/environment actors, and exactly one P04 backcloth. Every
  actor path, range, existing visibility track and group count is written to
  `p96_dry_<run>.json`; APPLY is pinned to its whole-state SHA-256 digest
  (`p96_editor.py:251-302,416-472`).
- **declaration-proven:** P04 lights and S4-hangar light/emissive actors are hidden
  for all of S4. Klara's lights/environment are hidden only through frame 405 and
  restored at the cut. The P04 backcloth is hidden from 405 through scene end, so
  its existing fall remains untouched and her later pullback cannot reveal the
  raised cloth (`p96_editor.py:267-278`; `p96_core.py:153-180`).
- **declaration-proven:** Visibility tracks bind `("bHidden","bHidden")`, store
  `False` (not visible), and use `RESTORE_STATE`. Exact existing coverage is
  deduplicated; inert `bHiddenInGame` tracks are reported but not trusted; other
  overlapping working tracks refuse APPLY (`p96_core.py:66-92`;
  `p96_editor.py:328-361`).
- **declaration-proven:** APPLY writes a record and
  `Backups/PreP96S4DarkCut-<run>` before mutation, admits exactly
  `LS_DevScene_04` in the dirty census, target-saves only that asset, and performs
  pre/post-save read-back. REVERT validates the recorded applied state, backs it
  up, removes only recorded tracks/bindings, restores the two camera fields,
  target-saves, reads back, and archives the record (`p96_editor.py:303-415,439-533`).

## Dedupe and traps

- **measured (offline source census):** `s4_backcloth_hold.py` already provides a
  Geometry Cache hold, but its KEEP_STATE result is explicitly inferred until PIE
  (`Saved/CodexConductor/s4_backcloth_hold.py:1-25`). Job 96 does not duplicate or
  depend on it; the reversible post-cut visibility hide is narrower.
- **declaration-proven:** Stable GUID conversion uses
  `GuidLibrary.conv_guid_to_string`; enum wrappers and suffixed channel names are
  normalized. The tool never writes `cue_guid`, calls `set_light_color`, edits a
  StaticSwitch, imports FBX, or uses a CineCamera component accessor because none
  is on this write surface (`p96_core.py:28-39`; `p96_editor.py:57-63`).
- **declaration-proven:** The tool never uses Save All, asset deletion, or permanent
  file deletion. Klara actors may be possessed by the show sequence, but the exact
  dirty census refuses any Klara package before any save (`p96_editor.py:405-413`).

## Verification

- **measured (offline harness):** `python
  Saved/CodexConductor/P96S4DarkCut_20261009/test_p96.py` passes **15/15**: 2
  positive, 9 negative and 4 trap/static-safety controls
  (`harness_result.json:1-10`; `test_p96.py:54-149`). Python compilation also
  passed for the core, editor adapter and runner.
- **inferred:** The edit will produce the requested total-dark arrival and clean
  hard cut. This remains unproved because the job was explicitly offline and light
  contribution/camera precedence require live read-back and rendered PIE.
- **inferred:** Hiding the backcloth after frame 405 is visually equivalent to
  keeping it down for Klara's pullback. This is intentionally chosen over the
  unproved cache hold and must be judged in the supplied stills plan.

## Conductor run order and acceptance

Follow `Saved/CodexConductor/P96S4DarkCut_20261009/README.md`: clean census -> DRY
-> inspect exact census/resolutions -> APPLY -> saved read-back -> focused cut tests
-> uninterrupted P04/S4 PIE plus rehearsal-jump stills. The confirm strings are
`APPLY P96 S4 DARK CUT` and `REVERT P96 S4 DARK CUT`.

`stills_plan.json` covers frames 0, 104, 118/119, 319, 404/405/406, Klara's
curtain-crossing/rest frames, the last Klara frame and the exit cut. Geometry Cache
captures must pose, decode/tick, re-pose the same frame, then capture.

**Open until live DRY:** the exact actor counts and whether any pre-existing working
visibility track conflicts. **Open until PIE:** zero light leakage, correct camera
ownership on 405, no one-frame flash, and no curtain reappearance. A DRY refusal or
UNCLEAR rendered verdict is preferable to widening the target set.

Git note: `p96_args.json`, `stills_plan.json`, `harness_result.json`, and this
folder's README are ignored by the broad `Saved/Codex*/**` rule; the conductor must
force-add those four data/docs files when committing.
