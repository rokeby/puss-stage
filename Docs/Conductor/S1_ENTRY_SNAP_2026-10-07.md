# S1 entry "camera view snap" (P01 → S1, HUD Cue 2 → 3): offline investigation, 7 Oct

Read-only. Nothing was run in Unreal or over MCP. No Content, tools, Show or level were edited, and nothing was
committed. The scratch files are in `Saved/CodexConductor/S1Snap/`: the sem dumps of `LS_DevScene_01`,
`LS_S1_HangarRise`, `LS_Animals_1_S1Hangar`, `LS_InfinityStage_V1Master` and `LS_Choreo_Passage_1`, made with
`S3Diag/s3_seq_sem.py` at 19:08, plus the probe and its harness.

Tiers: **[decl]** source, header or config read; **[meas]** a record, a log line or asset bytes read back;
**[inf]** a conclusion that could not be verified (the reason is given). No claim here is rendered or PIE-measured.

Gary (PIE, 7 Oct): "in the transition from P1 into S1, the turn of the rig is good but then as it comes into view,
we suddenly get a change in camera view snap"; later: "the boundary between cue 2 and 3".

## Verdict

| Suspect | Verdict | Tier |
|---|---|---|
| (c) Entry/handoff pose or lens mismatch | **Not supported.** P01's authored end and the Entry camera agree to 0.00 cm / 0.00°, 25 = 25 mm, same filmback. The glide starts on the same pose and lens. | meas (records + bytes) |
| (b) Cut conflict at S1 frame 0 | **Not supported.** Frame 0 is owned by the root Entry cut. No nested cut exists before frame 594. | meas (bytes) |
| (d) 2-tick boundary mismatch | **Not supported at this boundary.** P01 end = S1 start = 4624705 in the saved Master. Gary's play crossing claimed at the first tick inside S1. | meas (bytes + log) |
| (e) Look offset dropped at the hard cut | **Open, and the best remaining candidate.** Any dog-gaze or mouse look on the P01 rig is zeroed instantly at the cut by design. | decl (code); magnitude unmeasured |
| (f) Lens or PP settings the Match does not copy | **Open, minor.** The Match copies pose, filmback, lens, focus and aperture, but not the camera PostProcessSettings. | decl |
| (g) The Entry → Glide cut at S1 +4.76 s | **Poses identical in bytes.** Unkeyed aperture and PP are open. It is not at the cue boundary. | meas / inf |

None of the offline evidence shows a pose snap. The probe below separates (e), (f) and (g) in one play-through.
**Recommendation: no rematch and no glide change until the probe has run.**

## 1. Which boundary "Cue 2 → 3" is

