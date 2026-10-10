# Morning report: 10 Oct 2026 (Conductor 5, overnight)

Verdicts on stills are by the conductor's eye. "Applied" means saved and read back. The full evidence is in `APPLY_PASS_REPORT_2026-10-10.md`, and the tracker is `OVERNIGHT_QUEUE_2026-10-10.md`. Stills are in `Saved/CodexConductor/ApplyPass_20261010/stills/`.

## Visually confirmed
- **S4 blackout**: P04 end, cut and S4+1 s are fully black. The 67 S4 hangar lattice lights are hidden over the P04 tail, plus a black cut fade (`01_pass7_*_black.png`).
- **Pearl 2 s fade**: the clam is empty at frame 5040 (`03_pass7_pearl_frame5040_empty.png`).
- **S3 arrival**: blackout, then the rise (`01_pass5_s3_arrival_*`).
- **S3 fabrics**:
  - Shirts and shorts in hessian brown with the weave, on all figures, crowd copies and the last NPC included.
  - The shorts' metal look removed.
  - The hessian shroud back-face fix.
  - Feet raised.
- **P05 deer curtain** (`02_pass3_p05_deer_*`).
- **P04 smoke props hidden** (all three pots; the smoke itself stays).

## Applied; please check in PIE (stills too dark, or not yet seen)
- **S2 hangar resized** around Klara's scene. From outside it looks enclosed, but the still is very dark.
- **P05**: cut to 42.04 s. The left wings are offset on local X, but **−20 cm** (the tool chose the direction that removes the overlap; minimum gap 0.15 cm).
- **P06**: Walking6 at 125 s plus the full retime (dusk not yet seen).
- **P02**:
  - Top wings flipped, practicals removed, 4 beams, lighting = P01.
  - Car radius 10000.
  - **The floor = P01 copy SAVED, but its own post-save check failed**: job 147 verifies it or reverts it.
- **S5 girders**.
- **Nap camera** at your values.
- **Interactions**: camera seams (95), I1 polish (90), curtain-before-shadow on I1 and I3 (89).

## Concerns
- **P02 is a wall of milky haze** in PIE at 30% and 60% of the passage (`Saved/CodexConductor/PassageStills/PSTILLS-P02-20261010-070928-*`). Inferred: tonight's P02 lighting = P01 (beams + atmosphere). It is also over the perf budget (p95 40.7 ms vs 33.4 ms). Job 125 has trim options. **Your call: keep, trim or revert.**
- Tonight's early stills were taken without sequence evaluation, so the method was fixed mid-night. Trust only stills dated pass 7 onwards.

## Later in the night (passes 8–12)

**Done:**
- **P04 smoke props**: all three pots hidden (the smoke stays).
- **P02 floor**: the copy landed 1,000 m too low, so it was **reverted from the backup**. P02 has its original floor back. Job 152 fixed the maths (33/0); it is ready for the next slot.

**Not done**, each with a fixed tool ready for the next slot:
- **Shadow radii**: the survey found 310 candidates; APPLY refused pre-mutation. Nothing changed.
- **I2/I3 back wall (job 144)**: an existing visibility-track conflict on I2; nothing applied.
- **3D stage front**: meshes and textures imported; the **Arch** material instance is saved; the other five pieces and the placement are not done.
- **Chandelier chain** and **Ending 101**: not run.
- **Fringe**: held after two failures.
- **Shadow-cat build**: v2 and v3 both failed to compile, so both were reverted and the editor rebuilt clean. It needs a compile-fix round with Gary around.

**Machine (end of night):**
- Metamall's build + slot are done (slot ended 04:37).
- Then **the GPU device was REMOVED** (`DXGI_ERROR_DEVICE_REMOVED`) during pass 14, before any mutation. The editor was hung and is now CLOSED, with nothing saved.
- Last time (8 Oct) a GPU loss needed a **REBOOT**. **Please reboot before opening Unreal.** If it happens again, the 8 Oct runbook points at the volumetric fog plus heavy relights: P02's new lighting is the prime suspect (haze + over budget).

**Ready for the next slot, in order:**
1. Shadow radii: the APPLY refusal comes from a helper's import side effect, not the args, so it needs a small fix.
2. The 3D stage front: resume at MATERIAL `wall` (Arch is done), then gilt, crest, column, cat, PLACE, then the wide opening still. After that, job 87 is re-planned against the new stage.
3. The P75 chandelier chain.
4. Ending 101.
5. A P06 dusk still.
6. The P02 floor (job 156: yawed curved-route segments, and its DRY now runs the APPLY check).
7. I2/I3 back wall (job 144): an I2 visibility-track conflict, which needs your eye.
8. Fringe (held).
9. Shadow-cat build: v2/v3 compile errors; needs a fix round.

