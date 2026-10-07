# S4 entry investigation: pendulum, curtain, pre-rolled reveal (7 Oct 2026, read-only)

The investigation was read-only. Nothing ran in Unreal or over MCP, and no project file was edited. The only file
written is this one. The scratch readers live in the session scratchpad. They reuse the byte reader in
`Saved/CodexConductor/KlaraIngest/test_klara_reveal_offline.py:785-1007`.

**Tiers.** Every claim carries one of these:
- **[decl]** stated in source, args or a doc we can read (file:line);
- **[bytes]** a `.uasset`/`.umap` parsed offline today (a measurement of the saved asset, not of runtime);
- **[meas]** a value read back from a live run's record;
- **[inf]** inferred, with the reason.

No DLL was inspected, so nothing here is binary-proven.

## Verdicts in one screen

| Question | Verdict |
|---|---|
| Camera "behind the P4–S4 curtain" | **Explained.** It is **her** first shot's dolly-back, not our glide. Her `CineCameraActor` rests at world (10241, 239604, 91) from her frame ~780 to 3002. That is 209 cm upstream of the P04 Backcloth plane (x 10450, ±39 cm thick, y ±500). [bytes + meas, curtain position inf] |
| Pendulum, hypothesis (iii): its own Blueprint tick | **Supported.** `BP_Pendulum` has an enabled `ReceiveTick` that calls `K2_SetRelativeRotation` on its root every frame. [bytes] |
| Pendulum, hypothesis (i): binding or space mismatch | **Partly supported, but not as stated.** Her LS places the anchor 5.1 m from where her level places it. So in our glide (no LS) it stands where her renders never show it. [bytes] |
| Pendulum, hypothesis (ii): resize moved the set but not the pivot | **Not supported.** The anchor's LS location was shifted exactly by the level transform. [bytes + meas] |
| Animation already in motion, then restart | **Authorable** with a second, stripped section of her copy before the cut. There are four traps (§D). |

## A. How the S1 entry works (S1 reveal v3)

- **Tool.** One tool covers every Scene: `Saved/CodexConductor/KlaraIngest/klara_reveal.py` (DRY / APPLY / REVERT, one
  Scene per run). Its runner and request are `klara_reveal_run.py` and `klara_reveal_request.json`. The harness is
  `test_klara_reveal_offline.py`. The design doc is `REVEAL_PLAN.md` §2–§10. [decl]
- **Parameterised by Scene: yes.** `klara_reveal_args.json` takes `scene` plus `scenes.{1,4}` blocks: sequence,
  level, copy, entry/exit cameras, glide-camera label, roof, placement override, `reveal_style`, `lit`. [decl
  `klara_reveal_args.json:58-88`]. S4 already runs through it (§B).
- **Live S1 state.** `KLARAREVEAL-20261007-104054`, roof kept, backup `Backups/PreKlaraReveal-S1-KLARAREVEAL-20261007-104054`
  [meas `klara_reveal_record_S1.json`].
- **What it authors.** Everything goes into the Scene sequence `LS_DevScene_0N`, the hookin copy and the map. It does
  not touch the Show cues, the Master or the rise asset [decl `REVEAL_PLAN.md:188-197`].
  - A level move of her streamed level: remove, then re-add with a new LevelTransform (`_move_level`,
    `klara_reveal.py:2449`) [decl].
  - A copy key shift (`_shift_copy`, `:2404`) [decl].
  - A new level CineCamera, `S<n> Reveal Glide Camera`, with per-frame world keys (`plan_glide` `:184`,
    `glide_seconds` `:312`) [decl].
  - A root cut split: Entry | Glide | Exit [decl `REVEAL_PLAN.md:140`].
  - `LightColor` black sections on the non-glow hangar lights (`_add_color_black` `:2284`). A LightColor fade on the
    ceiling glows, and the bulbs hidden [decl `REVEAL_PLAN.md:85-97, 310-313`].
  - The additive lattice cancel, so the rig does not lower (`_add_lattice_cancel` `:2346`) [decl].
  - Intensity sections on her lights (`_add_float` `:2234`) [decl].
  - Env ramps (sun, sky, fog, PPV BlendWeight) [decl].
  - Edits to the hookin windows: Hers Dark, Ours Off, Level Visibility (`_add_visibility` `:2389`) [decl].
  - The slot sub-section re-timed with a start offset (`slot_skip` `:833`) [decl].