- The HUD prints `Cue %d/%d` as `State.SegmentIndex + 1` / `Transport->Segments.Num()`
  (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageDirectorHud.cpp:209-210`). The index is
  `Transport->FindSegmentAtFrame(Frame)` (`:376-377`). So it is the transport segment index, not a GO number
  (GO numbers are 10/20/30… in the log) **[decl]**.
- The segment order is 0 Opening — Curtain, 1 Passage 1, 2 Scene 1 — External Sound, 3 Interaction 1, and so on
  **[meas `Saved/CodexSoftGoods/extend_scene_playback.json` segments; `passage_speed_probe_PSPEED-20261006-223036.json`]**.
- So **Cue 2 = Passage 1 and Cue 3 = Scene 1**. Directing's reading is confirmed.
- The live transport claims `requested=2` (Scene 1) at 4624705 **[meas `Saved/Logs/PussStage.log`]**.

## 2. What CS v2 targets, and what the Entry camera is

- **The Entry camera** is `Scene 1 — External Sound — Entry Handoff Camera`. It is bound in `LS_DevScene_01` as
  binding `48b46452…` (= `5264B448…` in GuidLibrary order) **[meas bytes; `klara_reveal_record_S1.json` cuts_after]**.
- **How the Match builds it.** The builder takes the Entry from the P01 rig's
  `GetCameraViewAtMasterFrame(IncomingSegment.EndFrame)`
  (`InfinityStageEditor/Private/InfinityStageSceneHandoffBuilder.cpp:220-226`). It copies it with `CopyCameraView`
  (`:112-135`): actor transform, Filmback, LensSettings, manual focus, focal length and aperture. It does **not**
  copy PostProcessSettings or the aperture-ratio flags **[decl]**.
- **The authored pose the rig evaluates** (`InfinityStageCameraRig.cpp:869-1010`) is route spline at distance,
  plus CameraOffset and the LocalOffset channels, rotated by look-ahead and LocalRotation. It includes the settle
  (`GetCrossingSettleFrames()`, `:912`). It **excludes** the gait bob and the dog/mouse look, which are applied
  live on top **[decl]**.
- **What CS v2 does.** It eases route **speed** to 0 at the same end distance and frame, and fades the bob and its
  roll to 0 (`Public/InfinityStageCameraRig.h:270-283`, `CrossingSettleSeconds = 1.0`;
  `Public/MovieSceneInfinityPassageTrack.h:99-115`). The arrival pose is unchanged, so the Entry stays valid
  **[decl]**.
- **P01 authored end pose** is (28784.0135, 0, 150), pitch 0, yaw 0, 25 mm. The last 12 s are straight (yaw 0,
  pitch 0, z 150), and the settle is visible in the samples: −0.2 s → 28782.20, −0.1 s → 28783.77, 0 → 28784.01
  **[meas `Saved/CodexConductor/passage_end_drape_S1_dry.json` inputs.passage_camera, written 02:44]**.
- **Entry camera pose and lens.** Location (28784.0135, 0, 150), pitch 0, yaw 0, focal 25 mm, focus 600, filmback
  23.76 × 13.365 **[meas same file, inputs.entry_camera; and `klara_reveal_record_S1.json` plan.poses.entry at
  10:40]**.
- **Staleness log.** The handoff watch has logged no live `INFINITY_HANDOFF_WATCH_STALE` for Scene 1; only the
  automation-test show appears **[meas: grep of `Saved/Logs/*.log`]**.

## 3. What S1 actually opens on

- **Root cut track** in `LS_DevScene_01` (sha 47586ab4a63e, saved 10:40 by KLARAREVEAL-20261007-104054):
  - Entry [0, 119);
  - Glide `S1 Reveal Glide Camera` [119, 6151);
  - Exit [6151, 6176).

  The numbers are Scene frames at 25 fps. No section has easing **[meas bytes]**.
- **Nested content:**
  - `Hangar Fold` sub [0, 775) → `LS_S1_HangarRise`, which has **no** camera-cut track **[meas bytes]**;
  - the cinematic shot [594, 5769) → `LS_Animals_1_S1Hangar`, which has her cut track, offset 86400 ticks
    **[meas bytes]**.
- **So frame 0 is the root Entry cut, and nothing nested can outrank it before frame 594.**
- **The glide's first key, at frame 119 (tick 114240):**

  | Property | Value |
  |---|---|
  | Location | (28784.0137, 0, 150) |
  | Rotation | 0, 0, 0 |
  | CurrentFocalLength | 25.0 |
  | ManualFocusDistance | 600 |

  That is identical to the Entry **[meas bytes]**. It matches `klara_reveal.py:2177`: start_pose = the Entry pose,
  with the focal converted for an equal HFOV, and the same filmback here **[decl]**.
- **Unkeyed on the glide camera:**
  - **Aperture:** a spawned default CineCamera (`klara_reveal.py:3422-3430` sets only filmback and focus method)
    **[decl]**. Its value against the Entry's copied rig aperture is **[inf: not in any record]**.
  - **PostProcessSettings:** default **[inf]**.
- **The Master** (`LS_InfinityStage_V1Master`, saved 09:28): P01 section [2312640, 4624705) and Scene 1 sub
  [4624705, 10553665) = 247.04 s, which matches the reveal's planned_end 6176 **[meas bytes]**.
- **Choreo.** `LS_Choreo_Passage_1` has 0 tracks, so no score turns the P01 camera **[meas bytes]**.

## 4. Comparison

| Quantity | P01 authored end | Entry (frame 0) | Glide (frame 119) | Delta |
|---|---|---|---|---|
| Location | 28784.0135, 0, 150 | 28784.0135, 0, 150 | 28784.0137, 0, 150 | 0.00 cm |
| Rotation (pitch, yaw, roll) | 0, 0, 0 | 0, 0, 0 | 0, 0, 0 | 0.00° |
| Focal / filmback | 25 / 23.76 × 13.365 | 25 / same | 25 / same (her filmback = this one) | 0 |
| Focus | not in the record | 600 | 600 | — |
| Aperture, PP | rig instance | copied aperture; PP not copied | default; PP default | **unknown** |

The authored pose and lens are continuous across both cuts **[meas]**. What the operator **sees** on P01 is the
authored pose plus three live layers. These are the only places a step can come from:

1. **Gait bob.** CS v2 fades it to weight 0 at the end. On the last rendered P01 tick, about 1 frame before the
   end, the smoothstep weight is about 0.005, so the residue is under 0.1 cm **[decl formula; inf magnitude]**.
2. **Dog/mouse look on the rig's camera component.** `bResetLookAtCut = true`
   (`Plugins/Go1Input/Source/Go1Input/Public/Go1RemoteReceiverComponent.h:199-209`, Gary 30 Sep "Reset at every
   cut"). On a view-target change with no blend in flight, `SettleLookAtOnce()` drops the look instantly
   (`Private/Go1RemoteReceiverComponent.cpp:377-400`). The P01 → Entry handover blend is 0.000 s
   **[meas log `INFINITY_HANDOVER requested=2 … blend=0.000s`]**. In any case the Entry camera never carried the
   P01 rig's component look.
   - So **the snap equals the look offset at the crossing**. If Gary or the dog had looked even a few degrees away,
     the view jumps back to straight ahead **[decl mechanism; magnitude unmeasured]**.
   - This is the best fit for "the turn … is good, then … a snap" **[inf]**: the authored P01 end has no turn at
     all, so any camera turn he saw was live look.
3. **The hangar swing.** "The turn of the rig" may instead mean the hangar's root pitch, −90° → 0° over S1
   −5.87 s … +4.13 s (`LS_S1_HangarRise` S1 Hangar Root Rotation[1] keys −140800 → 99200 ticks) **[meas bytes]**.
   - Before the Scene, the Arrival evaluates the **same** channel through the mapped motion time
     (`InfinityStageArrival.cpp:1126-1157, 1244-1254`) **[decl]**. Inside the Scene, Sequencer does. So the swing
     should be continuous **[inf: same curve, two evaluators; not observed]**.
   - The probe logs the hangar root rotation per tick to settle this.

**(d) boundary.**
- The saved Master puts P01 end and S1 start on the same tick, 4624705 **[meas bytes]**. The 6 Oct 2-tick mismatch
  was P06/S6 (`Docs/Conductor/GARY_PIE_NOTES_2026-10-06_overnight.md:18-19`) **[meas there]**.
- In Gary's 22:53–22:55 run, play crossed with no ADVANCE between P01's start and Scene 1. The Scene 1 claim landed
  at 4624743, 38 ticks into S1, which is the first tick inside **[meas `PussStage.log:10615-10619`]**.
- No stall is evidenced; SeamDiag was off in that run (no `INFINITY_SEAM_DIAG` lines) **[meas]**.

**(b) cut conflicts.** None at frame 0 (§3). Inside [594, 5769) her nested cuts outrank the root Glide; that is by
design and is not this boundary **[meas bytes + memory: nested outranks root]**.

## 5. Fix paths

The tool and arguments for each verdict the probe can return:

- **`CROSSING_POSE_STEP` / `CROSSING_FOV_STEP` with the look at 0** (a true Entry mismatch; not expected from the
  records).
  - **Re-run the Match for S1 only:** `Saved/CodexCameraPilot/match_scene1_handoff.py`, which calls
    `InfinityStageCameraPilotLibrary.match_named_scene_handoffs(show, [S1 cue GUID 91030A272145EBEF25D33BA016458739], 1)`
    (`Public/InfinityStageCameraPilotLibrary.h:116-120`).
  - **Caution:** the Match also re-takes S1's **Exit**. A retained Exit copies the last interior camera, which is
    now the glide, and the reveal's glide-out targets the Exit pose. So after a Match, klara_reveal's keys would
    have to be re-derived: REVERT → DRY → APPLY, `klara_reveal_args.json` scene 1. That is a backed-up,
    conductor-approvable write sequence, not a one-liner.
  - **Alternative that leaves the Match alone:** start the glide from the rendered P01 end. klara_reveal reads
    `entry` as its start (`klara_reveal.py:2177`); an override would need a new arg. Not written.
- **`LOOK_OFFSET_DROPPED_AT_CUT`.** This is behaviour Gary chose for cuts inside Scenes. At a matched P→S crossing
  it shows as a snap. The options are a look decision for Gary, routed via the conductor:
  - (i) ease the look to 0 over the settle window, the last `CrossingSettleSeconds` of a Passage, on the C++ side
    in the Go1 receiver, by Look & camera;
  - (ii) carry the look into the Entry camera, then ease it;
  - (iii) accept it.
- **`LENS_OR_PP_DIFFERS`.** Copy PostProcessSettings in `CopyCameraView` (a C++ patch), or set the glide camera's
  aperture and PP from the Entry in klara_reveal.
- **`GLIDE_CUT_STEP`** (frame 119). Key the glide camera's aperture from the Entry's, or remove the cut by keying
  the glide onto the Entry camera. That is a klara_reveal change.
- **`STALL`.** Hand the SeamDiag lines in the same run to the C++ pass.

## 6. The probe (read-only, PIE-only)

**Files:**
- `Saved/CodexConductor/S1Snap/s1_entry_snap_probe.py`
- `…/s1_entry_snap_probe_args.json`
- `…/s1_entry_snap_probe_request.json`
- harness `…/test_s1_entry_snap_probe.py`: 6/6 −/+ controls (clean, look drop, pose jump, FOV jump, wrong owner,
  stall). The analyser is proven; the live calls are untested.

**What it does:**
- It never saves, never writes the editor world, never starts or ends PIE, and never quits the editor.
- **arm** pauses the Show Root's player and calls `transport.scrub_to_master_frame(P01 end − 2 s)`. It reads the
  frame back, refuses on a mismatch, then calls `transport.play_forward_through_boundaries()`. This is the route of
  the 30 Sep precedent `Saved/CodexCameraPilot/scene1_tail_view_pie.py:103-104`.
- It does not use `get_sequence_player` (absent in UE 5.8 Python) or EditorAssetLibrary (None in PIE).
- A Slate post-tick callback logs every tick from P01 end − 2 s to S1 + 5 s into `probe_<run>.jsonl`. Each row
  carries:
  - the Master frame and seconds, the segment by the compiled table, `held_end`, playing, and `last_handover`;
  - `player_frame`, world time and dt;
  - the rendered POV from the camera manager (location, rotation, FOV);
  - the view-target label and class;
  - its CineCamera component: world and relative pose, focal, aperture, sensor, focus, FOV, PP weight, and
    `cam_vs_actor_deg`, which is the live look;
  - the rig's settle weight, bob, walk weight and speed;
  - the Entry and Glide camera rows;
  - the S1 Hangar Root rotation;
  - the expected cut owner from the byte-read table;
  - the per-tick step in cm, degrees and FOV.
- It sets `InfinityStage.SeamDiag 1` (window = max(pre, post)) for the same run and restores it afterwards.
- It holds no UObject wrapper between ticks: it stores PIE paths and re-resolves them **[inf: the crash class is
  from memory]**.
- When the window closes it writes `probe_<run>_report.json` and logs
  `S1SNAP_VERDICT|run=…|flags=…|delta_cm|delta_deg|delta_fov|look_deg|vt=A->B`. `S1SNAP_OK` is logged only when
  rows exist on both sides of the boundary.
- **watch** logs the same window without touching the transport, for a natural play from the Opening.
- **stop** unregisters early.

**Run** (PIE already running; set a fresh run id first, because the probe refuses a reused one):

```bash
cd /e/PussStage
python - <<'EOF'
import json,datetime;p='Saved/CodexConductor/S1Snap/s1_entry_snap_probe_args.json'
a=json.load(open(p));a['run']='S1SNAP-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S');a['phase']='arm'
json.dump(a,open(p,'w'),indent=1);print(a['run'])
EOF
bash Saved/CodexConductor/conductor_helpers/mcprun.sh S1Snap/s1_entry_snap_probe_request.json "S1SNAP_OK|S1SNAP_FAILED" "S1SNAP_|INFINITY_SEAM_DIAG" 60
# offline re-analysis: python Saved/CodexConductor/S1Snap/s1_entry_snap_probe.py --analyze Saved/CodexConductor/S1Snap/probe_<run>.jsonl
```

**How to read the result:**
- **`look_deg` > 0.2 on the last P01 row plus `CROSSING_TURN_STEP`:** (e). The look was dropped at the cut.
- **A pose or FOV step with the look at 0:** (c).
- **`LENS_OR_PP_DIFFERS`:** (f).
- **`GLIDE_CUT_STEP`:** (g).
- **`STALL`:** (d).
- **`NO_STEP_FOUND`:** the step is not in the camera. Next suspects are the hangar root row (the swing) and
  exposure. The arm-phase scrub also differs from Gary's natural play, so re-run with **watch** and play from the
  Opening.
- For (e) to show, someone must look away with the mouse or dog during P01's last seconds. Run it twice: hands off
  (the control) and looking about 10° left (the test).

## What was searched and found nothing

- Live handoff-stale lines for Scene 1 (all logs).
- `INFINITY_SEAM_DIAG` in today's PIE logs (only the test suites).
- Camera-cut tracks in `LS_S1_HangarRise`.
- Tracks in `LS_Choreo_Passage_1`.
- Any record of the P01 rig camera's aperture or PP settings, or the glide camera's.
- A Python-visible way to read Sequencer's active cut offline. The probe infers the owner from the view target.
