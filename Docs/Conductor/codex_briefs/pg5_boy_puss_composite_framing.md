# PG5 — Boy + Puss composite framing, Puss stretch pose, curtain-like preview (offline)

Read `_house_rules.md`. Offline only. Do not edit `Saved/CodexConductor/animated_gobo.py`.

## Gary, 9 Oct (his words, summarised closely)
"Framing should be a bit smaller and to the left. Quite a bit smaller actually because ... Puss is a cat. He might be
a big cat, but he can at most come to halfway up the boy. ... we don't need to show Puss's whole body ... just show Puss
in the lower third of the screen on the right. But we should still ... see most of the boy ... with his knees cut off
... and Puss looking up at him or perhaps sometimes doing a stretch." Blur: "let's go with blur 0.25". He also said
the current previews are not "a very good representation of the blur as if rendered".

## What the frame is (measured / declaration-proven facts)
- The visible area is the 1.88:1 lit rectangle: border BorderAspect 1.88 with Scale 0.7071 crops each SQUARE atlas cell
  to its middle 1/1.88 band (animated_gobo.py CODE_BORDER; `Tools/ShadowGobo/gobo_twin.py`). Compose for that band.
- Boy faces right (left of frame), Puss faces left (right of frame) (`boy_rig.py`, `cat_rig.py` headers).
- Current boy clip window: square, centre (540,560), size 1450 world units (`boy_rig.render_clip`) = head-to-chest.

## Build
1. A composite clip renderer (extend `Puppets/clip_render.py`): one clip with BOTH puppets drawn into each cell, each
   with its own world placement (offset, scale) and its own key list; the cell is a product of transmissions of all
   parts of both puppets (card overlap rule). Keep holds/moves/easing/IK/quantisation/de-dup exactly as PG2.
2. Framing (look values in plain dicts; propose, Gary approves from the preview):
   - boy: visible from the top of his head down to just ABOVE the knees (knees cut by the band's lower edge); head top
     ~8 % below the band top; boy's centre at ~30 % of the band width; this is "quite a bit smaller" than now (~0.6x
     of the current boy-on-screen height; report the factor);
   - Puss: lower right third, centre ~75 % of the band width, body cut by the band bottom where needed, head top at
     most halfway up the visible boy; scale Puss so a sitting Puss's head reaches ~45 % of the boy's visible height.
3. New Puss pose `stretch` (classic cat stretch: front legs forward and low, rump up, tail up, chin forward), reading
   in silhouette by negative space; plus use `sit_look_up` ("Puss looking up at him").
4. Demo clip `clip_boy_puss_rub/`: the boy "rubbing eyes" beats (as `rubbing_eyes_clip`, real-time moves) with Puss
   `sit_upright` -> `sit_look_up` (when the boy starts to whimper) -> holds -> `stretch` near the end -> `sit_look_up`.
   SDF at 8192 (`pack_rig_flipbook.py --sdf`, BlurUV 0 is written by the packer). Report cells/grid/cell px and the
   minimum feature widths (rod, narrowest slit) — the boy is smaller now, so check the 2 px floor and propose fixes
   (thicker rods/slits as look args) if it fails.
5. A better "as rendered" preview (`gobo_twin.py --curtain`): project onto a pleated curtain look — vertical pleats as
   a periodic brightness/normal shading (period and depth args), a soft warm spot falloff, slight haze, at 1920 px
   wide, so Gary can judge blur like the UE stills (compare `Saved/CodexConductor/Captures/GOBOREVIEW-20261008-222925-boy005b/f290_mouth.png`
   for the real look). Render the demo with Defocus 0.25 plus three stills at Defocus 0.15/0.25/0.35.

## Harness (+/-)
Composite cell = product of both puppets (+: an overlap stays black; -: drawing Puss after the boy without the product
punches holes); boy knees below the band, head inside (+, measured from the render); Puss head top <= halfway up the
boy (+; -: a mis-scaled Puss fails); stretch pose reads (one connected silhouette + legs separated from the body by
light, measured); de-dup still works with two puppets (a hold = 1 cell).

## Deliver (rule 8)
Paths, commit (or file list), run order, harness, budget table, preview paths, questions for Gary.
