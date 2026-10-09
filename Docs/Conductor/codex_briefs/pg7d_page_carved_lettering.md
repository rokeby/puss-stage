# PG7d — Page: carved knife-cut lettering, diagonal (offline, small)

Read `_house_rules.md`. Offline only. Do not edit `Saved/CodexConductor/animated_gobo.py`.

## Gary, 9 Oct
After seeing the name in a typeset calligraphic font (Gabriola): "you were right the first time. [The name] is written
too nicely in the font. It would be better to use the kind of carved out look. Although a little bit more detailed
than your last effort. And also diagonally across the scroll." (The "first time" = PG7c's stick capitals, drawn by
`page_text_strokes()` in `Tools/ShadowGobo/Puppets/props.py`.)

## Build (in `props.py`, on master HEAD)
1. Carved woodcut lettering for `LOOK["page"]["page_text"]` ("Cagliuso"), replacing the default font path:
   - every stroke is a KNIFE CUT: a tapered wedge (thick in the middle/at the start, pointed at the ends) like
     `puppet_cut.slit`, not a constant-width line; downstrokes thick, upstrokes and crossbars thin;
   - small wedge serifs (triangular nicks) at stroke ends; a slightly flourished capital C (an extra tapered swash
     cut); letters slightly irregular in angle/size (deterministic jitter from a seed arg) so it feels hand-carved;
   - capitals or a mixed carved style — keep it legible from the audience; each letter a separate cut-out where
     possible (bridges of card between letters, like a real stencil).
2. Diagonal: the whole word runs diagonally across the scroll, rising left to right at ~ -18 degrees (look arg
   `page_text_angle_deg`), centred, filling ~85 % of the scroll's diagonal length (look arg).
3. Keep `page_font` as an OPTIONAL look arg but default it to None (carved). Keep the scroll outline, demo motion,
   SDF 8192 packing and BlurUV 0.
4. Thin features: knife-cut wedges must keep >= 2 px at their widest point in the page demo cells; report the
   narrowest wedge middle width. Raise the page's size_boy_height if needed (report it; Gary approves).
5. Re-render the page template, SVG (polygons, not a font reference), props_sheet, and the page demo (atlas,
   manifest, contact, GIF < 4 MB, frame strip) + a large close-up PNG of the flat page.

## Harness (+/-)
Letters render as >= len(text) separate cut-outs (+); the text's principal axis angle is within 5 degrees of the arg (+;
-: a horizontal layout fails); every cut stays inside the scroll with >= 6 units of card margin (+; -: an overhanging
stroke fails); no font file is opened when page_font is None (+); all existing prop checks still pass.

## Deliver (rule 8)
Paths, commit or file list, harness counts, close-up path, narrowest wedge width, any size change.
