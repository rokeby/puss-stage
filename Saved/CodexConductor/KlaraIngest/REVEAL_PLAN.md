# Klara reveal: intro | cinematic slot | outro (7 Oct, offline)

Offline only. Nothing was run in Unreal or over MCP, nothing was built or committed.

| File | Role |
|---|---|
| `klara_reveal.py` | The tool (DRY / APPLY / REVERT, one Scene per run) |
| `klara_reveal_run.py`, `klara_reveal_request.json` | Runner and MCP request |
| `klara_reveal_args.json` | Arguments: mode DRY, scene 1 |
| `test_klara_reveal_offline.py` | Harness: 71/71 pass (v4, §10; S4 facts re-read from bytes); v4: 12/12 seeded mutations caught in-harness; v2: 22/22; v3: 18/18 |

Proof tiers per claim: **[decl]** source or header read (file:line), **[prec]** in-repo precedent call,
**[meas]** a record or bytes read, **[inf]** inferred (the reason is given). Every [inf] API is probed in the DRY's
`api_table`.

## 1. What Gary asked for (7 Oct, via the conductor)

- Leave her elements unscaled. Move and resize the **hangar** around her diorama, and put the diorama right in front of
  the camera as it leaves the passage.
- The floor stays in total darkness. Ceiling-rig lights keep their glow.
- Her lights strike one at a time, as a crossfade. The lighting must never switch hard.
- **Plan A is video.** Her cinematic becomes a Sequencer **Media track** in each Scene sequence. Until the renders
  exist, her in-engine cinematic (the hookin's re-keyed copy) fills the same slot one-for-one.
- The intro ends on her **first** cinematic frame (pose and lens). The outro starts on her **last** one.
- S1 first, then S4. S2 is untouched.

## 2. The Scene timeline

`L` = land, `C` = cut, `E` = C + her length. For S1 these are L = 104, C = 376, E = 5641
[meas `klara_hookin_seq_record.json`].

```
[0, end)     non-ceiling hangar lights BLACK (LightColor = 0); ceiling glows untouched or radius-clamped
[L, D0)      dark hold, 0.6 s; her level is already visible from L (the hookin's Level Visibility track), her lights at 0
[D0, C)      her local lights strike one at a time
[G0, C)      glide: Entry Handoff pose -> her first camera pose and lens (6 s)
             her sun, sky light and fog ramp 0 -> her value; her PPV BlendWeight ramps 0 -> her value
             roof hidden from G0; OUR celestial hidden from G0; the hookin's "Hers Dark" now ends at G0
[C, E)       SLOT: her nested copy now, a Media track section later (same range)
[E, X)       outro: the camera is on her last pose; her lights blink out in reverse order; her env fades to 0;
             the roof comes back once her env is out; then a glide to the Exit Handoff pose
[X, end)     the existing Exit Handoff cut (25 frames)
```

- **No hard switch.** At C the strike and ramp sections end and her nested tracks begin. The intro settles to her
  values at her first frame, or to the level value where her LS does not key that property. The outro starts from her
  values at her last frame. So the cut is value-continuous both ways [inf: RESTORE_STATE semantics].
- **Pre-cut overlap is impossible.** Her nested tracks evaluate only inside [C, E) [inf: standard sub-section
  evaluation], so keying her lights' Intensity in our Scene before C cannot blend with her own keys. Her LS does key
  `LightColor` on RectLights and SpotLights [meas `names_S1.txt`; 3 RectLights and 11 SpotLights are bound,
  `census_report.md:19`].
- **The scene grows.** The outro lengthens the Scene to about E + 7 s. DRY prints the `extend_scene_playback` mode.
  APPLY refuses (`RELENGTH_FIRST`) until the playback end equals the planned end.

## 3. Mechanisms, with evidence

**Placement.**
- Her level and its re-keyed copy move together by one translation delta (dz = 0, so her floor stays on ours). The
  delta puts her first camera `lead_cm` (350, proposed) ahead of the Entry camera on the dock axis.
- The lead grows if her set would sit behind x_min = 500, the hinge. Lateral offset is 0 unless her set would cross a
  side wall.
- The copy shift follows the hookin's rules [prec `klara_hookin.py:1087-1139`]. It is exact for cubic keys [inf].
- The level move is remove + re-add [decl `EditorLevelUtils.h:276-277`].
  - `FLevelUtils::SetEditorTransform` exists but is C++-only [decl `LevelUtils.h:181`].
  - Setting `level_transform` alone probably does not move actors that are already loaded [inf].
- The box is read **live** from the wall bounds, not from the 30 Sep record.

**Hangar resize.**
- DRY emits snug `HANGAR_PARAMS` (depth, half_w, lattice_z, height) for Structure's `hangar_build.py`. Depth steps by
  2000, matching the floor tiles [decl `hangar_build.py:96-98`].
- It also reports K. K = sqrt(max(depth, 2·height)/6000) [decl `:178`], so a shallower box at 30 m height keeps the
  rise timing.
- **This tool does not rebuild.** A rebuild re-runs about 117 spawns, the Arrival, the exit doors and the retime
  [prec `s1_redock.py` docstring]. That is Structure's call.
- The S1 set already fits the live box with the camera at the front [meas footprint 18.6 × 10.2 m vs a 58 × 18 m
  interior].

**Hangar lights.**
- All hangar lights except the `S<n> Lattice Glow` lights get a `LightColor` = black section over [0, end).
- Why not muting or Intensity keys:
  - The rise sequence and the Arrival own Intensity [decl `InfinityStageArrival.cpp:282-289, 409-442`].
  - The Arrival's pre-Scene drive ignores section mute [decl `:123-160, 1221-1240`].
  - The level saves evaluated state (memory), so a muted section could hold a lit value.
  - Nothing keys LightColor [decl `hangar_build.py:488-496`, keys Intensity only], so black multiplies every
    contribution to zero, volumetrics included [inf].
- Glows:
  - They sit at lattice_z + 11 cm (1211) with radius 800, so they cannot reach the floor [decl `hangar_build.py:121,
    138-140, 415, 501`].
  - DRY measures their reach to her set. A glow that reaches it gets a constant `AttenuationRadius` clamp; that
    property is not keyed elsewhere [inf].
  - The lattice beams and rails have `shadows=False` [decl `:125, 129`], so they do not shadow her sun.

**Her lights.**
- Strike: Intensity uses constant-interpolation keys. Each light flickers ON/OFF at frame granularity:
  - 2–4 pulses, capped to fit in 0.32 s. At 25 fps, 0.3 s holds only 3 pulses.
  - One seeded generator per light, one draw per statement.
- Order is `near_to_far` from her first camera (proposed).
- Gaps are drawn from 0.6–1.2 s and compressed to fit [D0, C). DRY warns `GAPS_COMPRESSED` and refuses below 0.25 s.
  With 14 lights in about 10 s the gaps are compressed [inf from the S1 counts].

**Environment crossfade.**
- Her DirectionalLight and SkyLight `Intensity`, and ExponentialHeightFog `FogDensity`, ramp 0 → her value over
  [G0, C − 0.4 s].
- SkyAtmosphere and VolumetricCloud have no intensity. They become visible at G0 while her sun is at 0, so they read
  dark [inf].
- Our celestial stays hidden from G0 to the end. We do not fade it, because the CelestialRig writes its intensity and
  colour in Passages [decl `CelestialRig.cpp:362-528`]; under the roof it contributes nothing visible [inf].

**Roof (the coordinator's question).** Option `hide_roof` is the default and my recommendation.
- The roof would occlude her sun and sky (Lumen) [inf].
- The lattice stays, because it is Gary's ceiling rig and casts no shadows.
- Walls are hidden only with `hide_roof_and_seen_walls`, and only those that a ray grid from her first camera sees
  (`first_frame_sees`, an approximation [inf]).
- **Risk:** once the roof is gone, her sun also lights our hangar floor outside her own Floor. PIE stills must check
  this.

**PPV.**
- Our `S<n> Hangar Pinned Exposure` pins EV100 0.5 [decl `hangar_build.py:451-454`]. The rise keys its BlendWeight
  0→1 [decl `:516-523`].
- Her PPV's BlendWeight is ramped with the crossfade.
- DRY warns `HER_PPV_NO_EXPOSURE_OVERRIDE`, `HER_PPV_BOUNDED` and `PPV_PRIORITY`. Who wins the exposure is a Look
  decision; nothing is forced.
- The hookin's "Hers Dark: PostProcessVolume" Visibility track probably does nothing to a PPV [inf].

**Camera.**
- A new level CineCamera `S<n> Reveal Glide Camera` is created, unattached, with world keys [prec
  `curtain_sleight.py:1837-1852`].
- It has her filmback. Its start focal matches the Entry camera's horizontal FOV.
- Keys are baked per frame (LINEAR between frames): a cubic Hermite with start velocity 0 (the passage ends at rest)
  and end velocity equal to her camera's first-frame velocity, so there is no speed pop. Shortest-arc rotation.
- Lens (focal length, manual focus) eases to hers.
- The last-frame pose is sampled at `playback_end − 1` (memory: the end frame is the rest pose).
- We do not key the Entry Handoff camera: `MatchNamedSceneHandoffs` regenerates it.
- The root cut track becomes Entry [0, G0) | Glide [G0, X) | Exit [X, end). In the nested slot, her cuts outrank ours
  (memory).

## 4. Video slot (Gary: Sequencer Media track)

- **No playback path exists in the project.**
  - Grep of `Plugins/InfinityStage/Source` for MediaPlayer, MediaTexture, FileMediaSource, BinkMedia and ImgMedia:
    0 hits.
  - No MediaTexture asset exists [meas `SCENE_EXIT_BLOCK_PLAN_2026-10-04.md:37-38`].
- **The plugins are effective** [meas `pussstage_effective_plugins.json`]: MediaCompositing (the Sequencer Media
  track), MediaPlate, ImgMedia, ElectraPlayer and WmfMedia.
- **Proposed route.** Per Scene, one MediaTrack section over exactly [C, E), playing a FileMediaSource or
  ImgMediaSource into a MediaTexture. It is shown full-frame on the glide camera, through an after-tonemap
  post-process material or a plate at the camera.
- **Mute the nested copy then.** When the video is used, mute the nested copy (keep it as the fallback).
- **The sync is assumed, not checked.** The Media track seeks with the Master when scrubbing, so the transport keeps
  frame sync [inf; not verified in 5.8].
- **Needed from Gary:**
  - Renders of exactly her LS playback range. S1 is [-310, 6008) at 30 fps, 210.6 s [meas hookin record].
  - Frame rate: 25 (the Master's) is preferred, or 30.
  - Resolution equal to the show output.
  - Same tonemapper and exposure as the engine intro, or the first frame will not match.
  - An image sequence (ImgMedia) for frame-exact scrubbing, or MP4 if only linear play matters.
  - **Audio as separate WAVs**, kept on Sequencer audio tracks; her audio sections are already mapped by the hookin.
  - First- and last-frame stills for the seam check.

## 5. Steps (per Scene, S1 then S4)

0. `Backups/` snapshot. **DRY.** Read `klara_reveal_dry_S1.json`: api_table, placement delta and lead, live box,
   hangar proposal, timeline, glide report (peak speed, end-speed match, overshoot), her light list and strike times,
   hangar light actions, env and PPV rows, `first_frame_sees`, unresolved copy bindings, refusals.
1. **Relength** with `extend_scene_playback.py`, using the printed mode.
2. **APPLY.** It runs in this order:
   - backup and an exclusive record;
   - level move and copy shift (read back);
   - glide camera;
   - strike, ramp and blackout sections;
   - roof hide;
   - hookin windows (Hers Dark, Ours Off, Level Visibility);
   - cut split;
   - census;
   - save the map, `LS_DevScene_0N` and the copy.
3. `rebuild_managed_master`, then `SavedMasterMatchesShow`, then `SceneCutBindingsResolve` (that test uses its own
   world, `InfinityStageCutBindingTests.cpp:31`), then a live `check_scene_cut_bindings`, then PIE stills at L, G0,
   C−1, C, E−1, E and X.
4. **REVERT order:** klara_reveal REVERT → extend back → only then klara_hookin REVERT_SEQ (whose drift check would
   otherwise refuse).

## 6. Conflicts and other streams' files

- **This tool writes:**
  - the map, by moving her streamed level and adding the glide camera;
  - `LS_DevScene_0N`;
  - the hookin copy.
- **It edits the hookin's own sections:** Hers Dark, Ours Off, and the Level Visibility end.
- **It reads Structure's actors but never writes them:** `S<n> Hangar *`, `S<n> Lattice Glow *`, `S<n> Arrival`,
  `S<n> Hangar Pinned Exposure`.
- **It does not touch:** `LS_S<n>_HangarRise`, `hangar_build.py`, the Arrival, the Show or the Master.
- **The hangar resize, if wanted,** is Structure's rebuild from the DRY's `hangar_proposal.params`.
- **`s1_redock.py` is not applied yet** [meas: no record]. If it runs later, the glide camera must join its
  `extra_move_labels`. Its STATE_FILES list should also include `klara_reveal_record_S1.json`.
- **S4.** `LS_Children` binds 5 SpotLights in L_Animals [meas hookin plan §3]. Moving L_Animals for S1 moves them. DRY
  lists every copy binding that does not resolve (`copy_bindings_unresolved`); the rest are listed, not fixed.

## 7. Revision after the first live S1 DRY (KLARAREVEAL-20261006-233359)

**The conductor's live fixes are kept:**
- the far wall is a union of the exit-door pieces;
- GUIDs are compared with `GuidLibrary.conv_guid_to_string`.

**Footprint.**
- **What went wrong.** The DRY reported an 80 × 80 m set [meas]. That came from the environment actors.
- **The fix.** `footprint_from_rows` keeps only actors that pass all three tests:
  - the class is not Sky, Atmosphere, Landscape, Fog, PostProcess, Light, Volume, Cloud, Camera, Reflection, Decal or
    Audio;
  - the actor owns a StaticMesh, ISM/HISM, SkeletalMesh, GeometryCache or Niagara component;
  - the actor is no larger than `footprint_max_size_cm` (4000) on any axis.
- **What is logged.** Every excluded actor is listed with the reason (`KLARAREVEAL_FOOTPRINT`).

**Fit.**
- **Footprint outside the live box:** refuses with `hangar_proposal.params` in the message.
- **Set reaching the lattice:** refuses unless `allow_lattice_overlap` is set, in which case it is a warning.
- **The hangar is never rebuilt here.**

**Lead.**
- Target is 600 cm and the maximum is 800 cm.
- If her camera stands inside her own set, the lead needed to keep her set past the hinge can exceed 800. DRY then
  warns `LEAD_ABOVE_RANGE`; it does not refuse.

**Glide.**
- `glide_seconds` finds the shortest glide, in 0.5 s steps, whose keys keep peak speed at or below
  `max_glide_speed_cm_s` (300). The outro is checked the same way.
- If the intro then needs more time than [L, C) gives, the **cut moves later**:
  - the new cut is the latest of: the old cut, the glide's end, and the strikes' end plus the settle time;
  - APPLY moves the nested slot section by the same shift, with a parent-frame read-back;
  - REVERT moves it back.
- **This is a hookin-owned edit.** The hookin's REVERT_SEQ drift check would refuse while it is applied, so the reveal
  must be reverted first.

**`evaluate()`.**
- The probe was False on the live build [meas]. `_ch_eval` therefore uses `eval_keys`: an exact key, or the
  constant value before the first or after the last key.
- A sample between keys returns None, and the DRY refuses `HER_CAMERA_EVAL`.
- The live DRY did not refuse, so both her first-frame samples were outside her key range, or on a key. That makes
  her first-camera velocity of 0 genuine, not a fallback artefact [inf].

**Projection for S1.** This is not a live run. It uses the live DRY facts plus the offline pivot footprint
[meas hookin args]:

| Quantity | Value |
|---|---|
| Lead | 949 cm (`LEAD_ABOVE_RANGE`: her camera sits about 4.5 m inside her set's near edge) |
| Delta | (−2072, −120, 0) |
| Set, dock-local x | 500..2356 |
| Set, dock-local y | −628..388 |
| Fits the live box | Yes |
| Glide in | 6.0 s, 9.5 m, peak 238 cm/s |
| Glide out | 8.0 s, 15.1 m, peak 284 cm/s |
| Cut | 376 → 431 (+2.2 s, driven by the 14 strikes) |
| Planned end | 6153 (246.12 s) |
| Hangar proposal | depth 4000, same K |
| First frame sees | the set only (45/45 rays) |

## 8. v2 after Gary's review of the applied S1 (7 Oct)

Gary's words: "while we're in the dark, we should already have moved into the final position for S1's wide intro
and then it lights up, and then we start it without any external lighting interference"; and "no need for the
ceiling rig now to lower".

**What lowers the rig.**
- `LS_S1_HangarRise` keys `S1 Hangar Lattice Fly` Location.Z from 2800 to 1200 [decl `hangar_build.py:121, 501`].
  After the retime this runs over 12.63–16.63 s of rise time [meas `hangar_retime_record.json`
  scenes.1.after_keys.lattice_fly_z].
- The rise plays inside `LS_DevScene_01` as the "Hangar Fold" sub-section [0, 775) [meas `klara_hookin_dry.json`].
- The Arrival's pre-Scene drive moves only the root rotation and float drives [decl
  `InfinityStageArrival.h:142-198`]. Its initial-pose drive acts at game start only [decl `:160-166`]. So the lowering
  happens inside the Scene, where Sequencer evaluates it.

**How v2 stops it, without touching Structure's rise asset.**
- In OUR Scene, an **additive** 3D-transform section on the Lattice Fly holds it up. Location.Z gets `cancel_keys`:
  1. value = 2800 − rise value;
  2. **negated** tangents;
  3. the same interpolation;
  4. key times mapped through the sub-section;
  5. every other channel 0.
- So rise + additive = 2800 at every instant. A Hermite segment is linear in its end values and tangents [inf]. The
  harness proves the sum is constant on a reference curve; un-negated tangents or a wrong time offset fail it.
- **To confirm live:** that additive blending applies across the sub-sequence boundary [inf]. DRY probes
  `set_blend_type` and the key tangent getters and setters; APPLY reads back keys, tangents and blend type. PIE stills
  at 12–17 s must show the rig not moving.
- **Fallback, `lattice: "hide"`.** Hide every lattice piece from S0. The rig still lowers, unseen, and there is no rig
  in the outro.

**New intro order.** The S1 projection uses the v1 record's footprint; the DRY recomputes it.

| Window | Frames | Seconds |
|---|---|---|
| Rise, glows on | [0, 104) | 0–4.16 |
| Dark hold | [104, 119) | |
| Glide in the dark | [119, 269] | 4.76–10.76 s, peak 151 cm/s, 600 cm lead |
| Hold on her first frame | [269, 282) | |
| Glow fade-out; bulbs hidden at 282 | [244, 282] | |
| 14 strikes; env crossfade [282, 584] | [282, 575] | 11.28–23.0 |
| Cut | 594 | 23.76 (was 431) |
| Slot | [594, 5859) | |
| Outro: blink-out, then env out | [5872, 6076] | |
| Rig glows back with the glide out (peak 291 cm/s) | 6091 | |
| Exit cut | [6241, 6266) | |
| End | 6266 | 250.64 s (was 6103, 244.12 s): +6.52 s, relength needed |

**Other v2 changes.**
- **Glows.** The 24 ceiling glows get a LightColor fade, white → 0, which multiplies the rise's Intensity keys rather
  than fighting them. They come back only after her lights and env are out.
- **Bulbs.** The 24 bulb meshes hide while the rig is dark. Their emissive pops off, but the glows are already at 0.
- **Glide.** It ends at rest, because she starts static (vel 0, [meas] DRY).
- **REVERT fixes.** It now also allows and backs up her dirtied map package, which APPLY needed live. It checks for a
  clean census after saving.

**Apply order (REVERT then APPLY; no UPDATE path).**
1. REVERT with this code and the v1 record. The args file is now set to REVERT. This undoes the level move, the copy
   shift, all `Klara Reveal -` bindings, the cuts, the hookin windows and the slot.
2. DRY. It refuses while the reveal is applied (SLOT_DRIFT).
3. `extend_scene_playback` with the printed mode (≈250.64 s).
4. APPLY.
5. `rebuild_managed_master`, then SavedMasterMatchesShow, then SceneCutBindingsResolve, then live cut bindings.
6. PIE stills at about 4, 10.8, 11.3, 14, 23.7 and 24 s.

An in-place UPDATE would need its own drift checks across 20+ bindings. REVERT + APPLY reuses paths that have both
been proven live.

## 9. v3: strike to her lit look, skip her dark opening (Gary, 7 Oct)

Gary's decision: "Strike to her lit look; skip her dark opening". Offline only. Nothing was run in Unreal, nothing
was built or committed. Harness: 60/60 pass. 18/18 seeded mutations of the v3 code are caught.

### 9.1 Why v2 stayed dark

- **Her lights.** Every light row in the v2 DRY has `target_first` 0.0 [meas `klara_reveal_dry_S1.json`
  facts.her_lights]. So all 14 strikes went to 0. Nine lights are above 0 at her last frame [meas same rows].
- **Her environment (a second fault, found now).** Both live records' `hookin_after` are missing four names that
  their `before` has: `Hers Dark: DirectionalLight`, `ExponentialHeightFog`, `PostProcessVolume` and `SkyLight`
  [meas `klara_reveal_record_S1.json` and `.restored-from-backup`]. Those are exactly the four env actors the reveal
  ramps (the harness checks this: `Revert.test_measured_records_show_the_rename`).
  - No APPLY step removes a binding. So `add_possessable` on an actor the hookin already binds returned the
    hookin's binding, and `set_display_name` renamed it [inf: the only explanation the records allow; the header
    `MovieSceneSequenceExtensions.h:403-411` says "new binding"].
  - Effect in v2: APPLY step 7 looks bindings up by name, so it missed these four. Their "Hers Dark" visibility
    stayed [104, 376) [inf from the record's before ranges]. Her sun, sky, fog and PPV were hidden until 15.04 s,
    while the crossfade ran from 282.
  - Effect on REVERT: it removed every `Klara Reveal -` binding, which deleted those four hookin bindings. That is
    the live `REVERT_READBACK` [inf: it matches the record diff].

### 9.2 Her lit frame Lh

`find_lit_frame` (`klara_reveal.py:578`) and `snap_her_frame` (`:567`); defaults are in `LIT_DEFAULTS` (`:96`). All
numbers are proposed, not Gary's.

- **Inputs.** Each of her lights' Intensity key curve from the copy: tick times, interpolation and tangents
  (`_ch_curve`). It is evaluated per frame by `curve_at`, which is exact for linear and constant keys; cubic is an
  unweighted Hermite [inf].
- **Per light.** The window is her start + 60 s.
  - plateau = the highest level the light **holds** for 1 s (a one-frame flash does not count);
  - `lit_at` = the first frame from which it holds at least 90% of that plateau;
  - a plateau of 0.001 or less means the light is never lit in the window.
- **Lh.** The earliest frame by which 80% of the ever-lit lights are lit (ceil(0.8 n)-th `lit_at`).
  - Cross-check: the normalised sum (each light divided by its plateau) first holding 75% of its plateau. If the two
    differ by more than 2 s, it warns `LIT_METRICS_DISAGREE`.
  - Snapped up so it lands on our grid. 30 to 25 fps gives a step of 6 of her frames.
- **Overrides.** `lit.frame` sets an explicit her frame. `lit.enabled: false` gives v2 behaviour.
- **Refusals.** `LIT_NONE` and `NO_LIGHT_LIT_AT_LIT_FRAME`.
- **Unkeyed lights.** Lights her LS does not key do not vote. They strike to their level value.
- **What DRY logs.** `KLARAREVEAL_LIT` (frame, raw frame, seconds into her sequence, votes, sum frame) and one
  `KLARAREVEAL_LIT_LIGHT` per light, with its plateau, `lit_at` and keys in the window, so Lh can be checked by hand.
  `KLARAREVEAL_LIT_CAMERA` gives the cut covering Lh, the binding, pose, lens and velocity.
  `KLARAREVEAL_ENV` gives the level value, the value at Lh and `her_keyed` for sun, sky, fog and PPV.

### 9.3 What changes at Lh

- **Strikes.** Each light is struck to its value at Lh (`target_intro`). A light that is dark at Lh is held at 0
  over [land, cut) with no strike. Fewer strikes can bring the cut earlier.
- **Colour.** Where her LS keys LightColor, her colour at Lh is held over [land, cut) (`_add_color_const`, `:1957`).
- **Environment.** The env crossfade targets her value at Lh where her copy keys it, otherwise the level value.
- **Glide and placement.** The glide ends, and the placement anchors, on **her camera at Lh**.
  - `_her_camera(copy, "lit", Lh)` reads the cut covering Lh, its binding, its pose and lens interpolated at Lh,
    and its velocity.
  - If her camera moves at Lh, DRY warns `HER_LIT_FRAME_MOVES`.
- **Slot.** The slot section starts **into** her copy at Lh: `slot_skip` (`:641`).
  - start_frame_offset = (Lh − her start) × 800 ticks.
  - skip = (Lh − her start) × 25/30 Scene frames.
  - The slot is her remaining length.
  - Unit [inf]: `MovieSceneSectionParameters.h:74-76` says "display rate", but the hookin and audio precedents use
    ticks. APPLY settles it: it reads back `get_parent_sequence_frame(slot, Lh) == cut` and that her end maps to the
    slot end (`SLOT_MAPPING_READBACK`, `:2376`), and refuses before any save.
- **Timeline.** `plan_timeline(..., skip)` (`:699`): the intro is unchanged, and the outro, exit and end all come
  `skip` frames earlier.
- **Audio.**
  - Her copy's audio moves with her. Her S1 `Animals_Project_CLICK` section [−311, 4165) would join mid-sound at the
    cut, with its first (Lh + 311)/30 s skipped [meas `klara_hookin_seq_record.json` her_audio_in_scene].
  - Scene-level audio and markers do not move. DRY lists those past the new end (`plan.audio`). The hookin's muted
    narration section [5216, 6091) would then run past the end. It is muted [meas hookin record narration].
- **Outro.** Unchanged: her last frame.

### 9.4 S1 projection (not a live run)

The v2 DRY kept only first and last values, so it **cannot** give Lh; her per-light keys were never read. The
projection assumes Gary's PIE observation that the lights "kick in" about 18 s into her sequence [inf: his estimate].
With her start at −310 that is her frame 230, which is on the grid.

| Quantity | Value |
|---|---|
| Lh | her frame 230 (7.67 s her time; 18.0 s in) |
| Offset | 432000 ticks |
| Skip | 450 Scene frames (18.0 s) |
| Slot | 4815 frames (192.6 s) |

| Strikes | Cut | Slot | End |
|---|---|---|---|
| 14 | 594 | [594, 5409) | 5816 (232.64 s) |
| 9 (lit at her last frame) | 481 | | 5628 (225.12 s) |

v2's end was 6266 (250.64 s). **S1 shortens**, so `extend_scene_playback` runs with the DRY's printed
`new_end_s`; Scene cues may be shortened [decl `extend_scene_playback.py:344-346`].

### 9.5 Bindings fix and REVERT

- **`_possess` (`:1914`).**
  - A binding that already existed is never renamed. It is listed in `record.shared_bindings`.
  - Our tracks on it are named with the `Klara Reveal -` prefix, now including Visibility tracks.
  - APPLY reads back every hookin window at its planned range (`HOOKIN_WINDOW_READBACK`, `:2356`).
- **`revert_actions` (`:871`, pure, tested).**
  - Shared bindings: strip our tracks only.
  - Legacy v1/v2 bindings: a `Klara Reveal - X` binding whose `Hers Dark: X` is in the record's before-list, is
    missing now, and still carries the hookin's own Visibility track is **renamed back** and stripped.
  - Every other `Klara Reveal -` binding is removed, children first.
  - It refuses (`REVERT_UNRECOVERABLE`, nothing changed) if a hookin name cannot be recovered.
- **REVERT read-back (`run_revert`, `:2444`).** Each check is named: hookin windows, leftover prefixed bindings and
  tracks, cuts (range **and** camera GUID), slot (range **and** offset), glide camera gone. It also restores the slot
  offset.
- **Not live-proven.** `remove_track` on a binding [inf; probed in `api_table`; memory: it returns None, so it is
  read back].

### 9.6 Apply order

**Recommended undo for v2: restore from backup.** It is proven live tonight for v1 [meas
`klara_reveal_record_S1.json.restored-from-backup`]. The fixed REVERT is the alternative.

1. **Restore from backup** [inf: the procedure is as tonight's v1 restore].
   - Editor closed with Don't-Save.
   - Copy `Backups/PreKlaraReveal-S1-KLARAREVEAL-20261007-004756/` {`LS_Animals_1_S1Hangar`, `LS_DevScene_01`,
     `L_Animals.umap`, `L_InfinityStage_V1VerticalSlice.umap`} back over Content.
   - The v2 APPLY copied `L_Animals.umap` before saving, so it is pre-v2 [inf from the code order].
   - Rename `klara_reveal_record_S1.json` to `.restored-from-backup-v2`.
   - The restored `LS_DevScene_01` is 250.64 s, the hookin slot is [376, 5641) with offset 0, and there is no glide
     camera.
   - **Or REVERT** with this code and the v2 record (set the args file mode to REVERT; it is APPLY now). It should rename the four
     bindings back.
2. **DRY.** It refuses `SLOT_DRIFT` if anything is still applied. Read `KLARAREVEAL_LIT*`: check Lh and the
   per-light curves. Gary or the conductor can pin `lit.frame`.
3. **`extend_scene_playback`** with the printed mode. This **shortens** the Scene to the planned end (≈ 222–233 s for
   S1).
4. **APPLY.**
5. `rebuild_managed_master`, then SavedMasterMatchesShow, then SceneCutBindingsResolve, then live cut bindings.
6. **PIE stills** at about 11.3, 14, 18, cut − 0.1 s and cut + 0.1 s. Check that the lights are lit **before** the
   cut and that nothing changes across it.

## 10. v4: S4 (Gary 7 Oct: adapt her dark opening + pan, or strike as in S1)

Offline only. Tiers per claim. Bytes = `Content/LS_Children.uasset` (her original), `InfinityStage/KlaraHookin/
LS_Children_S4Hangar.uasset` (our copy), `L_KK_children.umap`, `KK_S1_Animals/L_Animals.umap`, read by the harness
(`S4Bytes`), extending the S6 reader with the soft-object-path table and UniversalObjectLocator fragments.

### 10.1 Why the live DRY stopped `HER_CAMERA_BINDING_FIRST: 0`
- Her first camera-cut section [0, 2) (her frames, 30 fps) binds GUID `c6fa8837...`, which has no possessable, no
  spawnable and no binding reference, in the original and in the copy [meas]. It is a dangling cut (a deleted camera).
  Every later cut binds a CineCamera in `/Game/L_KK_children` (locators `CineCameraActor_0/_1/_5`) [meas]. The binding
  IDs carry no sequence ID or space (root, local) [meas: only Guid + ResolveParentIndex 0 serialised]. Not a spawnable,
  not a sub-sequence (no sub tracks), not L_Animals.
- Fix: `first_bound_cut` reads her first camera at the first bound frame (2) and reports `dangling_cuts`. S1's first
  cut is bound, so its path is unchanged [meas: replay below].

### 10.2 Why the bindings look "very off"
- 5 `LightComponent0` possessables have parents with no possessable; the parents' binding references point at
  `L_Animals` SpotLight_1/17/20/22/23 (S1's level, in the S1 hangar) [meas]. They key constant Intensity 8-19.9.
  Whether they resolve without a parent possessable is [inf: engine private code absent]; if they do, S4 drives S1's
  lights. Not fixed here (the copy is the hookin's): propose deleting those 5 bindings from the copy.
- `L_Animals` has actors labelled `CineCameraActor`, `CineCameraActor2`, `CineCameraActor3`, `SpotLight2/3/4/6/7` and
  `Floor`, the same labels as her S4 bindings [meas]. Sequencer resolves by path, so playback is fine; our label
  match was ambiguous. Fix: `pick_camera_actor` prefers her own level.
- The copy's keys are shifted by exactly her LevelTransform (13639.97, 240008.5, 0) [meas].

### 10.3 Her opening [meas bytes; curves are CUBIC with stored zero tangents, i.e. eased]
- Playback [0, 4920) at 30 fps (164 s); 3 audio sections from -1.87 s; markers D 11.6 s, C 36.2 s; no fade track.
- 0-0.07 s: dangling cut (no camera). 0.07-11.7 s: CineCameraActor at (692, 293, 91), pitch 6, yaw 5, no rotation keys:
  a 60 cm sideways drift, not a pan. 11.7-26.5 s: an eased dolly back 18.9 m and 4.6 m sideways to the wide on the
  children; the pigeon drops 23.1-26.1 s and lands (landing anim from 26 s).
- Lights at 0 s: SpotLight and SpotLight2 are 0 and rise to 160 cd over 6.5-12.8 s and 5.5-13.1 s; window and
  SpotLight3 hold 160, SpotLight7 17, SpotLight6 0.64; SpotLight4 0 until 22 s.
- `opening_darkness` at her frame 6: only SpotLight and SpotLight2 cover her framed view (27 and 35 of 35 samples),
  both 0, so lit fraction 0.0: DARK [inf: cone/radius proxy, no occlusion or bounce]. Unweighted, 45 % of her light
  is on: the "total darkness" is what her camera frames.

### 10.4 The two styles (projection: S4 L/C/E 104/376/4476 [meas hookin record]; box, footprint and exit pose are
stale or SYNTHETIC [inf], so the live DRY decides)

| | her_dark_pan (auto default) | strike |
|---|---|---|
| her frame at the cut | 6 (0.2 s; first bound 2, snapped) | 354 (11.8 s, detected) |
| glide in the dark | [119, 357], 9.5 s, peak 287 cm/s | same |
| lights | no strikes; window/SpotLight3/5/6/7 ramp to their values over [370, 445]; SpotLight, SpotLight2, SpotLight4 stay 0 | 7 strikes [370, 485], to values at 354 |
| cut, slot | 455 (+79), [455, 4550) | 524 (+148), [524, 4329) |
| her audio | joins 2.07 s in | joins 13.67 s in |
| end | 4977 = 199.08 s | 4756 = 190.24 s |

Both warn `LEAD_ABOVE_RANGE` (her camera sits 13 m inside her set: lead 1792 cm). Strike also warns
`HER_LIT_FRAME_MOVES` 6.7 cm/s (her dolly is easing in).