- **How the one-by-one strike works.**
  - Lights are ordered `near_to_far` from her camera (`order_lights` `:408`).
  - `schedule` (`:419`) draws seeded gaps of 0.6–1.2 s and compresses them to fit the strike window.
  - `strike_keys` (`:459`) writes a 2–4 pulse constant-interpolation flicker in 0.32 s, settling at the light's value
    at her lit frame Lh. [decl]
  - S1 live: 14 strikes at frames 282…575, gaps ×0.99 compressed, cut 594, slot [594, 5769) starting 90 Scene frames
    into her LS (Lh = her frame −202) [meas `klara_reveal_record_S1.json` plan.timeline / strike_schedule / slot].
- **S1 timeline.** Rise with glows on [0,104), dark hold [104,119), glide in the dark [119,269], hold, glow fade
  [244,282], strikes, cut [meas same record].
  - **The same latent fault exists in S1** [inf, same mechanism]: her animals are static during the strikes, because
    her LS only evaluates inside the slot.

## B. How the S4 entry works now

- **Live state.** `KLARAREVEAL-20261007-095043` re-applied with the roof kept. Style `her_dark_pan` (auto: view-weighted
  lit fraction 0.028). Scene end 4890 = 195.6 s [meas `klara_reveal_record_S4.json` plan.reveal, plan.timeline].
- **Timeline** [meas same record, plan.timeline]:
  - land 104, dark [104,119), glide_in [119,307] (7.5 s, 1462 cm, peak 292 cm/s, ends at rest), hold [307,320);
  - crossfade [320,395]: **no strikes**. Lights lit at her frame 6 ramp smoothly: window 160, SpotLight3 160,
    SpotLight5 8, SpotLight6 0.64, SpotLight7 17.03. SpotLight, SpotLight2 and SpotLight4 stay 0;
  - cut 405 (+29 frames), slot [405, 4500) with start offset 4800 ticks = her frame 6 (her first cut [0,2) is dangling);
  - root cuts: Entry [0,119) | `Klara Reveal - S4 Reveal Glide Camera` [119,4865) | Exit [4865,4890).
- **Where the glide end pose comes from.** It is her `CineCameraActor` at her frame 6, after the level move: (12127.7,
  240000, 91), rot (0, 6, 5), 35 mm [meas plan.poses.her_lit, plan.lit.camera_after_move]. The glide start is the
  Entry Handoff camera at (10668.5, 240000, 180) [meas plan.poses.entry].
- **Placement.** Her first camera is placed at lead 1459 cm (`lead_max_cm` 1500, the conductor's S4 override).
  - The level moved by (−2204.3, −301.5, 0), so LT goes from (13639.97, 240008.5, 0) to (11435.67, 239706.98, 0)
    [meas plan.placement, level_transform_before/after].
  - Set dock-local x is 500…3183 [meas].
- **Glide end is in front of the curtain.** Glide x runs 10668 → 12128. The curtain is at x 10450 [inf: position
  below].
- **Why the camera "comes to rest behind the curtain".** It is her own first shot [bytes `LS_Children_S4Hangar.uasset`
  camera channels, via `_cam_pose`]:
  - Cut [3, 3002) on `CineCameraActor`: static near (12128, 240000…240059) to her frame ~360.
  - It then dollies back 1887 cm and −396 cm sideways, **resting at (10241, 239604, 91) from her frame ~780 to 3002**.
  - In Scene frames that is about 1050 to 2902 (≈ 42–116 s into S4) [inf: slot mapping 25/30 from her frame 6 at 405].
- **The curtain.** It is the "P04 Backcloth (baked)" GeometryCache in S4's Arrival backcloth slot [decl
  `passage_end_drape.py:31-33`].
  - Location (10450, 240000, 0), hang AABB x ±39, y ±500, z 20–1220 [meas `backcloth_lead_fit_dry.json` inputs, run
    6 Oct 01:52].
  - That it is still there is [inf]: the S4 resize says "the dock and the hinge do not move", hinge 11168.47 [decl
    `S4_HANGAR_REBUILD_PLAN.md:77-82`]. Gary's note says "it doesn't drop now; we walk straight through it" [decl
    `GARY_PIE_NOTES_2026-10-05.md:94-99`].
  - Her rest camera is at dock-local x −427, y −396. That is inside the cloth's y span, 170 cm upstream of its back
    face, looking +x through it.
- **Root cause in the tool.** `solve_placement` (`klara_reveal.py:237-273`) checks only her **set footprint** and her
  **first/lit camera** [decl]. `first_frame_sees` samples only her first frame [decl `REVEAL_PLAN.md:118-119`]. Nothing
  checks her **whole camera path** against x_min or the backcloth.

## C. The pendulum

