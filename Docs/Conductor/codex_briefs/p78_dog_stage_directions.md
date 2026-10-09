# P78 — Dog stage directions in the Cue Book + Cue Director (Cueing stream; offline, medium effort)

Read first: `_house_rules.md`; `Tools/CueBook/README.md`; `Tools/CueBook/site/index.html` (cue editor, At/GO/pause
hints from P66, running order P48, print presets P54, undo P66); `Tools/CueBook/apps_script/Code.gs` (FIELDS,
validation); `Tools/CueBook/site/print_presets.json`; `Tools/CueSheet/cue_sync.py` (`WEB_FIELDS`, render, print);
`Docs/Go1TelemetryProgress.md` (READ ONLY; never touch the GO1, the Go1Input plugin or go1_pi_bridge);
`Plugins/InfinityStage/Source/InfinityStage/{Public,Private}/InfinityStageCueSheet.*`, `InfinityStageRehearsalBar.*`,
`InfinityStageDirectorHud.*` (Cue Director notes / rehearsal bar). Dedupe done: no dog/GO1/treadmill fields exist.

Gary, 9 Oct, "very crucial": the Cue Director and the Cue Book must show what the DOG is doing at each point. The dog is
a performer with stage directions, ultimately for Gary (who operates it):
(a) physical action in plain words (running, trotting, crouching, still, looking, climbing…);
(b) technical state: the GO1 mode to be in;
(c) treadmill on/off, part of the same stage direction (not its own slot).

## Facts to respect

- The GO1's telemetry `mode` field read 0 in every state (standing, move mode) when measured
  (`Docs/Go1TelemetryProgress.md:135-138`), so the "mode" here is a DIRECTION for the operator, named the way the
  operator switches it on the handheld remote, never a value read from the robot. Derive the list from the doc
  (cite lines) and the remote button names in `Go1RemoteReceiverComponent.h` (`EGo1RemoteButton`), plain words first:
  e.g. "Lying down (damped)", "Standing", "Walk / trot", "Run", "Stairs / climb" — keep only modes the doc supports;
  mark anything inferred. Add "—" (unspecified) as the default.

## Build

1. Cue fields (all optional): `dogAction` (free text), `dogMode` (enum above, stored as a short id), `treadmill`
   (`on` / `off` / empty = no change). Code.gs FIELDS + validation; page editor (one "Dog" group with plain hints,
   tooltip and "?" like At/GO); cue card shows one compact line "DOG: trotting · Walk/trot · treadmill on"; running
   order shows it; print presets: Gary's preset and Stage manager include it, plus a new "Dog" preset (dog line +
   context). Undo works for the new fields (P66 path). Old-deployment gating: hide the Dog group until the updated
   script answers (as for at/go/pause).
2. A "current dog state" carry-forward: since most cues don't restate the dog, the page shows the dog state in force at
   each cue (last stated mode/treadmill above it, greyed when inherited). Same rule in prints.
3. cue_sync: carry the three fields to `working.csv` (appended columns "Dog action", "Dog mode", "Treadmill") and the
   Unreal cue-sheet CSV (columns by name; CD1 ignores unknown ones today).
4. Cue Director (Unreal): show the current and next dog direction in the script panel / rehearsal bar. This is C++:
   deliver as a HELD patch `Scripts/patches/cueing_P78_dog_directions_cuedirector.patch` against current master
   (+ test), reading the new CSV columns in `InfinityStageCueSheet` (role "Dog"), carry-forward identical to the page.
   Keep it small; do not touch tonight's stack patches (`Scripts/patches/stack_0919_*`, SW1, HUD1).

## Harness

Python (cue_sync fields + carry-forward + print preset "dog"), browser harness (edit, display, inherited state,
treadmill, undo, old deployment hides the group), automation test in the held patch. Report counts. If git cannot
commit (index.lock), leave the files and list them. Say clearly that Code.gs changed (Gary must redeploy).
