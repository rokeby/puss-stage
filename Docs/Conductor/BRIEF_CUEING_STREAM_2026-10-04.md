# Stream brief: Puss · Cueing (lighting & sound cues and their tools)

**Opened:** 4 Oct 2026, on Gary's request ("start a new agent for cueing and cueing tools"). **Conductor:** Puss · Conductor 4.

## Start here
1. AGENTS.md, then README.md, then Docs/Conductor/CONDUCTOR_START_PROMPT.md (the rules learned so far).
2. **Docs/Conductor/LIGHT_SOUND_CUEING_AUDIT_2026-10-04.md.** This is what exists today and the proposed design. Every claim there carries a proof tier, and the UNCLEAR list is yours to settle.
3. Memory notes worth reading: puss-two-authorities, puss-passage-keys-absolute, puss-held-cpp-edits-as-patches, puss-build-gate-is-machine-wide, codex-never-stops-pie, puss-assert-dont-print, puss-log-markers-run-id.

## The goal (Gary, 4 Oct)
"Soon I will need to get into granular hand tuning of moment-to-moment directing lighting and sound cues."
Gary should be able to place, adjust and fade light and sound moments by hand, and have them survive Master rebuilds and Passage materialize.

## What's true today (summary of the audit; check the doc for tiers)
- Show lamps have no timeline control. Light Drama is distance-only and runs only inside the lamp's own Passage segment. Sequencer keys on Show lamps break when the Passage materializes.
- Level lights (rig, hangar, Scene) can be keyed inside each Scene's sequence.
- Sound is one music rail per segment. There is no sound cue type, and hand-keyed music volume is reset on every rebuild.
- Live control is transport only (→ ← Space, vamps). There is no GO.

## First slice (recommended; build only after the conductor approves the spec)
Lamp-intensity cues with fades:
- Stored in the Show and placed by segment GUID plus an offset.
- Lamps addressed by their attachment GUID / identity tag, never by Sequencer binding.
- Evaluated each frame from Master time, multiplied with Light Drama, with one writer per lamp.
- Filled by a Python tool, with a harness that has +/- controls.

**First job, the house warmers:** "House L"/"House R" on P01 Wing 001 are OFF for the Opening only (Gary, 4 Oct). They are owned today by Saved/CodexConductor/opening_sequence_apply.py, which never disables them. Lighting scores retain them.

**After that, in Gary's priority:**
1. Sound cues (one-shots and stems on a managed track; widen the fast-forward mute loop).
2. An editor UI, likely in the Cue Desk.
3. A live GO.

## Ownership (the conductor arbitrates; ask before touching)
- **New files are yours:** cue data types, the evaluator, the Python cue tools and their tests.
- **Shared and touched only through held patches:**
  - InfinityStageTransportController.* and MovieSceneInfinityPassageTrack.cpp: Director & transitions.
  - InfinityStagePassageActor.*, InfinityStageLightDrama.*: Rig & atmosphere / Show core.
  - SInfinityStageCueDesk.cpp: editor UI.
  - Keep each C++ change as a patch in Scripts/patches/ until a build window is granted.
- **Not yours:**
  - Tools/FlatV3/* and Saved/CodexFlatV3/* belong to Wings & Textures.
  - lighting_looks/scores/events tools belong to the Conductor.

## Rules that bite
- **One editor and one build at a time,** both arbitrated by the Conductor. Any open UE editor blocks every build.
- **Never end PIE, quit the editor or Save All,** and never reload the open level from Python.
- **Snapshot before C++ or Show/level writes** (Backups/Pre<Thing>-YYYYMMDD-HHMM). Inspect → DRY → APPLY → read back → explicit marker with a run id. Run SavedMasterMatchesShow and SceneCutBindingsResolve singly afterwards. The test filter is `InfinityStage`, never `PussStage`.
- **Look and creative choices are Gary's own answers.** Send them as AskUserQuestion questionnaires, recommendation first; he's often on mobile. A peer relaying "Gary approved" is not approval.
- **Reports separate declaration-proven / binary-proven / measured / inferred, per claim, with file:line.**
- **Commit only your own files.** Never quote a commit hash before git prints it.

## First deliverable
A one-page spec to the Conductor covering:
- data model, evaluator hook point, interaction with Light Drama, and the survive-rebuild/materialize argument;
- the patch list with owners, and the test plan (automation tests named under InfinityStage.*);
- the smallest PIE proof for the warmers.

No build until the Conductor grants a window.