**What it is** [bytes `Content/L_KK_children.umap`, `Content/L_KK_Children/Blueprints/BP_Pendulum.uasset`]:
- **The anchor.** Actor `BP_Pendulum_C_0`, label `Pendulum_Anchor`, in L_KK_children.
  - Its root component is `PivotRoot`, a SceneComponent with no AttachParent, at relative (865.15, 333.32, 456.89)
    and rotation yaw 130.
  - Instance override `SwingSpeed` 0.3. CDO `SwingAngle` 25, `ElapsedTime` 1.5.
- **The string and ball.** `Pendulum_String` (StaticMeshActor_1) and `Pendulum_ball` (StaticMeshActor_9) are attached
  to `BP_Pendulum_C_0.PivotRoot`, about 415 cm below it.
- **The Blueprint graph.** `ReceiveBeginPlay` and `ReceiveActorBeginOverlap` are disabled (EnabledState set).
  **`ReceiveTick` is enabled.**
  - Nodes: ElapsedTime += DeltaSeconds; three Multiply; MakeLiteralDouble (the only non-zero literal in the asset is
    `360.0`); DegSin; MakeRotator; `K2_SetRelativeRotation` on `PivotRoot`.
  - The only implicit-cast pin is `MakeRotator_Pitch`, and no `130` literal exists. So Yaw and Roll are most likely
    0 [inf: pin wiring is not decoded].
  - Read: pitch = 25·sin(360·0.3·t), a 3.3 s period. Because PivotRoot is the root, the tick **replaces the actor's
    world rotation and drops yaw 130** [inf from the above].
- **Her LS binding.** `LS_Children` and our copy both bind possessable `Pendulum_Anchor`, top level, with locator
  `/Game/L_KK_children.L_KK_children:PersistentLevel.BP_Pendulum_C_0`. It has one 3DTransform section over her whole
  range [0, 4920) [bytes].
  - Translation has **no keys, only defaults**: original (1375.15, 383.32, 456.89), copy (12810.82, 240090.30,
    456.89). The copy minus the original equals the current LT (11435.67, 239706.98) exactly.
  - Yaw default 130. **Pitch has 71 cubic keys, ±30°, from her frame 191 to 4683**, a period of about 7.5 s. So the
    LS holds the pendulum still at +30° for her first 6.4 s.
- **The shift was right by luck.** The hookin logged "no level actor: keys shifted as absolute" for display name
  `Pendulum` [meas `klara_hookin_seq_record.json:731-733`]. The reveal DRY lists `Pendulum` in
  `copy_bindings_unresolved` [meas `klara_reveal_dry_S4.json:308`]. Our label match missed it, but the shift was still
  correct, because the anchor is unattached [bytes].
  - Why the record's display name ("Pendulum") differs from the possessable name in bytes ("Pendulum_Anchor") is
    [inf, unknown].

**Hypotheses against the evidence:**
- **(iii) Own tick, independent of her LS: supported** [bytes].
  - It explains "swinging during the glide while the children are static": the tick runs in PIE, and her LS is not
    evaluating before the cut 405.
  - It explains the wrong angle: the swing is about the actor's Y axis with yaw forced to 0, so it is along the dock
    axis instead of at 130°. Amplitude is 25° against her 30°, and the period 3.3 s against her ~7.5 s [inf].
  - After the cut, the LS and the tick both write rotation every frame. Which one wins depends on tick order [inf:
    Sequencer vs actor tick order not verified]. Gary's "keeps swinging at the wrong angle" suggests the tick wins.
- **(i) Space or binding: partly supported.**
  - Before the cut, the anchor is at the level placement: world ≈ (12300.8, 240040.3, 456.9) [inf: level relative +
    LT].
  - Her LS places it at (12810.8, 240090.3, 456.9), **5.1 m away** [bytes]. So in the glide it stands where her renders
    never show it.
  - After the cut the LS default should move it. If Gary sees no jump, the binding may not resolve in the show world
    [inf, unverified].
  - The relative-to-parent variant is refuted: no parent, no AttachParent [bytes].
- **(ii) The resize moved the set but not the pivot: not supported.** `hangar_resize_s4.py` writes hangar pieces only
  [decl `Saved/CodexStructure/hangar_resize_s4.py:10-25`]. The pendulum's LS location matches the current LT [bytes +
  meas].

**One read-only probe settles it** (after Gary's PIE, during a PIE run of S4; read only, no save, no transport
stop):
- Log `BP_Pendulum_C_0`'s `get_actor_location`, `get_actor_rotation` and `is_actor_tick_enabled()` on 3 consecutive
  frames at Scene-4 time 10 s (pre-cut) and at about 20 s (in the slot, past her frame 191). Stamp each line `run=<id>`.