## Still in the queue (as of writing)
- **Pass 9:**
  - the 3D stage front (all six pieces, Dusty, Iron3, materials, placement, wide still)
  - fringe
  - shadow radii with the perf auto-revert
  - chandelier chain
  - ending
  - a P06 dusk still
- **Job 144**: I2/I3 at the hangar back wall (front spot, framing matched to I1/I4/I5 at 714 cm, I3 reuses a gobo). It is waiting on job 147's label fix.
- **Job 87** (opening camera, uplights, bulbs): re-plan against the new 3D stage front.
- **Build window**: shadow-cat v2. Then Metamall's build and 3 h slot.

## Waiting on you
- P02 lighting/haze (above).
- **P06 parcan + sun**: the tool (job 126) needs a PIE probe plus your pick of the parcan.
- One-time Cue Book button setup: put your passcode into `Saved/CueBook/cuebook_pass.txt` (I created it empty), restart Unreal, then **Puss > Pull Cue Book**.
- Later notes on file: S3 long unkempt hair; garment stains; girders everywhere (job 116 built); swarm (100); S6 old-lady cuts (direct them by hand first).

## Early morning (offline, no GPU)
- **Shadow-cat BUILT** (v4, commit 6fddad8a).
  - All 7 new tests pass.
  - The full headless suite: 259 Success / 4 Fail. All 4 are pre-existing and untouched by the patch:
    - CrossingSettle expects a 1.0 s settle vs tonight's 3.0 s
    - NestedSequencesFitTheirParents
    - SavedFixturePIE
    - ShadowCatPIE: the shadow cat has no direct idle/walk animation
- **Ready for the first editor slot** (job 159):
  - shadow radii (side-effect import isolated)
  - fringe (5.8-safe texture settings)
  - I2 track conflict (SAFE_SKIP default)
- **Job 160: the opening (87) re-planned** against the 3D stage front: the wide camera fits the whole front, then the move-in, uplights on the new lip, bulb scatter clear of the pieces. Preview: `DerivedAssets/P87OpeningFixes/p87_stage_front_camera_frusta.svg`. It runs after the stage front is placed.

## First slot after the reboot (approved order)

1. **The P02 lean lighting (job 161, Gary approved)**: DRY → APPLY → PIE p95 + stills; auto-REVERT if it is not better. Car 4600 cm.
2. Shadow radii (job 159 fix).
3. The 3D stage front (5 more MIs + place), then the opening (job 87 re-plan from 160), with stills.
4. The chandelier chain.
5. Ending 101.
6. The P02 floor (job 156).
7. I2/I3 back wall (SAFE_SKIP).
8. Fringe.
9. Stills: P06 dusk, S2 from outside, P05 wings.

## GPU diagnosis (10 Oct ~11:45 local)
- **Measured:** the RTX 5070 Ti on driver 610.88 is healthy at idle (33 °C, no throttle, 1.3/16 GB).
- **04:49 was a real Windows TDR**: event 4101, nvlddmkm recovered.
- **11:34 was only Unreal's 5 s GPU-timeout WARNING**, on frame 7 after launch. There was no Windows reset.
- **Inferred cause of both:** heavy first frames (distance fields, Lumen, skinning, plus the new 2M-tri Nanite stage-front pieces).
- **Lever 1**: the job 166 safe editor launcher (opt-in, resets the settings in PIE).
- **Lever 2 (GARY, LATER):** raise the Windows TDR timeout. In an Administrator PowerShell:
  - Set: `New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name TdrDelay -PropertyType DWord -Value 10 -Force`
  - Then reboot.
  - Undo: `Remove-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name TdrDelay`
  - It is a system setting, so Claude cannot change it.

## Afternoon slot (job 167, safe launcher): no GPU errors
- **Applied and verified:**
  - **3D stage front placed** (8 actors).
  - **Chandelier staging** for the opening (28 actors, 2 tracks).
  - **P02 floor = P01 copy** (4 replacements).
  - **Proscenium fringe** (3 textures, 6 MIs).
  - P02 lean lighting and shadow radii: both reverted on perf.
- **Conductor's eye on the stills:**
  - **Stage-front wide**: looks RICH; the paper proscenium plus the 3D arch/columns frame the stage, with the curtain pile in front (`03_job167_stagefront_opening_wide_pre87_revealed.png`). Codex marked it a visual fail; Gary to judge.
  - **P06 dusk**: passes.
  - **P02 floor reflection**: too dark to judge.
  - **S2 from outside** and **P05 wings**: inconclusive.
- **Not done** (stopped at their guards):
  - Job 87 (opening camera/uplights/bulbs)
  - Ending 101
  - I2/I3 back wall
  - Chandelier P06 part, candles, swing
- **Waiting:**
  - S1 job 168 (Gary to choose: shrink vs real fade vs darkness)
  - P06 parcan (job 126; Gary's pick: the body at "P06 EVT B02 BLACK F00 CAMERA")
