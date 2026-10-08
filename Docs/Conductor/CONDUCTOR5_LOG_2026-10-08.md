# Conductor 5 log — 8 Oct 2026 (UTC)

## 00:00–01:50 — S3 timing to sound, lighting pass (Gary in the editor, then on a 15-min break)

All [measured] by success markers unless marked.
- Lattice glow 8→1 cd, uplights 4000→1000 (S3L-20261008-000149 / -000632). BUG found: the S3 float hold in
  LS_DevScene_03 holds lights by channel DEFAULT after 31 s, so rise-only edits reverted after the fold. s3_light_levels.py
  now writes the hold defaults too (fixed in S3L-20261008-003136).
- Opening (Gary): dark, rig folds, figures appear in the dark, ghost, then waves. S3OPEN-20261008-003115; Gary then moved
  the ghost to 7.6–8.1 s by hand; figures at Scene frame 100 (S3FIG-20261008-012750, rise 405→125 [inferred 1:1 nesting:
  the fold section is 32.375 s vs 31 s inner, play rate unreadable]); strike group OFF always (Gary: "don't like them"),
  rig practicals + lattice 0 all scene (S3L-20261008-003136, -012916).
- Editor crash ~00:18 during Gary's manual editing; restore list empty.
- Audio: Gary's "Shore_People_Stereo(1).wav" = sha-identical to DerivedAssets/.../f32/S03_Shore_People_Stereo_f32.wav;
  the 16-bit derivative (sha 46cc34c7…, 246.877 s) imported as SW_S3_Shore_People, track "Scene Score" in LS_DevScene_03
  from frame 0 (SCENEAUDIO-20261007-214457, local-time run id). scene_audio_import.py gained start_option scene_start
  and marker kind "given". Eight audio markers; old 'S3 1–7' deleted (S3MREPL-20261008-014526); VampStart/VampEnd kept
  (transport reads them).
