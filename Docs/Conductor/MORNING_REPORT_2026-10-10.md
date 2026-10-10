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
- **Shadow-cat build**: v2 failed to compile (header include order), so it was reverted and rebuilt clean. Job 154 is fixing it (v3).

**Machine:** the editor is closed after a clean build. Metamall has the build window, then its ~3 h slot.

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
