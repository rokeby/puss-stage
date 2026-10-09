# PG1 — Puss the tomcat: jointed cut-paper shadow puppet (offline)

Owner of review: "Gobo shadow animation tool" session. Read `_house_rules.md` first (rules 1, 2, 5, 6, 7, 8 apply;
no Unreal, no Blender). Gary 8 Oct: "Puss is a cat, a big tomcat. He can have various sitting poses." The show is
simulated shadow puppetry: very low frame-rate, joints move only when needed; otherwise the figure is held still and
only a hand's wobble moves it (that wobble is added later in UE, NOT baked by you).

## Reference implementation — copy its architecture exactly
- `Tools/ShadowGobo/Puppets/puppet_cut.py`: `chain()` (cubic Bezier outlines), `slit()` (tapered knife cut),
  `punch()` (round hole).
- `Tools/ShadowGobo/Puppets/boy_rig.py`: the boy. Parts = outline + their own cuts in LOCAL coords with a pivot;
  `pose_parts()` composes transforms; `render_pose()` multiplies per-part transmissions (a cut only lets light through
  where no other part covers it — like real card); `projected()` makes the screen preview; replacement face parts
  (eyes/brows/mouth dicts) swap per pose; rods are drawn as thin lines (they are part of the shadow).
- Look at `Tools/ShadowGobo/Puppets/rig_v1/boy_poses.png` and `boy_expressions.png` for the style: solid black,
  few cuts, each a clean tapered sliver, woodcut-like. The boy faces RIGHT; **Puss faces LEFT** (they face each
  other).

## Build `Tools/ShadowGobo/Puppets/cat_rig.py`
1. A big, heavy tomcat in strict side profile: broad tomcat jowls/cheek ruff, thick neck, one notched (torn) ear,
   a scar slit, a heavy chest, sitting haunch, thick tail. Whiskers as 3–4 thin black strokes OUTSIDE the outline
   (cut-paper puppets use thin wire/card whiskers).
2. Parts and joints: body (root, haunch + chest + hind leg as one piece), head (neck pivot), near front leg
   (shoulder pivot + wrist pivot: the paw can lift), tail in 3 segments (base, mid, tip pivots) so it can curl and
   flick, optional lower jaw (hinge) for a meow.
3. Replacement face parts: eyes {open (almond with a vertical slit pupil left as a black bar inside the cut),
   half (heavy lid), shut (contented curve), wide}, ears {up, flat (pinned back), one-swivelled}, mouth {closed,
   meow (jaw open, two fang cut-outs)}.
4. Named poses (args with defaults; Gary picks): `sit_upright` (tail wrapped round the front paws), `sit_proud`
   (chest out, chin up — for the King), `loaf_hunched`, `sit_look_up`, `paw_lick` (paw raised to the mouth),
   `washing` (head turned down, paw at the face), `meow` (jaw open, ears up), `tail_flick` (two-frame tail move).
5. Outputs (to an out dir given on the command line): `cat_poses.png` (all poses on the projected preview),
   `cat_faces.png` (expression set close-up), `cat_<pose>.svg` cut templates (evenodd holes), and a short stepped
   demo GIF at 8 fps WITHOUT baked wobble (sit_upright → look_up → meow → washing → sit_upright, 2–4 in-between
   frames per move, holds as repeated identical frames).
6. Keep every look value (angles, sizes, pose table) in plain dicts at the top so Gary can retune.

## Traps (why the obvious version fails)
- **Black-on-black is invisible.** A paw over the face or a tail across the body vanishes in silhouette. Every
  gesture must read through NEGATIVE SPACE: the paw must stick out past the face profile, the tail must curl into
  empty space or cross a gap. The boy needed three attempts and an IK with the elbow out front (`boy_rig.ik`,
  `HEAD_IN_HANDS`) before "head in hands" read. Check every pose's silhouette for this and say which ones read.
- **Cute cartoon/anime reads wrong.** Woodcut-crude, heavy, a bit grotesque like the old man reference
  (described in `boy_rig.py` header), not kawaii.
- Cuts must not reach an outline edge (they would sever the card); keep ≥ 6 units of card around every cut.
- Product of transmissions, not "draw cuts last over everything" — the latter punches holes through parts in front.

## Harness (`Tools/ShadowGobo/Puppets/test_cat_rig_offline.py`), negative AND positive controls
- every named pose renders, deterministic (two renders byte-identical);
- the silhouette of each pose is one connected black component plus whisker/rod strokes (count components);
- every cut lies inside its own part's outline with the ≥ 6-unit margin (−control: a deliberately misplaced cut
  must fail);
- overlap rule: a cut covered by another part stays black (+control) and a cut with nothing in front shows light;
- facing: the nose is the left-most point of the head part in `sit_upright` (−control: a mirrored head fails).
Report counts.

## Deliver (rule 8)
Paths, worktree commit hash, how to run, harness counts, which poses read in silhouette and which don't
(measured from your renders, by eye — say so), open questions for Gary. Apply nothing.
