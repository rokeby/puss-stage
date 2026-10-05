# Retime robustness audit — 4 Oct 2026

Gary, 4 Oct: *"scene and passage timings will naturally shift, so there needs to be a robust way for that to happen
without everything breaking."* Offline audit only. No Unreal, MCP or build was run. Tags: **[decl]** = read in
source/config, **[meas]** = a recorded run, **[inf]** = inferred, with the reason.

## Answer (5 lines)

1. **A Scene or Opening that is lengthened rigidly is mostly safe.** Scene and Passage sections, Passage camera/wing keys (patch K), Choreo, music, render cuts and Scene-internal markers all re-derive from the compiled cursor [decl].
2. **A Passage whose duration changes is NOT safe.** Wing pass frames move, but camera and wing-channel keys stay at their old section-relative frames, so the score drifts off the wings. Keys past the new end are dropped from play, and pins past it are deleted [decl].
3. **Handoff cameras are not rematched by a rebuild.** Only `extend_scene_playback.py` rematches, and only the Scene it extends. A Passage resize leaves the neighbouring Scenes' Entry/Exit views stale [decl].
4. **The safe tool blocks the common case.** `extend_scene_playback.py`'s KEY GATE predates patch K. It refuses any retime ahead of a Passage with a varying channel, so it would refuse the Opening because of P01 [decl].
5. **No test grows a Passage.** None covers music, handoffs or cut coverage after a retime either. Section 4 proposes one transient "grow everything" test plus a GUID-relative rule for tools.

## 1. Inventory: what is anchored, and does it follow?

**Legend for "Scene/Opening grows":** ✅ = follows. **Legend for "Passage duration changes":** ✅ = follows; ❌ = the content keeps its old relative frames.