- Compare against two predictions:
  - LS-only: location (12810.8, 240090.3, 456.9), yaw 130, pitch from the keys;
  - tick-only: level location (12300.8, 240040.3, 456.9), yaw 0, pitch 25·sin(108·t).
- Location tells whether her binding resolves; yaw tells who wins rotation.

## D. Animation in motion before her first cut, restart at the cut

- **Why the children are static now.** Her copy is one sub-section at [405, 4500). Its tracks evaluate only inside it
  [inf `REVEAL_PLAN.md:54-57`]. Before 405 the children stand in their level pose.
- **Proposed mechanism.** Add a **pre-roll sub-section** in `LS_DevScene_04`, on a new row, over [P0, C).
  - Its sequence is a **stripped duplicate** of the copy, for example `LS_Children_S4Preroll`.
  - Keep: the SkeletalAnimation + ControlRig tracks on `BP_MHC_Child*/Body`, `SK_Pigeon_01`, `Paper_Fall…`,
    `GC_Old_Book`'s GeometryCache track, and the transforms [bytes: track classes in `census_report.md:44-45`].
  - Its start offset puts it inside her idle (proposed: her frames from about 191, so the pendulum keys are swinging).
  - The main slot keeps starting at her frame 6 at C. That is the restart.
  - Copy keys are already absolute world positions for the current LT [bytes], so the duplicate needs no re-shift.
    It must be re-shifted with the copy if the level ever moves again [inf].
- **The four traps:**
  1. **Camera cuts.** Nested shot cuts outrank the Scene's root cuts [decl memory `puss-camera-handover-facts.md:229`].
     The duplicate's CameraCut track must be **removed**, not muted (muting the copy's would kill her cuts after C).
     Also remove its audio (double audio) and **every light Intensity/LightColor track**, or they fight our strikes
     on the same lights [inf].
  2. **Bindings must resolve in the show level** [decl memory `puss-camera-handover-facts.md:234`].
     - Its 5 `LightComponent0` bindings point at L_Animals (S1's hangar) [meas `REVEAL_PLAN.md:481-484`]. Strip them
       in the duplicate.
     - Run `SceneCutBindingsResolve` and `check_scene_cut_bindings` after.
  3. **The boundary at C.** Pre-roll ends at C (exclusive) and the main slot begins at C. With RESTORE_STATE, the
     restore and re-animate happen in the same evaluation [inf: not verified in 5.8]. PIE stills at C−1, C and C+1
     must show no one-frame T-pose or level pose.
     - GeometryCache: a capture right after a jump can be stale [decl memory
       `ue58-geometrycache-sequencer-traps.md`]. Re-pose before the stills.
  4. **Keys are absolute.** Passage keys are absolute and pins travel, keys don't [decl memory
     `puss-two-authorities.md`]. The Scene's sub-sections are moved by the rebuild, keys are not. A future relength or
     re-dock of S4 must move both sections together.
     - The reveal's REVERT and SLOT_DRIFT checks know only one slot [decl `REVEAL_PLAN.md:183-187, 456`]. The
       pre-roll needs its own record and its own revert.
- **The pendulum after the pre-roll.** Even with it, `BP_Pendulum`'s tick keeps writing rotation [bytes]. A fix needs
  one of these (Gary or Klara decide, because it is her asset):
  - (a) leave it;
  - (b) disable its tick in the show, through an actor property or a held level edit, never by saving her level
    [decl memory `klara-streamed-levels-traps.md`: never save her levels];
  - (c) edit `BP_Pendulum` to keep yaw.

## E. Authoring plan (DRY/APPLY, extending `klara_reveal.py` v5)

0. **Backup.** Take a `Backups/PreS4EntryV5-<ts>` snapshot of `LS_DevScene_04`, `LS_Children_S4Hangar`, the main map
   and `L_KK_children`. Then REVERT the current S4 reveal with its record. Its REVERT path is proven live for S1 [meas
   `.reverted-KLARAREVEAL-20261007-104026`].
