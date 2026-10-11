# PG8 — First pass of the five interaction shadow clips (+ the boy's hinged mouth) (offline)

Read `_house_rules.md` (all rules; effort medium). Offline only: no Unreal, no MCP, no Blender. Do not edit
`Saved/CodexConductor/animated_gobo.py`.

## Sources of truth
- Beats + timings: `Docs/Conductor/SHADOW_SHOTLIST_INTERACTIONS_2026-10-11.md`, section "Timed filming plan (revised
  11 Oct, Gary)" — the beat table (natural pace, ~40-51 s each, 1.5 s still plates at both ends).
- Gary 11 Oct (gobo session): "there's no sound from cameron here in a music sense - just room tone, so we can just
  time them to what feels natural for now and edit after we have the first pass". Use the table as-is; retiming later =
  moving keys.
- Gary 11 Oct decisions: use the DIGITAL puppets (not filming); I3 prop = **pearl only** (no clam); I5 = **crown, then
  boots** (the crown falls onto the boy at "Now you are king", then Puss's boots beats).
- Rigs/props/pipeline (all on master): `Tools/ShadowGobo/Puppets/boy_rig.py`, `cat_rig.py`, `props.py` (bucket on a stick,
  carved-name scroll, turnip with bites, pearl, crown, baby-bootie boots), `clip_render.py` (holds + real-time 25 fps
  eased moves, point-IK, quantised holds, reverse reuse, max_cells), `build_boy_puss_composite.py` (framing: boy left cut
  above the knees, Puss lower right at 0.5625 of the visible boy), `pack_rig_flipbook.py --sdf` (8192, BlurUV 0),
  `gobo_twin.py --curtain` (preview). Prop demos in `prop_demos/` show each prop's motion.

## Part A — the boy's hinged mouth (Gary 11 Oct)
"the boy's mouth should have a hinge, the profile of his mouth closed should remain the same but he should be able to
open it for the wailing parts". Add a lower-jaw part to `boy_rig.py` (pivot near the jaw hinge below the ear) with a
`jaw` pose angle: jaw 0 must reproduce the CURRENT closed silhouette exactly (harness: pixel-identical render of the head
at jaw 0 vs the pre-change render, per mouth state); opening rotates the lower lip/chin down and reveals a dark open
mouth (light shows through the gap only where it reads as an open mouth in profile). Mouth faces (pout/blubber/
surprised/sad) still apply to the closed profile; wailing = blubber/sad + jaw open 10-25 deg with a small jaw wobble.

## Part B — five interaction clips (first pass)
For each of I1-I5, build one composite clip (boy + Puss + that interaction's prop) following the beat table, with the
whimper beat at the end (use the jaw for the wails: small whimpers I1/I2/I4, BIG snivelling I3, mournful sag I5):
- I1 Washing the Boy: boy hunched -> **bucket emerges on its stick and pours onto him** (fountain-drained beat) -> Puss
  licks/washes the boy (head bobs against the boy's head/shoulders) -> boy straightens -> whimper.
- I2 Turnips: Puss brings the turnip -> boy grabs -> eats it all (bites) -> sad stillness, slow head down -> whimper.
- I3 Forgets His Name: Puss sits and sings (raised head, jaw opening rhythmically) and gives the **pearl** -> boy
  sways -> tongue lolls (simple tongue cut-out shape through the open jaw) -> coughs (sharp jerks) -> BIG whimper.
- I4 Gets a Name: Puss brings the scroll (carved "Cagliuso") -> boy holds it up -> turns it over -> pause, lowers ->
  whimper.
- I5 Becomes King: **crown falls onto the boy** ("Now you are king") -> boots pop in -> Puss admires -> pulls them on
  (comic struggle) -> struts -> mournful whimper.
Each: atlas (8192 SDF) + manifest with schedule, cell budget table, curtain GIF < 4 MB, a 6-frame strip per beat, and the
per-beat timing table actually used. Budget: aim <= 196 cells per interaction (744 px cells); use holds, reverse reuse
and max_cells; if an interaction still exceeds, split into two atlases (A/B halves) and report how (do not shrink below
the 2 px feature floor).

## Traps (house rule 9 + puppet lessons)
- Black-on-black vanishes: every gesture reads through negative space (licking, handing over the pearl/scroll, crown
  above the head before landing).
- Do not bake handheld wobble (UE adds it live).
- Quantise holds so they de-dup; real-time moves at 25 fps with easing.
- Report every claim tiered (rule 6). Commit is blocked in your sandbox: list files.

## Harness (+/-)
Part A jaw-0 identity (+) and a moved-jaw-0 control (-); per interaction: beats in order with the table's durations
(+/- 1 frame), whimper last, prop present in its beats, cells <= cap or split reported, all existing harnesses still pass.

## Deliver (rule 8)
Paths, file list, run order, harness counts, per-interaction budget + timing tables, strips, open questions for Gary.
