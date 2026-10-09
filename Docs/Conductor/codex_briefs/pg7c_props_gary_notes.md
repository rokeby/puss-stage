# PG7c — Shadow props: Gary's notes (offline)

Read `_house_rules.md`, `pg7_shadow_props.md`, `pg7b_shadow_props_revision.md`. The current reviewed props are on
master (commit 13343ffb): `Tools/ShadowGobo/Puppets/props.py` (with the review's bucket look values: stream_width,
splash_scale, stop_xy, target_xy — keep them), `prop_demos/`, `props_sheet.png`. Work from those files in your worktree.

## Gary, 9 Oct (his notes, close to verbatim)
- **Page:** "should read [the name] still cut out, but maybe in a calligraphic feeling font or shape. ... could
  actually look more like a scroll type old page than a document." -> an old scroll/parchment: rolled or curled ends
  (top and bottom rolls drawn as curled card), irregular aged edges, NO ruled document lines; the name cut out as
  calligraphic lettering (thick-thin strokes, flourished capital, slight slant), legible when the page is flat. Make
  the text a look arg `page_text`, default "Cagliuso" (Gary typed "Camuso"; likely speech-to-text for the cue-sheet
  name — the gobo session will confirm with him). Build letters as vector shapes (no system font dependency) or
  from a bundled open calligraphic-feeling outline you draw; keep strokes >= 2 px in the cell.
- **Turnip:** "needs to be fatter with a couple of lines on its rotund side with smaller spiky leaves." -> a fat,
  rotund bulb (clearly wider than tall), 2 curved tapered slit lines following its roundness, a short tail root, and
  SMALLER spiky leaves (shorter than the bulb's height, 3-5 points). Keep the bite notches.
- **Bucket:** "looks okay, but ... it looks as though the water is coming out of the bottom of the bucket. So perhaps
  lose the handle and just make it slightly more bucket shaped." -> no handle; a classic pail: wider at the top than
  the bottom, a visible thick rim at the mouth, 2 hoop slits. Fix the pour origin: when tipped, the stream must leave
  from the LIP of the mouth (the rim edge closest to the boy), clearly at the open end, never from the base. Keep the
  current stop/target/stream/splash look values.
- **Pearl:** "good, although the pearl could lose its little star." -> remove the star punch; keep the crescent gleam.
- **Crown:** good, unchanged.
- **Boots:** "not very legible. It needs more detail as a boot. Although it should be a bit rounded and almost like a
  kind of mitten-y shape on the foot because we're actually buying little baby shoes to put on Puss." -> soft baby
  booties: a rounded mitten-like foot (big round toe, no heel spike), a soft ankle cuff (scalloped or folded edge), a
  strap or bow/button at the ankle, a stitched seam slit along the sole and one across the toe. Still sized for
  Puss's paws; same fall/bounce/land-in-a-row behaviour.

## Deliver (rule 8)
Updated props.py, props_sheet.png, re-rendered demos for page, turnip, bucket, pearl, boots (crown unchanged unless
the shared code requires it), frame strips, harness (keep all checks; add: bucket stream origin lies within N units of
the rim lip in every pour frame (+) and a base-origin stream fails (-); pearl has no punch other than the gleam (+);
turnip bulb width/height > 1.25 (+); page text renders N connected letter cut-outs (+)). Commit or file list.