1. **New reveal style `strike_preroll`** in `klara_reveal.py`, reusing `schedule`, `strike_keys`, `order_lights`,
   `plan_glide` and `plan_timeline`:
   - glide in the dark to a **new entry pose** (args `scenes.4.glide_end_pose`, Gary's framing), not her frame-6
     pose;
   - strikes over her lights in a chosen order to **chosen targets** (her plateau, or her value at a pinned frame);
   - `slot_skip` stays at her frame 6;
   - a hard cut at C from the glide camera to her shot. This is a camera cut, not a glide into her pose.
2. **Dark start with faint rig lights while the rig rises.** Keep v2's `lattice: cancel` or drop it, so the rig "rises
   into place"; Gary's word decides.
   - Keep the glows on [0, L), then fade over `glow_fade`, as S1 does [meas S1 timeline].
   - The S4 hangar hold must stay applied (`s4_hangar_hold.py`, S4HOLD-20261007-102817) [meas commit 73ed25f].
3. **New gates in DRY:**
   - **(i) `CAMERA_PATH_BEHIND_CURTAIN`.** Sample her **whole** slot camera path, and the glide, against the live
     backcloth AABB and x_min. Today her rest pose sits at dock-local x −427 against the curtain at −218 [bytes/meas].
     - Fix by an extra placement lead of at least ≈ 350 cm: the set then spans 850…3533, inside the 6400 far limit
       [inf from the dry's wall extents], and the glide gets longer.
     - Or by a Visibility hide of `P04 Backcloth (baked)` from C, inside the Arrival's after-cut Sequencer window
       [inf].
   - **(ii)** The glide entry pose must lie in front of the cloth's front face (x > 10489 + near-clip margin) and
     inside the hangar box.
   - **(iii)** Extend `first_frame_sees` to the glide end pose.
4. **New script `klara_preroll_s4.py`** (DRY/APPLY/REVERT, own record):
   - duplicate the copy into `LS_Children_S4Preroll`;
   - strip the CameraCut, audio, light and L_Animals bindings, then read back that none remain;
   - add the sub-section [P0, C) on a new row with the chosen start offset;
   - read back with `get_parent_sequence_frame`, as the reveal's `SLOT_MAPPING_READBACK` does (`klara_reveal.py:2736`).
5. **After both:** `rebuild_managed_master`, then SavedMasterMatchesShow (the real test, not the swapkit stage [decl
   memory `tk-saved-master-stage-is-fake.md`]), then SceneCutBindingsResolve, then live cut bindings.
   - PIE stills at L, mid-glide, each strike, C−1, C, C+1, and her rest pose (≈ 42 s), checking for the curtain.
   - Save only `LS_DevScene_04`, the duplicate and the main map, never Klara's levels.
6. **Pendulum.** Run the §C probe first. Then apply Gary's chosen remedy (§D last bullet) as a separate, reversible
   step.

**Open look decisions for Gary** (none of these numbers is his yet):
1. **Glide entry framing.** Where the dark glide ends (a wide on the children? the pigeon?) and how long it takes.
2. **Strike order and timing.** near→far as in S1, or by subject (children, pigeon, window). Gap range 0.6–1.2 s, and
   whether to flicker.
3. **Strike targets against her dark opening.** At her frame 6, SpotLight, SpotLight2 and SpotLight4, the lights on
   the children, are **0**; they reach 160 cd only at 5.5–13.1 s [bytes, `REVEAL_PLAN.md:494-499`]. Striking them
   before the cut means a lighting drop at the cut. Options:
   - (a) accept it;
   - (b) strike only what is lit at her frame 6;
   - (c) hold her opening lights at plateau in the copy, which edits her look.
4. **Pre-roll range** (which of her frames play before the cut). Note the pendulum is held at +30° until her frame
   191 [bytes].
5. **The curtain:** extra lead, which moves her set about 3.5 m deeper and lengthens the glide, or hide the P04
   backcloth from C.
6. **The pendulum tick:** leave it, disable it in the show, or ask Klara to edit `BP_Pendulum`.
7. **The rig:** keep it up (`lattice: cancel`, as in S1 v2) or let it visibly rise or lower into place.

## Searched and found nothing in

- **"pendulum" in docs and tools.** No hit in `Docs/` (apart from the conductor 5 log), `Tools/`, `Scripts/`,
  `Saved/CodexStructure` or `Saved/CodexCueing`. No tool has ever addressed the pendulum.
- **Pendulum in `census_report.md`.** Its only pendulum mention is the bound-actor list (`:45`).
- **Camera-path checks in `klara_reveal.py`.** No check of her camera path beyond the first/lit frame (grep of
  `near_ok|far_ok|first_frame_sees`).
- **A P04→S4 `passage_end_drape` record.** None exists (`passage_end_drape_record_S{1,2,3,5}.json` only); S4 was
  refused BACKCLOTH_SLOT_TAKEN [decl `passage_end_drape.py:31-33`].
- **Media/video playback code.** None in the plugin [decl `REVEAL_PLAN.md:145-147`].
- **The BP's MakeRotator pin wiring.** Not decoded (EdGraph pin serialisation not parsed); hence the [inf] on yaw 0.
