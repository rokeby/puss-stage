# Spec: Lamp-intensity cues (Cueing stream, slice 1). 4 Oct 2026

**Status:** spec only. Nothing has been built, patched or run. No editor or MCP was used.
**For:** Puss · Conductor 4. **Source:** `Docs/Conductor/LIGHT_SOUND_CUEING_AUDIT_2026-10-04.md`.

**Tags:** **[decl]** = read in source today, **[meas]** = read from a file on disk today, **[inf]** = design or reasoning that has not been checked.

**Paths:**
- `IS/` = `Plugins/InfinityStage/Source/InfinityStage/`
- `IST/` = `…/InfinityStageTests/Private/`

## 1. Data model (Show-owned)

There is a new `USTRUCT FInfinityLampCue` in a new header, `IS/Public/InfinityStageCueLayer.h` (mine). Its fields:

- `FGuid CueGuid`, `float Number` and `FText Label`.
- **Anchor.** `FGuid SegmentGuid` plus `int32 OffsetFrames`, in Show tick-resolution frames, relative to the segment's start frame.
  - A negative offset is allowed, so a cue can be written as "Opening end − N" against the next segment.
- **Targets.** `TArray<FInfinityLampRef>`, each one a `(CueGuid, AttachmentGuid)` pair.
- **Level and fade.**
  - `float Level` is a multiplier on the authored intensity: 0 is off and 1 is authored.
  - `int32 FadeFrames` is a linear fade, and 0 means a snap.

The Show gains one array, `UPROPERTY TArray<FInfinityLampCue> LampCues`.
- Old assets load it as empty. This rests on tagged-property serialization [inf]. I will confirm it in the build window by loading the current Show and checking that `Cues.Num()` is unchanged.
- Python fills it with `set_editor_property`, through the guarded MCP route.
- Slice 1 has no colour, no sound, no `bWaitForGo` and no level-actor targets.

## 2. Evaluator

The evaluator is a pure function, `InfinityStageCueLayer::LampLevelAt(Cues, SegmentStarts, Lamp, MasterFrame) → float`.

**How a lamp's level is computed:**
1. Resolve each cue that targets the lamp to an absolute frame: segment start plus offset.
2. Sort those cues by (frame, Number, CueGuid).
3. Track through them:
   - Before the first cue, the level is 1.0.
   - Each cue fades linearly from the value at its own frame to its `Level` over `FadeFrames`.
   - A cue that starts mid-fade takes the value at that moment as its starting point.

There is no stored state, so forward play, reverse play and scrub give the same result. That settles the audit's reverse-scrub UNCLEAR by construction [inf until the PIE proof].

**Hook point.** The hook goes in `UInfinityStageTransportController::TickComponent`, straight after `CurrentFrame` is read (`IS/Private/InfinityStageTransportController.cpp:567`).
- It must sit **before** the vamp and claim early `return`s at `:580-583` and `:585-594` [decl]. If it sat after them, cues would freeze during vamps and on seam ticks.
- The transport already holds `Segments[]` with `SegmentGuid` and `StartFrame` (`IS/Public/InfinityStageTransportController.h:200-222`) [decl]. It therefore needs no per-frame compile.
- It runs in game worlds only, the same rule as drama (`PassageActor.cpp:1623`) [decl]. Writing in the editor would feed the capture hook, which writes live lamp values back into the Show as authored values (`ISE/Private/InfinityStageEditorModule.cpp:292-345`) [decl].
- The cost of that rule: cues are not visible on an editor scrub, only in PIE. An editor preview belongs to the UI phase.

**Lamp lookup.**
- At BeginPlay, a single `TActorIterator` pass maps the tag `InfinityStage.Attachment.<cue>|<att>` to the lamp actor. The tag is minted in `PassageActor.cpp:967-970` [decl].
- The map holds weak pointers and re-resolves any entry that has gone stale.
- No Sequencer binding is involved.

