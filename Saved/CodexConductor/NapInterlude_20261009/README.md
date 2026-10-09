# P79 Nap interlude — conductor runbook

Status: offline-authored only. `nap_interlude.py` and its fake-backend harness
have not opened Unreal, Blender, PIE, or MCP. The Show Asset remains authority.

## What the tool owns

- one Sequence cue, `Nap — battery change`, inserted only in the exact order
  `S4 -> I4 -> Nap -> P05`, immediately after I4 and immediately before P05;
- `/Game/InfinityStage/Dev/Sequences/LS_Nap_BatteryChange`;
- four tagged level actors: sleeping Puss, a CineCamera, and at most two dim
  warm/cool Rect Lights;
- only the tracks, keys, cut, and markers in that new sequence;
- an MRQ job specification for exactly one loop.

It refuses if S4/I4/P05 are not contiguous, if the I4/P05 GUIDs drift, if the
I4-end/P05-start boundary drifts, or if asked to insert between S4 and I4. It
does not edit S4, I4, P05, any Passage row, or any existing sequence. Creative
defaults are all in `nap_interlude_args.json`. Puss uses the catalogue's
`A_Cat_Rest_Sleep_to` at an explicit held pose; the authored Z keys supply the
seamless breathing loop. New light shadow casting is off by default.

UE 5.8 mints the Nap cue GUID during the managed-Master rebuild. The tool
never writes `cue_guid`: after insertion and rebuild it reads the minted value through
`GuidLibrary.conv_guid_to_string`, immediately persists it in the APPLY record,
and thereafter requires the exact `Nap — battery change` label/GUID pair for
read-back, fallback-job identity, idempotence, and REVERT. REVERT refuses before
mutation if either half of that recorded identity has drifted.

## Ordered live slot

1. Start from the canonical Puss editor and vertical-slice world, with PIE/SIE
   stopped, Sequencer closed, and an exact empty dirty-package census. Do not
   close, restart, or otherwise control the editor from this tool.
2. Choose a new run id. Keep `mode=DRY`, set `confirm` to
   `DRY NAP <run>`, and execute `nap_interlude_run.py` through the guarded
   `ExecuteProjectPythonFile` request. Require `P79_NAP_DRY_OK`.
3. Review the report and PNG. Copy the DRY-discovered I4 and P05 GUIDs into
   `expected_interaction4_guid` and `expected_passage5_guid`. Gary chooses loop and
   wake-tail duration, breathing amplitude/period, held sleep-pose fraction,
   cat/camera/light transforms, focal length, drift, colors, and intensities.
   The loop must contain a whole number of breathing periods.
4. Repeat DRY with those pinned GUIDs and final values. APPLY must use the same
   snapshot and plan: `mode=APPLY`, a fresh run id, and
   `confirm=APPLY NAP <apply-run>`. It creates
   `Backups/PreNapInterlude-<apply-run>` plus an exclusive record before its
   first mutation, checks the exact four-package dirty census, saves only the
   Show, Master, level and new sequence, reloads, and emits
   `P79_NAP_APPLY_OK` only after read-back.
5. Run these separately and read their Success lines in the Unreal log:
   `InfinityStage.Editor.SavedMasterMatchesShow`, then
   `InfinityStage.Editor.SceneCutBindingsResolve`. MCP transport success is not
   either test result.
6. Review `nap_fallback_job_<run>.json`. It specifies one 20-second loop from
   the managed Master for the Saturday MRQ workflow. The current Cue Desk only
   exposes video for Scene ordinals, so do not claim the Nap clip is selectable
   until that code gate is implemented and tested.
7. In PIE, verify one continuous breath across repeated vamp seams, one GO 45 to
   release the loop, the one-second wake tail, arrival at the P05 start with no
   second cue-book HOLD, P05 entry,
   lights, shadows, framing, and actual battery-change time. This is rendered
   and operational acceptance; offline green is not a substitute.

## REVERT

With the applied record unchanged: use a new run id, set `source_run_id` to the
APPLY run, and confirm `REVERT NAP <source-run>`. REVERT takes
`Backups/PreNapInterludeRevert-<run>`, removes only the exact cue and tagged
actors, rebuilds the Master, and moves (does not delete) the sequence to
`/Game/InfinityStage/Dev/Sequences/_Reverted/`. Run both tests again.

## Operator semantics

The only GO marker is `GO 45 PASS Nap — battery change`, at the same frame as
`InfinityStage.VampEnd`. Its parsed label exactly equals the Master cue label,
including U+2014. Existing transport semantics consume RIGHT/GO to release the
armed vamp and play at 1x to the Nap segment end, which is the P05 start. `PASS`
cannot create another hold. The controller still records its normal segment-end
rest at that shared frame; offline authoring does not claim P05 has advanced
beyond its first frame. Confirm that exact handoff in PIE.

Offline harness:

```powershell
python Saved/CodexConductor/NapInterlude_20261009/test_nap_interlude.py
```

Expected: `P79_NAP_HARNESS_OK|positive=3/3|negative=14/14|checks=45`.

## Job 97 / E18 in-place revision (9 Oct evening)

Do not rerun P79 insertion: the Nap is already applied. Job 97 is
`e18_nap_revision.py`, launched by `e18_nap_revision_run.py`; editable live
values and mode/confirmation are in `e18_nap_revision_settings.py`. It anchors
the existing cue on minted GUID `211B6129497610E7977707AA939D7763`, never writes
`cue_guid`, and renames both cue and same-frame GO marker to
`Interlude: Puss Sleep/Wet Tennis Ball/Battery`. It pins the recorded Master
range at 1490.64–1511.64 s and refuses or reports any timing change.

The patch hides the existing cat reversibly, puts the breath on the ground-level
camera (Z 45 cm, 1.25 cm rise/fall, 0.20 degree roll, four-second seamless AUTO
cycle), dims the two P79 lights to 18/8, and audits I1–I5 in I4-first order. For
each existing named shadow-spot pair it adds explicit zero-intensity/unspawned
keys at the sequence end; zero bindings means absent, while exactly one refuses.

Run DRY first with `DRY E18 <run>`, review its exact dynamic package census,
JSON/PNG and stills plan, then APPLY from unchanged state with
`APPLY E18 <new-run>`. APPLY backs up every named package before mutation,
requires precisely that dirty census, target-saves it, and reads it back before
`E18_NAP_REVISION_APPLY_OK`. Run `SavedMasterMatchesShow` and
`SceneCutBindingsResolve` separately, then capture entry, breath peak, both vamp
seam sides, and I4 terminal darkness. PIE/rendered acceptance must prove no cat,
CAT'S VIEW, near-dark ambience, seamless breath, one-GO release, unchanged P05
handoff, and terminal darkness across all interactions.

REVERT uses `REVERT E18 <apply-run>` plus `source_run_id=<apply-run>`. It takes a
fresh backup, restores complete recorded cue/marker, cat, camera, lights and spot
channels, target-saves the same package set, and requires exact semantic
read-back. Offline harness command:

```powershell
python Saved/CodexConductor/NapInterlude_20261009/test_e18_nap_revision.py
```

Expected: `E18_NAP_REVISION_HARNESS_OK|positive=3/3|negative=15/15|checks=26/26`.
