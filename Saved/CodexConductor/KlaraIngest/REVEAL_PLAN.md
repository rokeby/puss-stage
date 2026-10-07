# Klara reveal: intro | cinematic slot | outro (7 Oct, offline)

Offline only. Nothing was run in Unreal or over MCP, nothing was built or committed.

| File | Role |
|---|---|
| `klara_reveal.py` | The tool (DRY / APPLY / REVERT, one Scene per run) |
| `klara_reveal_run.py`, `klara_reveal_request.json` | Runner and MCP request |
| `klara_reveal_args.json` | Arguments: mode DRY, scene 1 |
| `test_klara_reveal_offline.py` | Harness: 43/43 pass; 22/22 seeded mutations caught |

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