| # | Item | Anchor | Scene/Opening grows | Passage duration changes | Evidence |
|---|---|---|---|---|---|
| 1 | Segment cursor (all starts/ends) | Cumulative sum of Scene lengths (sequence playback when `bUseSequenceLength`, else `DurationFrames`) plus Passage lead-in + intervals + tail | ✅ | ✅ | [decl] `InfinityStage/Private/InfinityStageCompiler.cpp:17-40, 215-226, 254-316` |
| 2 | Wing pass frames | `FirstPassFrame + ΣIntervalToNext`, recompiled | ✅ | ✅ | [decl] `Compiler.cpp:255-287` |
| 3 | Passage sections | Matched by GUID, `SetRange` to the compiled range | ✅ | ✅ (range only) | [decl] `ISE/Private/InfinityStageSequenceBuilderLibrary.cpp:244-311` |
| 4 | Passage camera + wing channel keys (patch K) | Section-relative after `MoveSection(Δstart)` | ✅ rigid shift | ❌ Keys are not stretched or re-fitted to the new pass frames, and keys past the new end are not evaluated | [decl] `Builder.cpp:300-309`; [decl test] `InfinityStagePassageKeyCarryTests.cpp:84-119` (Scene grow only) |
| 5 | Passage pins (`PinnedPassageFrames`) | Relative frames | ✅ | ❌ Pins at or past the new duration are **deleted** on rebuild, which cannot be undone except from a backup | [decl] `Builder.cpp:286-298` |
| 6 | P01 wing score "15 s early" | Was authored before patch K | ⚠ Stays 15 s off; patch K preserves an existing offset and does not repair it | — | [inf] from memory `puss-passage-keys-absolute` (not re-read from the asset) |
| 7 | Scene / Sequence sub-sections | GUID, `SetRange` only (no `MoveSection`) | ✅ | ✅ | [decl] `Builder.cpp:322-364`. [meas, indirect] SavedMasterMatchesShow passed after the Scene 1 0→5270 extension (`Saved/CodexSoftGoods/extend_scene_playback.py:16-19`) |
| 8 | Everything inside a Scene sequence: shots, hangar rise sub-sections (`LS_S*_HangarRise`), exit-block cut [W0,W1) and `EXB` markers, vamp markers, GO markers, hidden changeover | Relative to that Scene's playback start | ✅ | ✅ | [decl] `InfinityStage/Private/InfinityStageTransportController.cpp:134-140, 172-182, 255-265` (all `MarkedFrame - PlaybackStart`). Hangar inside the Scene: [decl] `Docs/Conductor/SCENE_EXIT_BLOCK_PLAN_2026-10-04.md:187` |
| 9 | Choreo sections | GUID, `MoveSection` then `SetRange`, then verify, then recreate | ✅ (FollowsRetime 72000→312000 [meas], commit 2684fb7) | Range follows. Choreo content stays fixed; past its end it is silent (warned `INFINITY_CHOREO_SHORT`) | [decl] `Builder.cpp:367-483`. **Not in the saved Master today**: the apply was reverted after a Sequencer crash (commit 0506a2f) |
| 10 | Music rail sections | GUID, `SetRange` only, `SetStartOffset(rail in + offset)`, envelope reset each build | ✅ [inf] | Plays more or less of the rail; fades re-fit | [decl] `Builder.cpp:78-95, 485-608`. **Untested for retime** (see §3) |
| 11 | Render wrapper camera cuts | Cleared and re-laid from the compile on every call | ✅ | ✅ | [decl] `Builder.cpp:612-793` |
| 12 | Scene Entry/Exit handoff cuts + camera views | Cuts relative to the Scene's playback range. Views are copied from the Passage camera at the boundary **Master frame** | ✅ if rematched | ❌ until rematched: the view at the Passage end/start changes, and nothing rematches automatically | [decl] `ISE/Private/InfinityStageSceneHandoffBuilder.cpp:225-234, 249, 425-461`. Callers: `CameraPilotLibrary.cpp:590-602` and the extend tool only. Stale detection: `HandoffWatch.cpp:166` |
| 13 | Opening internal moments (curtain release, swells), Opening walk-in | Marked frames `OPN …` in the Opening sequence. Last-applied record is in Opening frames | ✅ for other retimes | — | [decl] `Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md:172-183`; `opening_sequence_apply.py:444, 907` |
| 14 | Artist tracks on the Master | Absolute Master keys; the rebuild leaves them alone | ❌ | ❌ | [decl] `LIGHT_SOUND_CUEING_AUDIT_2026-10-04.md:28`. **None today** [meas, byte-grep in that audit] |
| 15 | Hangar strike | `strike_after_land_seconds` (relative to the land) in timing data | ✅ [inf] | ✅ [inf] | [decl] `Saved/CodexConductor/atf_hangar_timing_apply.py:33, 185, 235` |
| 16 | Light Drama | Distance-driven, evaluated per Master frame through the rig | ✅ [inf] | ✅ by distance [inf] | [decl] `OPENING_SEQUENCE_PLAN:118-121`. The distance→frame map is recompiled (row 2) [decl] |
| 16a | Mechanism `ExplicitOriginFrame` | **Absolute Master frame** | ❌ | ❌ | [decl] `InfinityStage/Private/InfinityStagePassageActor.cpp:1381-1389`, `Public/InfinityStageTypes.h:645` |
| 16b | Light Drama slow move | Absolute Master seconds, periodic only | Phase shifts, no event moves | same | [decl] `PassageActor.cpp:1625` |
| 16c | Opening curtain hold/exit (`CurtainHoldFrames` 240000, exit 48000) | Fixed counts from the segment start, not scaled to the segment length | ✅ start. A shortened Opening can end with the curtain still closed [inf] | — | [decl] `InfinityStage/Private/InfinityStageShowRoot.cpp:118-137`, `Types.h:859-870` |
| 16d | Shot-step boundaries, GO cues (Scene or Choreo marks) | Child mark − child playback start + segment start | ✅ | ✅ | [decl] `TransportController.cpp:237-286, 324-378` |
| 16e | Hangar rise | Nested in the Scene child; mapped from the compiled segment start, recompiled every call | ✅ | ✅ | [decl] `InfinityStage/Private/InfinityStageArrival.cpp:1029-1124` |
| 16f | Celestial phase | Integrated over compiled Passage durations | ✅ | ✅ | [decl] `Compiler.cpp:413-473` |
| 16g | Effect pump/flicker | `World->GetTimeSeconds()` (world time; does not scrub) | n/a | n/a | [decl] `InfinityStage/Private/InfinityStageEffectSource.cpp:691-726` |
| 16h | PassageResize tool | Edits wing count and `TailFrames`. Lists Master marked frames and artist tracks as "not rippled". Never rebuilds the Master | — | ❌ for artist content | [decl] `ISE/Private/InfinityStagePassageResizeLibrary.cpp:140-200, 253-408` |
| 17 | `walkin_transitions.json` OPENING row | `minimum_end_frame 375`, `landed_s 6.33` | ❌ stale | — | [decl] `OPENING_SEQUENCE_PLAN:233` (Look & camera's file) |

## 2. Tools that store absolute frames

| Tool | What it stores | Class | After a retime | Minimal fix | Evidence |
|---|---|---|---|---|---|
| `Saved/CodexSoftGoods/extend_scene_playback.py` KEY GATE | — | Over-guard | **Refuses** any retime ahead of a varying Passage channel (P01, so the Opening) | Delete the gate. Replace it with a post-rebuild check that every later Passage's keys moved by exactly Δ | [decl] `:27-33, 193-212, 306-311` |
| `Saved/CodexConductor/p04_bay3_trace.py` | `TARGET_FRAME = 25433910` absolute | Absolute | Traces the wrong bay | Resolve it from P04 GUID + bay 3 pass frame at run time, or retire it (one-off) | [decl] `:44, 239, 291-294` |
| `Saved/CodexConductor/s3_wave_slides_apply.py` | `EXPECTED_PLAYBACK=(0,6240)`, strike 10.0 s | Guard (Scene-relative) | Refuses if S3's length changes. Fail-safe, but blocks a rerun | Drop the playback-equality guard and keep the strike-relative check | [decl] `:33-35, 76-132` |
| `walkin_transitions.json` (Look & camera) | `minimum_end_frame`, `landed_s` | Absolute (Opening) | Rebuilds a stale walk-in | Key by the Passage GUID, end = compiled P01 start at run time | [decl] `OPENING_SEQUENCE_PLAN:233` |
| `p01_hallway_pingon.py` (unapplied) | Resolves P01 at run time, but **writes absolute Master artist keys** | Writes row 14 | Its keys strand on the next retime | Key the lamp in the P01 Choreo instead (row 9) once Choreo is re-enabled | [decl] `OPENING_SEQUENCE_PLAN:231` |
| `lighting_looks_p04_driver.py` | `pass_frames` recomputed from compiled P04 start + intervals | Re-resolved ✅ | Safe, but the label lookup `"P04 Wing %03d"` breaks if wings are renamed | Key by cue GUID | [decl] `:190-212` |
| `opening_sequence_apply.py` `last_applied_frames` | Opening-relative moments | Relative ✅ | Safe | — | [decl] `:444, 907` |
| `atf_hangar_timing_apply.py` | Seconds after land | Relative ✅ | Safe | — | [decl] `:33, 235` |

**Not swept line by line (UNCLEAR):**
- the rest of `Saved/CodexConductor/*.json` request and record files;
- `Saved/CodexFlatV3/swapkit/*`, including `pf_saved_master_queue_*.py` and `st_pie_stills_driver.py`;
- `Saved/CodexCueing/choreo_request.json` and `scene_external_sound_request.json`. The last two are keyed by cue GUID per commit 4bf071c [decl, commit message only].

A delegated grep sweep of these was launched and had not returned when this was written.

## 3. Tests

| Test | Fixture | Covers | Does not cover |
|---|---|---|---|
| `InfinityStage.Editor.PassageKeysFollowSection` | Transient | Scene grow → later Passage moves by Δ; keys keep their section-relative frame; idempotent rebuild [decl] `PassageKeyCarryTests.cpp:20-125` | Passage duration change, pins, Passage-before-Passage shifts |
| `InfinityStage.Cueing.Choreo.FollowsRetime` | Transient | Choreo section start equals the recompiled Passage start; an absolute control does not move [decl] `ChoreoTests.cpp:111-134` | Choreo content vs a Passage duration change |
| `InfinityStage.Editor.SavedMasterMatchesShow` | **Saved** | Every Scene/Sequence section matches the compiled segment within 0.05 s [decl] `EditorAutomationTests.cpp:1491-1580` | Passage, music and Choreo sections; keys; cut coverage; handoffs |
| `InfinityStage.Editor.SceneCutBindingsResolve` | Transient | Cut bindings resolve [decl] `CutBindingTests.cpp:26-60` | Anything about time |

**Gaps:**
- No test grows a Passage.
- No test checks that music sections move. They use `SetRange` alone, which was **measured to leave a reused Choreo sub-section in place** (`Builder.cpp:424-426`). Scene sub-sections using the same call do move [meas, indirect, row 7]. Why the two differ is UNCLEAR.
- No test checks that handoffs are rematched, or that cut coverage holds, after a retime.

## 4. Retime safety net

### (1) One test: `InfinityStage.Editor.RetimeEverythingFollows`

Build it in C++, in the editor tests module. It duplicates the saved Show and Master into the transient package and saves nothing. Do this for each Scene/Sequence cue (+Δ = 2 s) and, separately, for each Passage (+Δ on one `IntervalToNext`, and separately on `TailFrames`).

First, record before:
- compiled segments;
- every managed section's range per BlockGuid;
- every Passage channel's key times relative to its section;
- every pin;
- every Choreo and music section;
- the music envelope keys.

Then rebuild and assert:
1. Segments ending at or before the change are unchanged. Every later segment moves by exactly Δ.
2. Passage, Scene, Choreo and music sections (by GUID) equal the recompiled ranges.
3. For a rigid shift, Passage keys keep their relative frames. For the changed Passage, the test either **expects a re-fit** (if C++ re-fit is adopted, below) or **asserts a loud warning** naming every key and pin that now falls out of range or off its pass. It must never pass silently.
4. No pin was deleted without a logged `INFINITY_PIN_DROPPED`.
5. The music start offset is unchanged, and the envelope endpoints are at the new section ends.
6. Run `CheckSceneHandoffs` on the duplicated world view: Scenes adjacent to a changed Passage report stale. After `MatchSceneHandoffs`, nothing is stale and every Scene's cut track covers its playback range.
7. A negative control: an unmanaged absolute float track added to the Master does **not** move, which proves the test can fail.

### (2) The tool rule

> Store `{cue_guid | passage_guid, offset_frames_from_segment_start, tick_resolution}`; never a Master frame, a label or an ordinal. Re-resolve from `Compile()` at run time. A guard may compare *relative* state, never absolute playback ranges.

Violators and fixes are listed in §2:
- **extend KEY GATE**: delete it and replace it with a Δ check;
- **p04_bay3_trace**: retire it;
- **s3_wave_slides guard**: relax it;
- **walkin_transitions OPENING row**: re-key it;
- **p04 driver**: switch from labels to GUIDs;
- **p01_hallway_pingon**: move it into the Choreo.

All of these are **Python-only**.

### (3) C++ vs Python

| Item | Needs |
|---|---|
| The test above | C++ (tests module) |
| Rebuild auto-rematches handoffs for Scenes adjacent to a moved or resized Passage, or refuses with a list | C++ (`Builder` → `HandoffBuilder`) |
| Passage-resize key policy: keep relative and **warn**; or rescale keys by the pass-frame map; plus a pin-drop log instead of a silent delete | C++ (`Builder.cpp:286-309`). **Look decision for Gary**: rescale or hold? |
| Music `MoveSection` before `SetRange`, as Choreo does | C++, small |
| Tool fixes in §2 | Python |

## 5. Ranked by risk to directing tomorrow

1. **Passage interval/tail change desyncs the camera score from the wings and silently deletes pins** (rows 4–5). This is the most likely directing edit.
2. **The KEY GATE refuses the Opening and any Scene before a scored Passage.** The safe path is blocked, which invites unsafe manual edits (§2).
3. **Handoff views go stale after a Passage resize**, giving a visible pop at the Scene join. Nothing rematches automatically (row 12).
4. **Music sections may not move on a reused section.** The Choreo precedent was measured; music is untested (row 10, §3).
5. **Stale absolute records** (`walkin_transitions` OPENING row, `p04_bay3_trace`, the unapplied P01 ping-on writing absolute keys) misplace work when rerun (§2).

## UNCLEAR

- Why `SetRange` alone left a reused Choreo section in place while Scene sub-sections move. This decides whether risk 4 is real.
- Whether the saved P01 score is still 15 s early. That comes from memory and was not read from the asset.
- The full line-by-line sweep of `Saved/CodexFlatV3`, `Saved/CodexCueing` JSON and the remaining `Saved/CodexConductor` request files.
- PassageResize does not rebuild the Master (rows 16h). Whether its documented follow-up step rescales keys or rematches handoffs is UNCLEAR. I found no evidence that it does either.
- Which saved mechanisms use `ExplicitOriginFrame` (row 16a). Settling it needs an asset read.
- Whether the saved Opening's `DurationFrames`/sequence length is shorter than its curtain hold plus exit (row 16c).
