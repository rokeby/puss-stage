# PG7b — Shadow props: revision after review (offline)

Read `_house_rules.md`, `pg7_shadow_props.md` (incl. its two Gary addenda). Start from the previous run's uncommitted
files in `C:\Users\Administrator\.codex\worktrees\0c3d\PussStage\Tools\ShadowGobo\Puppets\` (`props.py`,
`test_props_offline.py`, the boy/cat anchor additions in `boy_rig.py` / `cat_rig.py`): copy them in and revise.
Your base HEAD now has the CURRENT framing on master (`build_boy_puss_composite.py`: Puss = 0.5625 of the visible boy,
boy cut above the knees, `BOY_KNEE_SOURCE_Y = 1250`) — render every demo with it (the previous run used the old 0.45).

## Review of PG7 (by eye, from props_sheet.png and frame strips of the curtain GIFs)
1. **Bucket FAILS.** In `clip_prop_bucket` the pail sits on top of the boy's head for the whole clip and reads as a hat;
   no pour or splash is visible because water over the head/hair is black on black. Gary: "no one holds the bucket, it
   can emerge on a stick and pour onto the boy and animate as different cutouts of splash". Required: the bucket ENTERS
   on its own visible stick from the upper right of the band (moves in, real time), stops ABOVE and IN FRONT of the boy's
   face with clear light between pail and head, tips, and the pour (a wavy ribbon) falls through the LIGHT in front of
   his face onto his head/face; splash = 3-5 replacement cut-out splash shapes that burst OUTWARD beyond his silhouette
   (so they read against light), then drips; the bucket rights itself and exits on its stick. Harness: during the pour,
   the water silhouette must cover >= N light pixels that are outside the boy's silhouette (measure on the cell), and a
   bucket overlapping the head while pouring must fail (-).
2. **Turnip does not read** (spiky pinecone blob, tiny root). Draw a real turnip: a round, slightly flattened bulb
   (wider than tall), a thin tapering tap-root tail, and 3-4 long separate leaf blades (stalks) rising from the top with
   light between them; a cut band/ring slit where the purple shoulder meets the white root. Bites remove scalloped
   tooth-mark notches from the bulb's edge.
3. **Pearl highlight** is an angular "P" cut: make it a smooth crescent gleam (tapered slit following the sphere's upper
   left edge) plus a small star or round punch; the disc must stay perfectly round.
4. **Style:** props are blockier than the boy and Puss. Give each 1-3 tapered knife cuts in the same woodcut language
   (bucket hoops as tapered slits, wood-grain nicks; page edge torn irregular; crown with a band slit; boots with cuff
   fold slit and a stitched-sole line).
5. **Boots:** keep the behaviour (fall one by one, bounce, land upright in a row in front of Puss) and Gary's size rule
   ("little, the size for puss's shadow's feet"); give them a cavalier boot silhouette (flared cuff, heel, pointed toe)
   rather than rectangles.
6. Keep: page, crown behaviour; budgets; SDF 8192; BlurUV 0; GIF < 4 MB; feature floors >= 2 px.

## Deliver (rule 8)
Same as PG7 plus: frame strips (6 evenly spaced frames per demo) as PNGs next to each GIF, so the reviewer can see the
action without playing GIFs; the pour-visibility measurement per frame for the bucket.