- Closed Gary's open Sequencer tab on LS_DevScene_03 (census clean) so the tools could run (close_sequencer.py).
- Drama lights S3DRAMA-20261008-014904 (after a failed first APPLY, CUBIC enum → Don't-Save restart, record kept as
  .failed-…): Clam Key spot 400 cd 4200 K on the risen clam (ramps with Gary's rise keys 3593→4170), Pearl Glow pink
  point attached to the pearl (faint in the rise, 40 cd from 4290, out at 3:10 = 4560), 4 cool 6500 K wall-graze spots
  3000 cd (choir 3120→, 30 % after 3:10), wave lights ×2.5 / ×1.8 + a deterministic shimmer. Values are first guesses,
  NOT seen rendered.
- Both tests green after the writes (SavedMasterMatchesShow, SceneCutBindingsResolve singly).
- Grease red tint: subagent building an offline v2 master + swap (not run).

## 02:00–02:10 — S3 retime to the audio (Gary questionnaire ~02:05)
- Gary: grease red tint stays BUILT, not placed (swatch E chosen; 6424067). Lights and audio "good".
- SLOT BACK from finishing touches 02:05 (clam looks v3 swapped: Pearl_v3/Shell_v2/Mantle_v2; tests green).
- S3RETIME-20261008-020659 [measured APPLY_OK, tests green after]: clam rise 3593–4170 → 1080–1440 (0:45–1:00; 100 keys on
  clam/lid/mantle/pearl/millstone); Clam Key + Pearl Glow keys follow (glow bright 1440→1560); B07 orbit cut + 721-key
  VampOrbit → 1440–2880 (×2 slower, the cello); B04 cut + keys → 3480–4200 (×0.5); B02 cut 15–30 s, B03 30–45 s
  (45–60 falls to S3 Wide); figures' teleport LS_Clams 1494/1495 → 1461/1462 = Scene 1439/1440, on the 1:00 cut
  (Gary: teleport while the camera is distracted, no turn). Backup Backups/PreS3Retime-S3RETIME-20261008-020659.
- OPEN: VampStart/VampEnd still 145–175 s, the window the orbit was built for; now B04's compressed move plays there.
  Gary to say whether the vamp follows the orbit to 1:00.

## 02:10–02:35 — Gary's corrected audio times; lid opening
- Gary: chorus 2:08–3:07 ("petering out by 3:07"); Puss decides after 3:15, takes the pearl ~3:20; 3:23→end wailing.
  The 3:00/3:10 markers were wrong. S3MSET-20261008-021848APPLY: removed 'choir sings 2:10', 'Puss narration 3:00',
  'Puss takes clam 3:10'; added chorus 2:08 / chorus ends 3:07 / Puss decides 3:15 / Puss takes pearl 3:20 / wailing 3:23.
- Pearl glow (Gary confirmed here): 4 cd → 40 cd over 1:02–1:04 (2–4 s into the cello), dims to 12 cd over 3:02–3:07
  (chorus ends), out at 3:20–3:21 (S3KM-20261008-021829APPLY). Wall grazes follow the chorus: up 3072/3102→3144/3174,
  down to 30 % at 4488→4584 (four S3KM runs 0218xx–0219xx) [inferred from Gary's chorus correction; not separately asked].
- Lid opening (finishing-touches tool d7dec87): first APPLY CLAMOPEN-20261008-021929 refused READBACK on ~2e-6°
  float rounding → Don't-Save restart; READBACK_TOL 1e-4° added for new key values (harness 64/64);
  CLAMOPEN-20261008-023043 APPLY_OK (lid 0°→80° over 1446→1746, tangent_changes=0). Tests green after.
- 02:36 Gary questionnaire: vamp follows the orbit to the cello (VampStart 1440 / VampEnd 2880); B08 extended to 3:23
  (4200–4872), B09 4872–5040 (S3CV-20261008-023611APPLY); wall grazes stay full after the chorus (four S3KM 023611–023615).
  Tests green after.
- 02:37 Gary: "When puss takes the pearl, it should disappear with a fade over 4s, leaving 1s of a glow halo." Glow light
  done (S3KM-20261008-023655halo: 12 cd to 4800, 18 cd 4872–4896, 0 at 4920). The pearl MESH fade needs a keyable Fade
  param on the pearl material; that was requested from finishing touches (they own the pearl look). Pending.
  Tests green after (SceneCutBindingsResolve re-run singly).
- ~03:25 Bones imported (Gary: "Import only", then "just do the bone import for now"): SM/T×3/MI for HominidJaw,
  HominidLegBone (MI RoughnessMultiplier 1.95), HominidRibcage under /Game/InfinityStage/Dev/Generated/S3Props/
  (runs S3PROPS-20261007-2318xx…232443, each VERIFY_TEX 4096², BUILD_MAT OK) [measured markers]. Not placed.
- ~03:45 Gary: "I need S3 Shot B07 to revolve around the new clam position". s3_shots_fix.py gained `only` (orbit-only run):
  S3SHOTS-20261008-034435APPLY wrote the 721-key orbit +(1062.43, 169.5, 22) and read it back, then refused at CENSUS
  because an unconditional rise.modify() dirtied LS_S3_HangarRise with no data change (bug fixed: rise.modify only for
  old_clam). Finished with s3_orbit_finish_save.py: centre verified (15484.40, 160169.50), both saved
  (S3ORBITSAVE_OK) [measured]. Closed and reopened Gary's Sequencer tab on LS_DevScene_03 around the write (census clean).
- Queued (Gary via finishing touches): clam lid opening 80° → 55°, CLAMOPEN REVERT → DRY → APPLY in their pearl slot.
- ~05:20–05:40 S3 Play-only vanishing FOUND + FIXED [measured]: while PLAYING, bHidden flipped True on the clam parts,
  millstone and all six figures between S3 31.0 and 35.4 s. The Hangar Fold sub-section ends at Scene 777 (32.4 s;
  Gary lengthened it from 744) and its Visibility sections (completion = project default) restored the pre-animated
  hidden state; scrubbing in the editor never crosses the end, so the editor looked fine. Fix: S3KEEP-20261008-053739,
  KEEP_STATE on the 14 rise Visibility sections; re-measured in PIE: hidden=False at 30.5/34.9/41.5/48.0/54.5/59.0 s,
  clam rising. (A paused-PIE A/B, waves hidden vs shown, also showed the clam rendering at 0:52.)
- Choir: 8 visible bulbs on the glint lights (S3BULBS-20261008-052801, MI_S3_ChoirBulb_Glow Intensity 40, lights ×0.16);
  ghost light flame flicker (S3KM-…flame). Take (Gary): the pearl dims 30→8 cd at 3:20–3:22 and disappears 3:26–3:30
  (S3KM-…take); successive dim-outs S3FADES-20261008-053916: clam key 3:22, grazes 3:24/3:26, wave rows far→near
  3:28/3:30/3:32, warm side 3:34–3:36; only the ghost flame is left. s3_pearl_fade.py now fades 4944→5040 to match.
  Tests green.
- ~06:00–06:16 Grease tint PLACED (HP_TINT 20261008-020151, 1034 twins, verify paired=1034; Gary: "we do need to up the
  visibility"). Choir glint point lights keyed 0 (S3KM …glint*), then hidden + intensity 0, bulb glow 40→12, all 18 S3
  rect lights diffuse 0.1 / specular 1 (S3RECT-20261008-060812; includes Gary's Warm Side2/3/4). S3 PPV reflections
  (S3PPVR-20261008-061630): Hit Lighting for Reflections, reflection quality 4, scene detail 4, view/trace 40000,
  max roughness 0.6. QUEUED for the MRQ renders: r.StaticMeshLODDistanceScale=0.25 (render cvar only; not project-wide).
- Gary's PIE "cut-out" at S3 ~2:13 (05:44:41): clean EndPIE, no crash/error, no conductor MCP call in the window; not
  reproduced from 2:02 with performance mode off. Vamp did NOT loop in his run (it played on into the 2:05 shot).
  Rehearsal: Cue Desk menu "Rehearsal Transport (ignore external sound locks)" enables seek/FF in S3.
- ~06:29 S3FLAME-20261008-062908: Clam Key ×1.4, all 18 S3 rect lights diffuse 0.25, flame flicker on the 7 keyed wave
  lights (curve × flame, fades kept) + new S3.Flame tracks on Gary's Warm Side2/3/4. FAULT: it also added S3.Flame
  tracks to the 8 strike/daylight rects (their keys live in the rise / float-hold bindings 'S3 Hangar Float Hold: …',
  which my owner match missed, and their editor intensity was nonzero), which would have relit them; removed by
  s3_flame_remove_strike.py (S3FLAMEFIX_OK, 8 removed; first run refused, left the scene dirty by modify() only).
  Vamp markers removed (S3MSET-20261008-062837vamp; Gary's recording: at 2:00 the playhead lands on 4:19.9) — C3 on
  the notes list for the build window. Tests green.
- ~06:35–07:00 rect lights off until B02 (S3RECTON-20261008-063217); choir lift on the grazes +25% 2:43–3:07
  (S3ENV-20261008-064956, saved after Gary's PIE refused the first save); jaw glint spot (S3JAW-20261008-065500,
  0:30–0:45); ocean ground rows ×1.5 size/attenuation (S3OCEAN-20261008-065942) and ×1.2 keys (S3ENV …ocean); B06
  handheld shake as an ADDITIVE section (S3HAND-20261008-070009; delete the section to undo).
- Lumen hardware RT [measured]: on the 2:10 frame, r.Lumen.HardwareRayTracing 1 shows extra wall reflections (a pink
  smear Gary doubts is the clam: he saw the rock visible before the clam). Frame time 16.3 -> ~17.5 ms (paused frame,
  6 samples × 2). NOT made permanent; Gary's call pending.

## ~07:10–07:35 Overnight Phase A
- Codex P1–P4 dispatched (--worktree, codex_briefs/); P5 (mocap calm/frenzy timeline, Gary) dispatched. P2 done: held
  patch Scripts/patches/2026-10-08_vamp_end_jump.patch (sha 43e54bf7…, git apply --check OK on main; not built).
  Diagnosis [declaration]: start-at-playhead schedules PlayTo(Scene end); Vamp Tick returns early while the player
  reports paused at that bounded target, so the Scene-end PlayTo wins [inferred race].
- Finishing touches A1 (pearl twin, Fade/Dither MIs, twin StaticMeshActor_546) + A3 (lid 55°) done; A4 S1 pre-roll
  refused safely (probe gating + sub-frame section) — their tool fixes pending.
- A2 pearl fade keys S3PFADE-20261008-072738 OK (twin Fade 1→0 4944→5040, solid off 4944/twin vis 4944–5040). Two
  failed APPLYs before it (5.8 signature: MovieSceneComponentMaterialParameterSection.add_scalar_parameter_key(
  MaterialParameterInfo, time[ticks], value, layer, asset, interp)) → two Don't-Save restarts; sky toggle + HWRT cvar
  re-applied after each.
- Gary's leftover PIE ended; his level saved on his word ("Save it").
- W&T production curtain bake relaunched as unfurl_sleight_b1hop10_p02 (launcher copied to
  Saved/CodexSoftGoods/run_prod_unfurl.ps1; p01 died at ~frame 231/390 in the 7 Oct crash). ~6–7 h.
- A5 S1 snap probe S1SNAP-20261008-072753 (arm: scrub to P01 end −1 s, play through): camera continuous at the cut
  (Δ 0.001 cm, 0.0°, FOV 0), hangar root pitch smooth −33.8° → −31.6° across it; flag EXPOSURE_SETTINGS_CHANGE at the
  cut. [measured] No snap in a scrub-started play; Gary's screenshots were paused frames. Next: 'watch' mode in his
  natural play from P01 start.
- A6 clam SDF probe inconclusive (read the wrong flag); HW RT now on, so reflections trace real geometry.
- No renders tonight (Gary). Tests green after Phase A.
- ~07:35–07:45 P01→S1 SNAP FOUND + FIXED [measured, pie_s1_rig_tap]: at the cut the S1 roof hinge flipped (world pitch
  −36.1 → −57.8, yaw 0 → 180), the roof jumped ~4 m and the lattice +1.57 m; root and camera continuous (S1SNAP). Cause:
  every Arrival logged INFINITY_HANGAR_INITIAL_POSE movers=1 — AdditionalInitialTransformDrives was empty, so roof/lattice
  sat in the saved LANDED pose through the Passage and the rise snapped them at Scene frame 0. Fix ARRMOV-20261008-073648:
  roof hinge + lattice fly drives on S1–S5, lattice on S6 (map saved, backup PreArrivalMovers-…). Re-measured: movers=3
  (S6 2), and the roof hinge −47.9 → −52.1 → −56.3 → −60.1° and lattice 64 → 1461 cm move smoothly across the cut. Same
  fault latent at every Passage→Scene cut [inferred]; fixed for all six. Tests green.

## S4 entry check (P04 -> S4), 8 Oct ~08:00 UTC (final jobs 3.3)
- [meas] PIE taps (pie_s4_tap, 1 s spacing, S4 -2 s to +32 s). Her L_KK_children actors appear at S4 +4.4 s. From then
  until the cut into her slot (S4 +16.2 s, Scene frame 405) the children and pigeon do not move at all.
  - Pigeon at (11477, 239979, 88); it jumps 33.6 m at the cut.
  - Pendulum: the anchor stays at the level location (12301, 240040), but the ball swings ~1-1.2 m every second (its own
    BP tick). At the cut the anchor jumps 5.1 m to her LS location (12811, 240090), and the ball keeps tick-swinging
    there.
- [meas] Stills PSTILLS-S4-20261008-080010-s4entry_check:
  - 5 s: children lit in BIND POSE (arms out) with the pigeon frozen;
  - 9 s: the pendulum ball passes the lens;
  - 13 s: black;
  - 16.4 s: her first shot, ball still;
  - 17 s: ball swinging hard, which is the tick (her LS holds it for 6.4 s) [inferred from KLARAPENDULUM-20261007 probe].
- [meas] DRYs:
  - KLARAPENDULUM-20261008-035930 apply_ready=1 (tick-off event repeater in LS_DevScene_04).
  - KLARAPREROLL-20261008-035930 apply_ready=0. The single refusal is REVEAL_NOT_V5: the v5 reveal (arrive in the dark)
    was never applied, and the live S4 is still v4.
- **Pendulum tick-off APPLIED** KLARAPENDULUM-20261008-041003 (Gary's own yes, questionnaire ~08:05 UTC). First try
  -040829 hit ENDPOINT_INVALID, because quick binding needs the UFunction name SetActorTickEnabled. That left a
  Don't-Save restart, and the record was renamed .failed-*. Tests: SavedMasterMatchesShow + SceneCutBindingsResolve
  green [meas].
  - PIE re-tap [meas]: the ball is static (12319, 240048, 44) from 6.4 to 16.0 s. At the cut the anchor moves to her
    LS location and the ball holds still there (her +30° hold). Her swing from her frame 191 was NOT reached in the tap
    (the tap ends at 18.5 s).
- Gary on S4 children: "If Klara's first cut is black then start with black, if not then v5". Her first shot is NOT
  black (16.4 s still: lit pendulum close-up) [meas] -> v5.

## Night of 8→9 Oct (Gary asleep). Conductor work, in order
- Gary (own words, chat) asked for P01 smoke hidden, the P01 bay-1 wings on the stage front, and P03 lit like P01.
  He also gave notes 4.1-4.6 (FINAL_JOBS).
- **P01 smoke pots disabled** FXENABLE APPLY 20261008-042536: Show attachments `enabled=false` for FX SMOKE P01
  B09 L / B25 R / B41 L; P01 materialized; Show + level saved; backup Backups/PreFxEnable-20261008-042536.
  REVERT via fx_attach_enable.py. [meas] Probe after: no FX SMOKE P01 actors spawned.
- **Stage front temp wings** FRONTWINGS-20261008-042743: two StaticMeshActors using
  SM_FlatV3_P01_L_1_roccoco_L_t5p and SM_FlatV3_P01_R__1_roccoco_R_t5p at x -45, inner edges |y| 850 (spans
  -1574..-850 and 850..1575), z 0, attached to Structure 01, tag PussStage.StageFrontTemp. Map saved. [meas]
  - NOT yet seen in the Opening view: the stills tool's "Opening" mapping finds 0 segments, because the real label is
    "Opening — Curtain"; the stills tool needs a prefix match. Possible clash with the curtain overshoot pile at the
    floor (pile ±1220 at the lip) [inferred].
- Tests green after both writes (SavedMasterMatchesShow, SceneCutBindingsResolve) [meas].
- **S3 0-8 s light tap** (pie_lights_tap, s3_lights_tap.jsonl) [meas]:
  - The camera sits at (10922, 160000, 180), the P03 end, for S3 0-6.5 s.
  - P03 score lights stay LIT the whole time: pyre practicals B21 1600 cd at 10.9 m, B20 1520 at 14.8 m, B17/B18/B14,
    Blink Spot W017 1164, Rig Slash W020 at 15 m.
  - Nothing near the camera switches on at ~4 s.
  - "S3 WaveV3 Warm Side3" rect is lit at S3 -0.33 s (P03 tail, before the S3 sequence evaluates) and is off at 0.03 s.
  - [inferred] The spoiler Gary saw at 0:04 is most likely the P03 pyre/score lights reaching into the dark S3 arrival.
    This is unproven, because how much the hangar walls block was not measured. Proposed fix: P03 score lights out by
    the S3 cut (fold into P16's P03 relight).
- Codex launched: P8 S4 v5, P9 interactions (done 53/53), P10 front/void/ending (done), P11 music timing, P12
  handprints, P13 opening lighting, P14 rehearsal robustness, P15 video transitions + aspect, P16 P03 = P01 lighting.
  P3, P6 and P7 imported and committed.
- Stage front wings re-placed with inner edges at ±700 (FRONTWINGS-20261008-043305, after REVERT -043302); in the
  Opening stills (PSTILLS-OPEN-...-frontwings_open700) they frame the curtain. scene_stills.py now maps "Opening".
- **P11 imported** (0199f29, harness 21/0) [meas by Codex, harness rerun here]:
  - Opening major flurries peak at 37.44, 57.36 and 70.44 s (DerivedAssets/MusicAnalysis/Opening.png).
  - Music-locking all Passages shrinks the Master by 188.5 s, mostly P05 (186 → 42 s).
  - P05 Camera.HeightOffsetCm has 2 keys past its new end; P06 uses 110.56 s of its 125 s WAV.
  - Gary to confirm before any relength.
- **P12 handprints imported** (14d109b, harness 17/0). Codex's layout: 198 marks in the B06 band (2x), but bunched
  into ~4 tall columns. Conductor variant "many" (2790829, hp_dense_config_many.json): the same 198 marks as 20
  shorter climbs spread along the band (previews/many/). Gary picks; nothing applied.
- **Pearl** (finishing touches, merged 1caceb9): BUILD_MAT Pearl_v3_GreenOrange OK, no swap. Their stills [meas]: the
  keyed 40 cd "S3 Drama Pearl Glow" clips every subsurface pearl to white. Held A/B: s3_key_move_args_pearlglow_low.json
  (peak 3 cd), not applied.

## ~09:00-09:25 UTC: P03 relight applied, then GPU LOST (machine needs a reboot)
- **P03 = P01 lighting APPLIED** P03ASP01 APPLY run 20261008-051137 [meas]: removed 286, added 377, kept 69 specials
  (score/keyed lights), 7 atmosphere changes; Show + level saved; read back; SavedMasterMatchesShow +
  SceneCutBindingsResolve green.
  - Backup: Backups/PreP03LightingAsP01-20261008-051137. Record p03_lighting_as_p01_record.json.
  - REVERT: args mode REVERT, confirm "REVERT P03ASP01".
  - Tool fixes before it ran:
    - hue-only colours (P03 dims its 42 "Low" lights via near-black RGB);
    - read-only GUIDs set via import_text (AttachmentGuid, ReplicatedFromAttachmentGuid);
    - original-error logging;
    - 1e-3 float tolerance on the atmosphere read-back.
  - Three failed APPLYs before it, each rolled back in memory, followed by a Don't-Save restart.
  - Before stills: PSTILLS-P03-20261008-085231-p03_before_asp01. NO after stills (see crash).
- **Crash 09:12:34** [meas, Saved/Logs + Aftermath dump D3D12.0.2026.10.08-05.12.32.nv-gpudmp]: during the P03 after-stills
  in PIE, DXGI_ERROR_DEVICE_REMOVED (DeviceRemovedNoGpuFault), breadcrumbs VolumetricFog::LightScattering, frame
  3524-3525; access violation in Background Worker #4. VRAM 10.3 of 15.2 GB.
- **Relaunch 09:22**: `nvidia-smi`: "GPU is lost. Reboot the system to recover this GPU". The editor falls back to D3D11
  (unsupported) and cannot run. Stuck editor killed. **Machine reboot needed: Gary's call** (the curtain bake pid 36792
  and Codex P17 are still running on CPU).
- Cause, [inferred, NOT proven]: the P03 relight adds ~91 lights (377 vs 286), all P01-style, inside P03's
  volumetric fog. That is a plausible GPU overload at the TDR limit (TDR delay 2 s). Against it: a GPU timeout already
  hung the editor at startup at 08:59 [meas], BEFORE the P03 APPLY, so the GPU was unstable earlier tonight.
- **Morning order:**
  1. reboot;
  2. editor_sky_toggle;
  3. P03 in Play from the start with PERF_OFF, watching for GPU timeouts.
  4. If it fails again → REVERT P03ASP01 and re-test, so P03 vs the GPU is the measured difference. Also check
     volumetric scattering on the new P03 lights (P01's volumetric settings were copied).

## After the reboot (8 Oct ~19:20 UTC)
- GPU check [meas]: RTX 5070 Ti, driver 610.88, 28 °C, 500 MiB used, no throttle reasons. The Windows System log has
  ONE display event: 4101 "nvlddmkm stopped responding and has successfully recovered" at 05:12:32 local (the P03-stills
  crash). The 04:59 startup GPU timeout left no Windows event.
- Editor started clean (0 GPU timeouts); sky hidden.
- P03 in PIE [meas]: played -2 → 28 s; 0 GPU timeouts; dt median 17.9 ms, p90 20.4, max 21.9 (48 samples); ~1380-1420
  lit light components.
- P03 after-stills retaken: PSTILLS-P03-20261008-192314-p03_after_asp01, 0 GPU timeouts. The crash did NOT repeat, so
  the cause of the 05:12 TDR is unproven [inferred: a transient GPU fault, or load spike + capture].
- Look [inferred, for Gary]: after = warmer/redder; the mid-passage frames (50/70%) read as a uniform red wash with less
  contrast, and the P03 light shafts (BeamLook) are much weaker after the atmosphere was matched to P01.
- **Build-window queue** (held patches, review before applying, stacking order matters):
  1. vamp end-jump: Scripts/patches/2026-10-08_vamp_end_jump.patch.
  2. fixtures bulb light sway: Scripts/patches/2026-10-08_fixtures_bulb_light_sway.patch.
  3. Rehearsal preference on PIE (P14): Scripts/patches/2026-10-08_rehearsal_preference_on_pie.patch.
  4. Cueing, in this order: CD1 → CD2 → UX1 (cueing_UX1_cuedesk_panels_shed_load.patch, 520ce63; panel toggles,
     resizable, AssetDetails shed, INFINITY_CUE_DESK_OPEN_MS).
  5. P15 video-transition subsystem (Scripts/patches/P15VideoTransitions, larger).
  6. P18 sky auto-hide startup ini patch (config only).
- Curtain p02 salvage: finishing touches built Tools/CurtainBake/stream_lowpass.py (harness 10/10, not run). Waiting for
  Gary's pick (explained smoothing, 8 Oct evening).
- **S3 crowd baseline** (5-figure, before P21) [meas, PIE, pie_dt, 30 samples each, 0 GPU timeouts]: S3 0:14+ dt median
  19.3 / p90 20.9 / max 21.5 ms; S3 1:28+ median 20.5 / p90 22.8 / max 24.0 ms. Codex P21 (S3 crowd: 20 live
  figures, establishing sway, frenzy build, choir sway from 1:30, handprints 8 s) launched.
- Cueing RB1 (f0736f3, rehearsal bar + Show Trims) added to the build queue after UX1. Music/Ambience trims need music
  waves on a Music SoundClass (content step).
- **Shoreguy cloth v3 APPLIED** (Gary: "Yes, apply + show me"): S3LIVESACK BUILD -155203 (16 assets), REVERT v2
  -155408, APPLY v3 -155422 (backup Backups/PreS3LiveSack-S3LIVESACK-20261008-155422), VERIFY -155429 0 fails [meas].
  - Five figures; Shore05_M53 is absent from the level (Gary: "5 figures now"). The v2 record copy drops M53; the
    full original is kept as .orig-with-M53.
  - Back pins: M56 and F55 only. Crown-only for F52 (bowed, back disc catches 0 particles), M59 (0 particles) and F25
    (BACK_FACING 73°, refused by BUILD preflight).
  - Fixed s3_sack_livecloth.py run_revert: v2 records store instance_asset_override as a LIST; the revert indexed it as
    a dict (it could never have run).
  - Stage-front actors relabelled without "TEMP" (SFRELABEL-20261008-155156): the BUILD guard refused on
    TEMP_ACTORS_PRESENT.
  - Restarts: 2 Don't-Save (BUILD guard after asset creation; REVERT list bug). Nothing saved wrongly.
- Outfit (loincloth-tone shorts): APPLY P1OUTFIT-20261008-155452 FAILED RESOLVED_READBACK on Shore01_M56 (the material
  override did not resolve as planned). Don't-Save restart; record renamed .failed-*. NOT applied; needs a live debug.
- S3 stills after the cloth v3 (PSTILLS-S3-20261008-200013-s3_cloth_v3b): figures are too dark/small in these frames
  to judge the cloth. A close-up check is needed.
- GPU: 2 GPU timeouts at editor STARTUP 19:56:10 (recovered), the same pattern as 04:59.
  [inferred] Correlated with the HWRT persistent-SBT build at startup; 0 timeouts in PIE/stills since.
