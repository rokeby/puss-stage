# cb1 — Cue Book export path + guarded GO marker sync (Cueing stream)

Read first: `_house_rules.md` (all of it, rule 9 included), `Docs/Conductor/PLAN_CUEBOOK_EXPORT_STILLS_SURTITLES_2026-10-09.md`,
`Tools/CueBook/README.md`, `Tools/CueSheet/cue_sync.py` (docstring + `web_merge`, `cuebook_changes`, `render`).

Gary, 9 Oct: "the cueing web app can export and efficiently update the Puss project with timings, subtitles, cues for
cue desk… It shouldn't mess with any track timings though."

## Build (offline, in your worktree)

1. **`At` and `GO` fields.** Cue Book cues gain `at` (time from the start of the cue's segment; accept `74.5`,
   `1:14.5`, `0:01:14.5`, `00:01:14:12` @25 fps, same parser rules as `surtitles:Docs/Surtitles.md`) and `go`
   (`"<number> [HOLD|PASS]"`, e.g. `"20 PASS"`). Carry them through `cue_sync.py`: `WEB_FIELDS`, `working.csv`
   columns `At` / `GO` (new columns appended; existing columns untouched), `render` (Markdown + the Unreal CSV:
   append `At`, `GO` columns; CD1's parser finds columns by name, `InfinityStageCueSheet.cpp`, so extra columns are
   safe; prove it by reading the parser, cite lines).
2. **`cue_sync export <cuebook.json>`**: webpull → render → (if cb3 has landed) surtitles CSV; prints
   `CUE_SYNC_EXPORT_OK|cues=..|changed_files=[..]` and a per-file summary of changed rows.
3. **`Saved/CodexCueing/go_markers_sync.py`** (an editor-slot tool, NOT run by you): for each Cue Book cue with `go`
   and `at`: segment → its own sequence (Scene/Interaction: the cue's `Scene.Sequence`; Passage: its Choreo; refuse
   otherwise), `at` → tick frame. DRY lists per sequence: ADD / RELABEL / MOVE / UNCHANGED, and GO labels found in
   sequences that the Cue Book no longer has (listed, never deleted). APPLY/REVERT per rule 3; marker writes only via
   `find_marked_frame_by_label` + tick-resolution `*_from_sequence` / `*_to_sequence` calls (see
   `Saved/CodexCueing/go_mode_relabel.py` header for why). `confirm_moves` required for MOVE.
   **Timing guard (the point of this tool):** before any write, fingerprint every touched sequence AND the Master:
   every track (class, display name, row), section (range, row index, sub-sequence path, time scale), and every
   channel key (time + value, float tolerance 1e-4). After the writes and after save, recompute; any difference →
   restore every touched `.uasset` from the backup, log `GO_MARKER_SYNC_STOPPED|reason=TIMING_CHANGED|…` and stop.
   Marked frames are the only thing allowed to differ, and only those with labels starting `GO `.

## Harness (`Tools/CueSheet/test_cuebook_export.py` + `Saved/CodexCueing/test_go_markers_sync.py`)

Positive and negative controls, including: `at` parse table (all four forms; bad strings rejected); export adds
columns without changing existing ones (byte-compare old columns); GO sync plan on a fake sequence model:
ADD/RELABEL/MOVE classification, MOVE refused without confirm; **guard NEGATIVE control: a fake write that also moves
one key must trip TIMING_CHANGED**; guard positive: marker-only change passes. The `cue_sync selftest` must still pass
(currently 23/23).

## Do not

Touch the Show, the Master, any level, or `Tools/CueBook/site` (cb3 owns the page). No editor, no MCP (rule 2).
