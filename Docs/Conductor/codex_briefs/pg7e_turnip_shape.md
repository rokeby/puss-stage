# PG7e — Turnip shape (offline, small)

Read `_house_rules.md`. Offline only. Do not edit `Saved/CodexConductor/animated_gobo.py`. Another job (PG7d) is
changing the PAGE lettering in `props.py` at the same time: touch only the turnip geometry/look values and the turnip
demo, so the two merge cleanly.

## Gary, 9 Oct (about the turnip; he said "pumpkin")
"[It] has gotten into a worse shape. I did want it rotund, as in somewhat round in the fat bit, but it still needs its
distinctive pointed end and to be slightly longer than it is wide with a small shrubby top like you have."

The current turnip (`props.py` `_turnip`, master HEAD 56c13b69, see `props_sheet.png`) is wider than tall with only a
stub of a root — wrong.

## Build
- Classic turnip silhouette: a round, full upper bulb (the "fat bit", circular-ish shoulders), narrowing smoothly into a
  long, distinctly POINTED tap-root (a tapering tail, slightly curved, ending in a fine point). Overall height (bulb +
  tail, excluding leaves) ~1.25-1.4 x the bulb's width — "slightly longer than it is wide".
- Keep the small shrubby/spiky top as it is now (short leaves, 3-5 points).
- Keep 2 curved tapered slit lines following the bulb's roundness, and the bite notches (scalloped tooth marks) on the
  bulb edge for bites 1-3 (bites never cut into the tail).
- Look values in `LOOK["turnip"]`: bulb_width, total_height_ratio, tail_curve, leaf_height.

## Harness (+/-)
height/width (bulb+tail, no leaves) in [1.25, 1.45] (+; -: the current wide shape fails); the tail ends in a point (its
last 10 % is narrower than 15 % of the bulb width) (+); bite area loss strictly increasing (+); all existing checks pass.

## Deliver (rule 8)
Updated props.py (turnip only), props_sheet.png, turnip template + SVG, turnip demo (atlas, manifest, contact, GIF < 4 MB,
frame strip), harness counts. Commit or file list.
