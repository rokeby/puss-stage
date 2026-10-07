# Morning summary — 7 Oct overnight (Conductor 4)

Gary signed off ~06:30 UTC: "if no big uncertainties then good night". Rule used overnight: apply only what is
approved AND has a clean DRY with no open look question; hold the rest here.

## Applied (saved + read back; SavedMasterMatchesShow + SceneCutBindingsResolve green after each block)
| What | Run / commit | Notes |
|---|---|---|
| P06 sunset (sun dead ahead, dark from 52 s) | P06SUN-20261007-010204 / f84b65b | C++ probe at 6 samples |
| S1 reveal v3 (strike to her lit look) | KLARAREVEAL-20261007-011535 / 36d844b | v2 reverted in-editor; S1 247.04 s; muted narration stand-in removed |
| S6 Void in the main level | KLARAVOIDS6-20261007-013108 / 4c110e4 | hangar hidden, her sun off, ends at her last cut (219.56 s), bee glimmer from 1 s; S6 Ghost Light off |
| P04 window shadows (7) + strobe cast shadows | 20261007-014208, P04STROBESHADOW-… / d574091 | |
| Puss shadow spot (8 cues, 6 rigs) | PSS-20261007-014914 | P06 cues capped before 50 s (stays dark) |
| P05 eye 90 cm | P05CH-20261007-015121 | C++ counters the cat |
| Velvet V2G (11 drapes) | VV2G-20261007-015155 | VERIFY_OK |
| P02 straighten (DOCK) + follow-ons + S1/S2 handoffs | P02STR-20261007-015540, P02FOL-…-015605 | Klara streamed actors now excluded from the route scan (would have moved 198 of hers) |
| P02 retime 180 → 47.52 s | RETIME-20261007-021031 | everything after P02 is 132.48 s earlier |
| Beam texture rollout (GSB) | P01 (7), P04 (1), P06 (5) / bb2f55a | P05 unsupported by the core |
| BP_Effect_SmokePot + BP_Effect_Motes classes | FXBP-20261007-021606 | not placed yet |
| P02 brighten (32 rows, second half) | 20261007-022814 | **no measurable effect** — see open issues |
| Girder v3 meshes imported (assets only) | GV3I-20261007-023001 | not applied to the Structures |

## HELD for Gary (DRY clean, look/ownership question open)
1. **Girders v3 at double section** — DRY GV3A-20261007-023014 clean (6 Structures). Side effects Gary hasn't seen:
   TOP lamps end up inside the new 1060–1420 cm girder band (rig_lamp_drop.py is hard-coded to 90 cm beams; needs a
   180-deep copy with a slight negative clearance = "lamps sit on the rig"); P01 portal timber rails become 80×180; grid
   top rises 135 cm (low lamps with drop > 765 cm lose their hanging line). Renders sent 7 Oct.
2. **P06 bee glints** — DRY P06BEEGLINTS-20261007-023031 apply_ready=1 (80/100/118 s). Needs the cueing stream's OK to
   add a sub-track to LS_Choreo_Passage_6 (cueing_ack), or use the master_bindings fallback (doesn't travel on rebuild).
3. **P01 note lamps** — APPLY failed EXPORT_OUTSIDE_SCOPE_CHANGED and rolled back (nothing saved). Cause UNCLEAR; the tool
   now logs P01NOTELAMPS_EXPORT_DIFF per changed item. Next: DRY, then APPLY reads its own diff if it fails again.

## Open issues
- **P02 second half is black in PIE** (luma 3 at 60 %, 0.02 at 80 %) and raising 32 lights to 800 lm / ×4 changed
  nothing [meas]. Line traces show nothing blocking the camera [meas]. So those lights do not contribute in PIE —
  candidates: strike-on-approach not firing after the straighten/retime, or the rig-pattern rows (6 Oct 22:38).
  On 6 Oct 06:37 (before both) the 70 % still was lit. Diagnose before any more P02 lighting.
- **S6 stills**: her woman's arm reads disembodied at ~20 % — her look, or MetaHuman instance overrides (forced LOD,
  face MIDs) the spawnable copy can't carry [inf].
