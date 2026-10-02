# Scene 3 — beat sheet (Gary, 1 Oct 2026, conductor session)

**Authority:** Gary's own words, verbatim below. Everything after the beats is the
conductor's reading of what it implies — marked as such, not decided.

## The beats (Gary, verbatim)

1. we arrive at the scene, the lights strike and we are in this eerie seaside place
2. we see the figures swaying, camera cuts from wide to figures.
3. Beyond the crowd of figures we see them surrounding a clam on a pedastal, the clam is shut
4. More shots of the figures with moving waves in background, they are getting more agitated and we get a couple more angles on them
5. As they agitate a lot (2min or so in) the clam mouth slowly opens
6. We see close up of it opening
7. There is a pearl inside glowing, we hear the song of forgetting
8. The figures (still out of focus in bg) start to calm
9. they stand calmly again, swaying (basically return to start of each figure's animation
10. we defocus a bit as we hear puss's thoughts (in the narration)
11. the pearl rises out to be at the centre of the camera, kind of dangling in front of it, showing that Puss has taken it.
12. We float with the pearl out of the scene, as it drops out of view and we go to the curtain for the boy cat interaction.

## Related rulings (Gary, same session)

- The centre of the diorama should be **about 10 m in front of the camera**, mid-box —
  today the figures stand right up close to it.
- Scene 3 cameras get defined **after** the diorama is set up, and **won't be moving**.
- `LS_Clams` was a test of the clam animation. **The animation stays in use; its cameras
  start from scratch.**
- Earlier (1 Oct morning): the cast appears while the landed hangar is dark, then a very
  bright strike; layers of wooden waves sliding back and forth behind them; a painted
  backdrop on the back wall (grey, foggy Atlantic coast, one island, barely visible).

## What exists vs what this needs (conductor's reading — INFERRED unless marked)

| Beat | Exists | Needs |
|---|---|---|
| 1 arrive, strike | Rise re-timed, cast reveal, pit + deck, strike — all applied and saved 1 Oct (measured, markers in CONDUCTOR_START_PROMPT) | Gary's judgement on strike brightness |
| 2–4 figures, clam on pedestal, waves | Six Shore figures + `Clam_with_Pearl` in the level (measured: actor list, run 123004) | Re-blocking to mid-box (~10 m); a pedestal (not checked whether one exists); wave rows + backdrop (Wings and Textures); static cameras (Gary) |
| 4–5, 8–9 agitation builds, then calms back to each figure's animation start | Figures have swaying animation (seen in PIE) | An agitation layer/ramp over ~2 min and a return — animation work, owner TBD |
| 5–7 clam opens slowly, close-up, pearl glows | `LS_Clams` clam animation (Gary: stays) | Timing to the ~2 min mark; pearl glow; the song (Cameron) |
| 10 defocus with narration | — | Focus key on the static camera |
| 11–12 pearl rises to dangle at camera centre; float out with it; it drops away; go to curtain | — | A pearl move keyed to the camera; the "float out" is a camera move — **check against the rule that camera moves are a score the live GO1 must be able to follow**; the exit to the curtain / boy-cat interaction |

## Blocking rulings (Gary, 1 Oct ~12:50)

- Crowd: a **loose ring around the clam, thinner on the camera side** so the wide sees the
  clam between the figures.
- Pedestal: the existing one, now labelled **`Clam_Pedastal`** (Gary renamed it; level
  saved 12:54:14). CORRECTED after probe 125725: `Clam_with_Pearl_Clam_with_Pearl_0` still
  exists (the static clam on top, beside the skeletal `source_Anim` clam), so the renamed
  actor was **`tg0pfjxda_tier_0`** (INFERRED: it was a reveal target and is no longer found).
  **TRAP:** `s3_cast_reveal_apply.py:46` and `s3_pit_deck_apply.py:48` still list
  `tg0pfjxda_tier_0`, and the cast-reveal record is keyed by it. A revert of either will fail its
  label lookup (INFERRED, not tested: both tools resolve targets by exact label and fail on
  a missing one, so it should fail closed rather than mis-target). Left as is on purpose: editing
  the label would desync the record. Map the label explicitly if a revert is ever needed.

## Landed box and placement (1 Oct ~13:10)

- Measured/inferred by probe 130916 (rest-pose check 0.000 cm over 56 actors, so the
  composition method is verified; landed values themselves are composed, i.e. inferred):
  landed interior is **60 m deep (dock x 500..6500), 20 m wide (y ±1000)**, floor top z −5,
  **roof underside 28.8 m, lattice ~10.6–11.3 m** — the roof is 17.5 m above the lattice,
  so in dim light only the lattice reads as a ceiling (Gary's "just the rig ceiling").
- The "right up close" view Gary saw was `LS_Clams` ClamCam1, 2.8 m from the cast (measured
  125725); the arrival camera stops ~23 m from the cast.
- **Gary: the pedestal goes to the middle of the landed floor, 35 m from the arrival point**
  (dock (3500, 0)). Ring around it, gap toward camera. Spec:
  `Saved/CodexConductor/specs/S3_DIORAMA_MOVE.md`.
- Beat markers: placeholder timings approved (table in the conductor session; 0:00, 0:15,
  0:40, 1:00, 2:00, 2:05, 2:25, 2:55, 3:15, 3:30, 3:50, 4:05, end 4:20). Structure per Look &
  camera: markers on LS_DevScene_03's ROOT; all cameras ROOT cuts; never use the label
  `InfinityStage.HiddenChangeover`. Order: extend to 260 s → S3 Wide spawnable (Entry pose)
  [95, end−hold) + deactivate both ClamCam1 cuts → `rematch_only`. Hole: scrubs landing on
  frames 81–94 may claim the retired root ClamCam1 (IsActive unchecked, declaration-proven) —
  2-line patch for the next build window.

## BUILT, 1 Oct ~15:50 (all measured, markers read back from the log, census clean)

- Diorama: `S3_DIORAMA_DONE run=133043` (pedestal at dock (3500,0), ring r 260/320 cm, gap to camera).
- Scene 3 length 6240 frames = 260 s (extend 13:46; SavedMasterMatchesShow Success).
- Beats: `S3_BEATS_DONE run=150947` — 12 root markers `S3 B01..B12`, spawnable `S3 Wide`
  (copied from the Entry Handoff camera) cut [95,6216], nested LS_Clams ClamCam1 cut DEACTIVATED.
- Root ClamCam1 cut REMOVED (binding kept): `S3_CLAMCUT_DONE run=154705 finished` — deactivating
  was not enough, the builder ignores IsActive and the rematch refused with gap [81,95].
- Rematch: Entry [0,95], Exit [6216,6240] copied from S3 Wide; SavedMasterMatchesShow and
  SceneCutBindingsResolve both Success.
- Backups: PreS3Beats-20261001-1509, PreS3RemoveClamCut-20261001-1543,
  PreSceneExtend-LS_DevScene_03-20261001-154745.
- INFERRED, not measured: Sequencer playback honours the nested ClamCam1 cut being inactive
  (FindSceneCameraCut reads root cuts only, so the transport never sees it). Check in PIE.
- Next for Gary: author the static cameras as ROOT cuts in LS_DevScene_03 (never nested).

## Waves and backdrop PLACED, 1 Oct ~19:11 (measured, markers read back; census clean)
- Import: `S3_FLATS_IMPORT_DONE run=190842 finished` (verify pass, no failures). 41 new assets
  under `/Game/Scenes/Wings/FlatV3/Scene3/` (7 meshes, 21 textures, MIs). Timber/Edge slots use
  `M_Wing_CanvasEdge_Master` TEMPORARILY (until Wing materiality's V3 masters exist).
- Placement: `S3_FLATS_PLACE_DONE run=191151`, backup `PreS3FlatsPlace-20261001-1911`.
  Waves `S3 Wave Row{1,2,3} {A,B}` on `S3 Hangar Root` at landed dock x 4200/5000/5800;
  `S3 Backdrop` on `S3 Hangar Far Wall`, landed dock (6497,0,-5). UV0 read back u->right,
  v down, normal -X (V-flip fixed by W&T's re-export). Revert: s3_flats_place revert mode.
- NOT YET: Gary's visual check in PIE (sky up, cottages right); the wave slides (keys);
  Gary's lighting (the white strike floods the side walls; NOT velvet — it's daylight).

## Scene 3 production priorities (Gary, 1 Oct evening — "wings is only one moment")
1. **Execute the shot list for the shore people** (the 12 beats).
2. **Skin tone** a bit more Mediterranean. (The cast are MetaHumans, `Content/Metahuman/ShoreCast_20260910`: a skin setting per figure.)
3. **Duplicate some figures** for a bigger huddle. (Each extra MetaHuman costs frame time — consider cheaper background figures.)
4. **Light the scene effectively** (Gary, with the landed preview).
5. **Make the clam beats happen** (opening at ~2:00, close-up, glow).
6. **The pearl**: the clam is Fab "Clam with Pearl V2" (skeletal `source_Anim` + static). Whether its pearl can rise
   separately (a bone, or a separate mesh) is UNCLEAR — find or make a pearl for beats 11–12.
7. **LIVE PERFORMER: when the clam opens, it is a live performer who sings the song.** Cueing this scene needs
   extra attention — the song's length is live, so the timeline can't simply run on fixed seconds through beats 5–9.
8. **Side walls: stained hand prints**, as if people have quietly, horrifically been trying to get out. (Also
   answers the walls-flooding problem through art rather than black velvet — it's daylight.)
- **Gary's answers (1 Oct evening):** the song is a **live HOLD**: the timeline holds at beat 5 (clam opens) until
  an operator cue starts the song section, holds again at the song's end, and the operator releases beats 8–12.
  **Shot list:** Codex drafts one static camera per beat as ROOT cuts at the markers; Gary adjusts in the viewport.
  **Huddle:** ~12 (6 + 6 duplicates, offset animation starts, varied skin; measure frame cost first).
  **Hand prints:** Wings and Textures paint the art (offline); applied to the S3 inner side walls.
- **Hand prints, W&T plan:** DBuffer DECALS from one atlas + a seeded placement table (≈150–250 per wall,
  shipped as JSON data; spawner reads it). **Gary to choose the art source (morning):** Fuser job
  `FuserQueue/24_S03_hand_prints_atlas` (old dried grime, not blood), or — W&T's preference — Gary's own hands
  pressed in thinned umber/dirt on paper, photographed.
- **THE SONG VAMP (Gary, 1 Oct evening):** while waiting on the live singer, "camera has only focus sharp on
  clam, everything else out and soft, lighting dims around, camera keeps rotating around clam until next."
  → A VAMP, not a freeze (a transport hold stops the whole Master: figures/waves would freeze — declaration-
  proven, one root player). Design: `InfinityStage.VampStart` / `InfinityStage.VampEnd` markers; playback loops
  that region until RIGHT, then continues at the next seam. Content keyed to loop seamlessly: orbit = exactly
  360° per loop, shallow DOF focused on the clam, lights dimmed and constant inside the loop. Figures' sway
  restarts per loop (soft, out of focus — check). **Camera = cat:** an orbit is a score the GO1 must walk —
  radius/speed must be performable (memory: puss-camera-is-the-cat).
- **Transport facts (Codex investigation, 1 Oct, file:line in Saved/CodexRuns/live_hold_investigation.log):**
  no mid-Scene hold exists; only `InfinityStage.HiddenChangeover` is read; Scene 3 is DeclaredUnpausable
  (12 Sep export) so manual pause AND fast-forward are refused there in performance mode; the C++ patch goes
  in the same held transport patch as hold-RIGHT fast-forward (next build window).

## Probe findings, 1 Oct ~20:55 (S3_CAST_PEARL_PROBE run=205414, read-only, census clean)
- **Pearl:** the Fab clam is ONE section / ONE material slot (static and skeletal); skeleton has two branches
  (`Clam_with_Pearl`, `Clam_with_Pearl_002`, likely the shell halves); skin weights unreadable in 5.8 Python.
  → Make a SEPARATE pearl (sphere + pearlescent material) for beats 11–12. Gary: size/look.
- **Skin tone:** baked MetaHuman skin (`MI_Body_Baked_VT`, `MI_Face_Skin_Baked_*_VT`); only micro-skin params
  exposed (cavity spec 0.6, normal 0.7, tiling 70/44) — no tone/melanin control. → Re-bake in MetaHuman Creator
  (Gary's tool), or a tint layer in a COPY of the skin material. Never edit the shared master.
- **Frame cost:** per figure 3 skeletal meshes + 6 grooms + head cloth; triangle totals unreadable. Inferred:
  grooms dominate; duplicates could drop grooms (head cloth covers hair). Measure before adding 6.
- **Landed preview tested in the editor** (runs 204110–204131): UP exact (0.000 cm), save-check refuses while
  up, DOWN exact; the identical level was re-saved after (CONDUCTOR_LEVEL_RESAVED 204517, backup
  PreLevelResave-20261001-2042). Use: UP → light → DOWN → save-check → save level.