**Write.**
- The authored intensity is the Show's own `Attachment.Lighting.Intensity`. The rig scales it by the cue level.
- A level of 0 or below calls `SetVisibility(false)`, which keeps the drama shadow-cost rule. The code to copy is in `IS/Private/InfinityStageLightDrama.cpp:118-126` [decl].
- `SetIntensity` and `SetVisibility` are called only when the value changes.

**Invariants:**
- **A lamp with no cue is never touched.** This keeps the change from altering the look of anything uncued.
- A missing segment, or a missing tag, logs `INFINITY_CUE_LAYER_SKIP` once per run and is skipped.
- BeginPlay logs `INFINITY_CUE_LAYER_READY cues=<n> lamps=<resolved>/<targeted>`.

## 3. Light Drama (one writer per lamp)

The two writers run in different tick groups:
- The transport ticks in `TG_PostUpdateWork` (`TransportController.cpp:506`) [decl].
- Drama runs later, from the camera rig in `TG_LastDemotable` (`CameraRig.cpp:99`, `:432`) [decl].

If both wrote the same lamp, drama would silently win.

**The rule:** drama owns a lamp's intensity on a frame if and only if all three hold:
- `bStrikeOnApproach` is set;
- the frame is inside the lamp's Passage segment;
- the world is a game world.

These are the exact gates at `PassageActor.cpp:1267-1270` and `:1623`/`:1642` and `LightDrama.cpp:112` [decl]. On drama-owned frames the drama path multiplies its result by `LampLevelAt`, so the final intensity is authored × strike × cue. On every other frame the cue layer writes on its own.
- The two writers share one predicate, `DramaOwnsIntensity()`, so they cannot disagree.
- Slow-move only ever writes rotation (`LightDrama.cpp:129-134`) [decl], so it never conflicts.
- The claim that drama runs on every in-segment frame is [inf]. It depends on the camera rig driving that Passage. The PIE proof includes a control lamp that checks it.

**Recommendation: ship this as slice 1b, not in the first build.**
- The warmers have no drama. Both House L and House R carry `bStrikeOnApproach=False, bSlowMove=False` [meas, `Saved/CodexConductor/light_guid_audit_20261004-121338.json`].
- Until 1b lands, the tool and the evaluator both **refuse** cues that target strike lamps.
- This keeps the first build to two held patches.

## 4. Why cues survive rebuild, materialize and rematch

- **Retime.** Anchors are segment-relative and are resolved every tick from the transport's segment table. A retime or rematch therefore moves the cues with their segments.
  - This holds unless `Segments[]` is stale against the Show. That is the same exposure the transport already has [inf].
- **Materialize.** Materialize destroys and respawns the lamps (`PassageActor.cpp:885-892`) [decl]. The new lamps carry the same GUID tag, and the cue data lives in the Show, not on the actors.
- **Master rebuild.** The rebuild writes managed tracks only (`ISE/…SequenceBuilderLibrary.cpp:195-480`) [decl]. Cues are not in the Master at all.
- **Deleting a lamp.** If a lamp is deleted from the Show, its cue only warns; nothing crashes.

## 5. Patch list (held in `Scripts/patches/` until a window is granted)

| Id | Files | Owner | Size [inf] |
|---|---|---|---|
| — (new, mine) | `IS/Public/InfinityStageCueLayer.h`, `IS/Private/InfinityStageCueLayer.cpp`, `IST/InfinityStageCueLayerTests.cpp` | Cueing | ~250 lines |
| **CL-A** | `IS/Public/InfinityStageShowAsset.h`: include plus the `LampCues` array | Show core / Rig & atmosphere | ~4 lines |
| **CL-B** | `TransportController.h/.cpp`: an `FInfinityCueLayerRuntime` member, BeginPlay resolve, and one call at `:567` | Director & transitions | ~15 lines |
| CL-C (1b) | `LightDrama.h/.cpp`: a `CueScale = 1.f` argument. `PassageActor.cpp:1652`: pass `LampLevelAt` | Rig & atmosphere | ~12 lines |

