# PG7 — Shadow-puppet props: library + animated demos (offline)

Read `_house_rules.md`. Offline only (Python/numpy/PIL/scipy). Do not edit `Saved/CodexConductor/animated_gobo.py`.

## Gary, 9 Oct (his list, verbatim)
"other things we need in shadow form - a bucket of water pouring onto the boy / a page from a book drifting in the air,
falling / a turnip that can be eaten by the boy Bite BIte BIte / A pearl (a shiny sphere) given by puss to the boy /
a little crown for the boy that appears and falls on his head / Four little boots for puss that fall out of th air
above the frame and onto the ground in front of him"

These map to the Interactions (`Docs/Conductor/SHADOW_PUPPET_PLAN_I1_I5.md`): bucket = I1 washing; turnip = I2;
pearl = I3; page = I4 ("Cagliuso"); crown = I5; boots = Puss in Boots (place per the plan or propose).

## Style and pipeline (reference, all on master)
- Cut-paper woodcut style exactly like the boy and Puss: solid black card, few tapered knife cuts / round punches,
  reads by NEGATIVE SPACE (`Tools/ShadowGobo/Puppets/puppet_cut.py`, `boy_rig.py`, `cat_rig.py`; pose sheets in
  `rig_v1/`, `cat_v3/`; composite preview `clip_boy_puss_rub/curtain_still_defocus025.png`).
- Composite renderer `Puppets/clip_render.py` + `build_boy_puss_composite.py`: cells = product of transmissions of all
  parts; holds = 1 cell, moves at 25 fps real time with easing; SDF packing at 8192 (`pack_rig_flipbook.py --sdf`,
  BlurUV 0 written); framing = the 1.88 band (boy left, cut above the knees; Puss lower right, ~56 % of the boy's
  visible height); stepped schedule -> CONSTANT keys in UE.
- Cell budget matters: ~200 cells per Interaction atlas at 8192 (`SHADOW_PUPPET_PLAN_I1_I5.md`), min feature 2 px.

## Build
1. `Puppets/props.py`: a prop library. Each prop = outline + cuts in local coords, a pivot, size relative to the boy,
   and an ATTACH mode: world (on its own rod, like a real shadow prop), or attached to a puppet anchor — boy hand
   (`*_hand_on_head` IK targets / forearm end), boy head top, Puss mouth, Puss front paw. Expose anchors from the rigs
   without changing their look.
2. Props and their motions (all deterministic, 25 fps, eased; look values in plain dicts for Gary):
   - **bucket of water** (I1): wooden pail with hoops (cut slits) and a handle, on a rod, tips above the boy; the
     water is a pouring ribbon + droplets made of cut-paper shapes (replacement sequence: stream lengthens, hits his
     head, splash shapes), finishing with drips. Shadow water should read as water: wavy ribbon edges, droplet cuts.
   - **page** (I4): a book page with a torn edge and a few cut "text lines"; drifts down like a falling leaf:
     side-to-side pendulum sway, tilt, and a foreshortening flip (scale x) as it turns, landing near the boy's hands;
     a variant with a large cut-out "Cagliuso" legible when held flat.
   - **turnip** (I2): bulbous root, tapering tail, 3-4 leaf blades; held in the boy's hand at his mouth; "Bite Bite
     Bite": 4 states (whole, 1, 2, 3 bites) as replacement outlines with bite-shaped notches (scalloped tooth marks),
     each bite a quick head-forward snap move of the boy (use his neck/IK), crumbs as 2-3 small falling punches.
   - **pearl** (I3): a shiny sphere: a disc with a crescent highlight CUT through it (light passes = shine) and a
     tiny star punch; carried in Puss's mouth (or paw), offered across the centre, transferred into the boy's hand.
   - **crown** (I5): little crown, 5 points, 2-3 round jewel punches; appears above the frame (enters from above the
     band), falls with a slight tumble, lands on the boy's head with a small bounce and settles (attach on landing).
   - **four boots** (Puss in Boots): tall cavalier boots with a cuff and heel (cuff slit, sole line), fall out of the
     air from above the frame one after another, bounce, rotate, and land upright in a row on the ground in front of
     Puss (ground = band bottom region; they may be cut by the band edge).
3. Physics helper: gravity + restitution bounce + spin + settle, sampled at 25 fps, deterministic; and a leaf-drift
   helper (sway amplitude/period, tilt, flip). Quantise transforms so holds de-dup.
4. Demos (one clip each, composite with boy + Puss in the current framing, SDF 8192): `clip_prop_bucket`, `clip_prop_page`,
   `clip_prop_turnip`, `clip_prop_pearl`, `clip_prop_crown`, `clip_prop_boots`. For each: atlas + manifest (commit
   these), a contact sheet, a 960 px curtain preview GIF (`gobo_twin.py --curtain`, Defocus 0.25; keep GIFs < 4 MB),
   and the cell budget. Plus `props_sheet.png` (all props flat, with names) and SVG cut templates per prop.
5. A short report of cell counts per demo and suggestions to reduce (shorter falls, fewer drops, reuse).

## Traps
- Black-on-black vanishes: a prop over a body part is invisible; stage every prop against light (turnip held in front
  of the face profile, pearl in the gap between the two puppets, crown above the head before it lands).
- A falling object at 25 fps adds a cell per frame; keep each fall ~0.6-1.2 s and say how many cells it costs.
- Thin features: drops, rods, handle, crown points must stay >= 2 px in the cell (report minimum widths).
- Attachment must be IK-consistent: the turnip stays in the hand through every bite move; the pearl hands over without
  a jump (interpolate the anchor as a POINT).
- Product of transmissions: a cut in a prop over a puppet stays black (card overlap), as in the rigs.

## Harness (+/-)
Each prop renders as one connected silhouette (+); prop-on-body overlap stays black (+) and a cut-through bug fails
(-); fall settles exactly on its target (ground / head) within 1 unit (+) and an unsettled sim fails (-); turnip bite
outlines strictly lose area 0->3 (+); hand/turnip anchor distance stays < N units through the bite moves (+; -: a
detached prop fails); pearl handover has no anchor jump > N units per frame (+); boots end upright in a row with
spacing > their width (+); all demos de-dup holds (a hold = 1 cell).

## Deliver (rule 8)
Paths, commit or file list, run order, harness counts, per-demo cell budget and min feature widths, preview paths,
open questions for Gary (e.g. who holds the bucket; whether the page shows the name; boots size vs Puss).

## Addendum (Gary, 9 Oct, after dispatch)
"no one holds the bucket, it can emerge on a stick and pour onto the boy and animate as different cutouts of splash".
So the bucket enters on its own stick (from above or the side of the band), tips and pours onto the boy, and the
water/splash is a sequence of different splash cut-outs (replacement shapes), not a simulated fluid. Review PG7
against this.
