# Cue Book → project: exports, stills, surtitles (plan, 9 Oct 2026)

Cueing stream. Gary's three asks (~03:05 UTC, relayed by Conductor 5):

1. "Making sure the cueing web app can export and efficiently update the Puss project with timings, subtitles,
   cues for cue desk, etc. It shouldn't mess with any track timings though."
2. "Make a still of each Passage, Scene, Transition etc for the Cue app's visual ref. Low priority - grab a visual
   for each actual cue where available."
3. "The subtitles system, built into cue desk in UE5 and also into cueing web app."

Nothing here touches the editor or the build until Conductor 5 books it. Tiers: **[decl]** read in source/config,
**[meas]** run and read back, **[inf]** inferred (reason given).

## The principle: the Cue Book never writes a track

Everything the Cue Book holds reaches Unreal as **files Unreal reads at runtime**, not as Show or Sequencer edits.
Timings are **relative to the start of their segment** (the same convention as the surtitles branch,
`surtitles:Docs/Surtitles.md`), so they follow a retime instead of fighting it.

| What | Where it lands | Read by | Writes an asset? |
|---|---|---|---|
| Cues (lines, light, sound, action, notes, video cue) | `Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv` (exists, `cue_sync render`) | CD1 script panel / Cue Director (builds tonight) | no |
| Cue time in segment (new `At` column) | same CSV | CD1 now ignores it; later the script cursor can follow the playhead | no |
| Surtitles | `Content/InfinityStage/CueSheet/Puss_Surtitles.csv` (the surtitles branch's path and columns) | `InfinityStageSurtitles` (branch `surtitles`, not on master, not built) | no |
| Stills | `Tools/CueBook/site/stills/` + `stills.json` | the Cue Book page | no |
| GO points (optional, phase B) | GO marked frames in the segment's own sequence | the transport's GO holds | **yes: marked frames only, guarded** |

So "doesn't mess with track timings" holds by construction for everything except GO markers. For those, a guard
**proves** it (below).

## 1. Export / update path (brief `cb1_cuebook_export.md`)

**Pull.** Two routes exist and are measured: Drive export of "Puss Cue Book data" (cues tab first; no passcode;
Claude runs it) and `cue_sync cuebook` (needs `CUEBOOK_PASS`) **[meas 9 Oct: 96 cues, 2 real edits found]**. Both
end in `cue_sync webpull`, which merges into `Docs/CueSheet/working.csv` with conflicts listed
(`web_report.md`), then `render` writes the cue-sheet CSV for Unreal.

**New:**
- `At` field on Cue Book cues (segment-relative, `74.5` / `1:14.5`), and an optional `GO` field (number + HOLD/PASS).
  Page shows them; `cue_sync` carries them to `working.csv` and the CSV.
- `cue_sync export` = pull + render + surtitles CSV in one command, printing what changed per file
  (`CUE_SYNC_EXPORT_OK cues=… surtitles=… changed_files=…`).
- **GO marker sync** (`go_markers_sync.py`, editor slot, DRY/APPLY/REVERT, rule-3 shape): for each Cue Book GO,
  resolve segment → sequence and `At` → frame; DRY lists adds / relabels / moves per sequence. APPLY writes only
  marked frames whose label starts `GO `.
  **The timing guard:** before and after, fingerprint every section (track class, row, range, sub-sequence) and
  every channel key (time, value; float tolerance 1e-4 per rule 9) of each touched sequence **and** the Master;
  any difference → restore from `Backups/PreGoMarkerSync-<run>` and `GO_MARKER_SYNC_STOPPED|reason=TIMING_CHANGED`.
  Moving an existing GO needs `confirm_moves=true` (a moved GO changes when a hold happens, though no track moves).
  Uses `find_marked_frame_by_label` and tick-resolution reads/writes (rule 4; `go_mode_relabel.py` notes why).

## 2. Stills (brief `cb2_cuebook_stills.md`)

Driver over the existing `Saved/CodexConductor/scene_stills.py` (supports Passages, Scenes, `Opening`, and
Interactions `I<n>` by label, `scene_stills.py:114-117, 646-649` **[decl]**), run by Conductor 5 inside a PIE it
already started:
- one still per segment at a configurable fraction (default 0.5; transitions 0.3, after the lights fold);
- one per Cue Book cue that has an `At` time ("where available");
- a publish step (offline): PNG → 1280-px JPEG into `Tools/CueBook/site/stills/<key>.jpg` and a
  `stills.json` manifest (segment key, Unreal id, master frame, capture time, per-cue files). The page reads the
  manifest instead of its hard-coded map, so new stills appear without a page change.
- **Segment mapping** in one editable file `Tools/CueBook/segment_map.json`: sheet name → Show segment
  (`Passage 4` → P04, `S1 Animals` → S1, `Scene 3` → S3, the n-th `Transition` → `I<n>`, `Curtain opening…` →
  Opening, `Ending` → Closing). Unmapped names are listed, never guessed. Today's map was by name and is
  **[inf]**; the I2/I3 records confirm the Transition ↔ Interaction order (`SCENE_EXIT_SHADOW_CURTAIN_PLAN`:54).
- Stills go on the public GitHub page (images only; no script text). Gary already accepted that for the first ten.

## 3. Surtitles (brief `cb3_cuebook_surtitles.md`)

**One data model, the one already written:** the surtitles branch's sheet — columns `Segment, In, Out, Speaker,
Text, Notes`, segment keys `S<n>/P<n>/I<n>` or a cue label, times relative to the segment
(`surtitles:Docs/Surtitles.md`) **[decl]**. No second format.

- **Cue Book:** a "Surtitles" view per segment: lines with In/Out, add/edit/cut, the same logged, conflict-checked
  saves as cues (new `surtitles` tab in "Puss Cue Book data"; `Code.gs` gains `listSurtitles` / `saveLine` /
  `addLine` → Gary pastes and redeploys once). A "make a surtitle from this line" button on a cue copies its text.
- **Export:** `cue_sync export` writes `Puss_Surtitles.csv`; the UE side reloads it within ~1 s
  (`Surtitles.md` "Reloading") **[decl, not run]**.
- **UE / Cue Desk:** the runtime overlay is the surtitles branch (owned by the "Surtitle system for show" session).
  It must reach master and a build window first. Showing and nudging lines inside the Cue Desk is later C++ (a Cue
  Desk panel listing the current segment's lines), not tonight.

## Order and who runs what

| Step | Who | Needs |
|---|---|---|
| cb1 offline: `At`/`GO` fields, `cue_sync export`, GO sync tool + harness | Codex (worktree) → Cueing reviews | nothing |
| cb3 offline: Cue Book surtitles view + Code.gs + export, tested on the mock | Codex → Cueing reviews | nothing |
| cb2 offline: stills driver + publish + harness | Codex → Cueing reviews | nothing |
| Code.gs redeploy (surtitles tab) | Gary | 3 min |
| Stills run | Conductor 5, editor slot (PIE) | the bake done |
| GO marker sync APPLY | Conductor 5, editor slot | Gary's yes per GO change |
| Surtitles branch → master + build | Surtitle session + Conductor 5 | a later build window |

## Open questions for Gary

1. GO points: should the Cue Book be able to **move** GOs, or only add/relabel? (Plan: add/relabel free, moves
   need an explicit confirm.)
2. Surtitles: edited only in the Cue Book from now on (the sheet tab becomes an export), or also in the master
   Google Sheet? Two editable sources would need a merge like the cue sheet's.