- P03 global-fog test: no tool written yet.

## Still running / for the morning build
- Barbed wire coil + strands (import + held C++ fence patch + apply) — agent writing.
- Smoke-pot placement (P01/P03/P04) + P04 rain PIE test — agent writing.
- Meshy bulbs + lanterns import + cube swap — agent writing; Gary: do it tonight.
- Morning build: W&T mechanism sound patch a7c89c5 (no Passage would sound — MechanismSound disabled everywhere,
  TOPPLE-20261007-022206) + the fence patch when ready.
- W&T: curtain unfurl bake (offline Blender), P06 topple variant C, P06 flats import.

## Update ~06:40 UTC (after Gary's last three answers)
- Gary: girders apply tonight (lamps may overlap); bees into the Choreo; dead bulbs -> warm orange/white/pink mix, all passages.
- **Girders apply STOPPED** (GV3A-20261007-023402): Structure 02 hanging lines 35 -> 50 vs predicted [32,32]; rolled back in
  memory, Don't-Save restart, nothing saved. Predictor is off even for the before-count; agent fixing it. Meshes are imported.
- **P06 bee glints APPLIED** (P06BEEGLINTS-20261007-023505) as a sub-track in LS_Choreo_Passage_6 — **tell the cueing stream**
  (Gary's OK, they were offline).
- **Smoke pots x9 APPLIED** (FXSMOKE 20261007-023816): P03 bays 8/13/18, 3 each in P01/P04. Plume visible in P03 stills.
  BP still carries the greybox Apparatus cube.
- **P04 rain**: Rain2 RENDERS in UE5.8 (P04RAINPIE-20261007-063520, controls valid). Not placed yet (needs a placement call).
- **Barbed wire meshes imported** (BWIMP-20261007-023744); held C++ patch Scripts/patches/2026-10-07_fence_top_row_wire_and_posts.patch
  for the morning build, then barbed_apply.py.
- **P02 dark explained** [record + code]: P02 SCORE lamps strike at 650 cm with unstruck scale 0 (SetVisibility false),
  B18-19 EXTINGUISH after passing -> everything ahead in view is off. Fix in progress: strike 2500 cm + HOLD for B12+.
- W&T has the slot for P06 topple variant (6-wing domino at ~37 s + one sliding wing), end drapes P01/02/03/05 + picture ASSIGN.
- **End drapes NOT placed** (W&T DRYs PED-20261007-DRY-S1/S2/S3/S5, apply_ready=0, nothing written). Gary's look call:
  S1/S2/S5 hem hangs ~20 cm above the floor (bake hangs from z 20; lowering sinks the pile) — accept gap / sink pile /
  re-bake lower? S3 floor top is 120.5 cm vs drape support 0 — site decision. 44–46 % of the hinge opening still visible
  at release (S1–S3). Pictures ready in MI_CurtainImage_P01/02/03/05.
- **Girders v3 APPLIED** (GV3A-20261007-024125, 968afa4) after the line predictor was rebuilt to match the C++:
  lines 48→64, 35→50, 19→18, 39→46, 158→209, 57→77 exactly as predicted; extra lines are cables under TOP lamps now
  inside the deeper band (the re-hang to sit on the rig is still to do: rig_lamp_drop copy for 180-deep beams). Tests green.
- **Meshy swap HELD (Gary's calls)** — import is ready, swap DRY not run. Findings [decl]: housings are ONE BodyMesh per
  Structure (InfinityStageStructureActor.h:396-416), so lanterns can't vary per role without C++; matching old sphere
  sizes makes bulbs 2–4× real; bodies sit up to 14.3 m from their lights in P06 (6 Oct rig-pattern moves didn't carry
  them) — placing bulbs ON their lights visibly moves them; P05 would get lanterns behind 185 practicals.
  Questions: bulb size (real vs old), move bodies onto lights?, lantern per passage OK or wait for C++?