The Python tool goes in `Saved/CodexCueing/lamp_cue_tool.py`, with an offline harness alongside it (mine). Its modes are INSPECT, DRY, APPLY and REVERT, and it writes `Show.LampCues` only.

What the tool resolves and refuses:
- It resolves lamp labels to GUIDs and segment labels to GUIDs.
- It refuses a missing label, a disabled lamp, a strike lamp (until 1b), a duplicate `CueGuid`, and any write outside `LampCues`.
- It snapshots to `Backups/PreLampCues-YYYYMMDD-HHMM`, saves the Show only, and reads the data back.
- Its success marker is `LAMP_CUES_APPLY_OK run=<id>`, emitted only after the asserted read-back.

The harness runs the planner against fixture JSON, with − controls that must fail: wrong label, strike lamp, overlapping write. Each control has a + twin that must pass.

## 6. Tests (`InfinityStage.CueLayer.*`, `EditorContext | EngineFilter`)

1. `Tracking.StepAndFade`: snap, linear fade, an interrupt mid-fade, and 1.0 before the first cue.
2. `Tracking.ScrubDeterminism`: a forward sweep, a reverse sweep and a shuffled order must match bit for bit.
3. `Anchor.FollowsRetime`: segment start +N moves the cue +N.
   - − control: the same cue anchored absolutely does **not** move.
4. `Anchor.MissingSegmentSkips` and `Target.MissingTagSkips`: `AddExpectedMessagePlain(…, Contains, 1)` checks that each fires exactly once.
5. `Apply.UncuedLampUntouched`: in a test world, a cued lamp changes and an uncued lamp keeps its intensity and visibility bit for bit.
6. `Apply.ZeroHidesLamp` and `Apply.EditorWorldNoWrite`.
7. Slice 1b only: `Ownership.StrikeInSegmentMultiplies` and `Ownership.OutOfSegmentCueAlone`.

After the build:
- run the full `InfinityStage` filter;
- after the APPLY, run `SavedMasterMatchesShow` and `SceneCutBindingsResolve` singly.

Pass criteria are read from the log, not from the console summary.

## 7. Smallest PIE proof: the house warmers

The proof applies two cues:
- `Opening +0: House L/R × 0, snap`;
- `P01 +0: House L/R × 1, fade F`. **F and its placement are Gary's** (see §8).

Gary drives PIE. The probe is a read-only MCP script that never ends PIE, never jumps the playhead and never saves. At each point it reads the Master frame, plus `IsVisible` and `Intensity` for House L, House R and one **uncued control lamp** on P01 Wing 001.

| Point (Gary navigates with → / ←) | Expect House L/R | Expect control |
|---|---|---|
| Opening, 1 s in | hidden | unchanged from authored |
| P01, mid-fade | visible, strictly between 0 and 1740 cd | unchanged |
| P01, after the fade | visible, 1740 cd (±0.5) | unchanged |
| ← back into the Opening | hidden again (settles the reverse UNCLEAR) | unchanged |

The run passes only if:
- every row matches;
- `INFINITY_CUE_LAYER_READY cues=2 lamps=2/2` appears in the log, stamped with this run's id;
- there are zero `INFINITY_CUE_LAYER_SKIP` lines.

Any failure means stopping and reporting. The REVERT is the tool's REVERT mode (empty `LampCues`) or the backup.

## 8. Open questions

- **Conductor:**
  - May I write the new files and the CL-A and CL-B patches now?
  - Should CL-C go in the same window or in 1b?
  - Who reviews CL-A and CL-B for their owners (Rig is parked)?
- **Gary (creative):** how the warmers come on at the Opening→P01 seam. I will ask him as a questionnaire.
- **Unchanged from the audit:**
  - Scene sub-section completion.
  - Live drama edits in PIE.
  - Scene-local audio contents.

  None of these blocks slice 1.
