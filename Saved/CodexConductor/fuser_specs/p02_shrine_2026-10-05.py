# P02 shrine end (Gary 5 Oct, his own photo as reference): an old stone pagoda gripped by fig/banyan trunks and roots,
# carved guardian-beast corners, tattered white paper-cloth offerings and one red ribbon, golden fallen leaves.
REFP = "DerivedAssets/FlatV3/GaryPhotos/Shrine_2026-10-05/pagoda_banyan_ref.jpg"
HAND = ("rich painted hand matching P02's Rousseau-like jungle wings, pushed slightly lurid and uncanny: deep shade, "
        "moss and lichen, an oily varnished sheen; painterly, not photographic; no outlines")
AVOID = "people; text or legible characters; cartoon; CGI sheen; crisp digital edges; tidy symmetry; modern buildings"
subs = [
 ("a: pagoda wing, left (Image node: " + REFP + ")", one_line(
   "Gary's own photograph of an old stone pagoda gripped by fig trees (reference for form only)",
   "paint a tall stone pagoda shrine wing from it: weathered multi-tier stone pagoda with carved guardian-beast corners and a dark "
   "doorway niche, its base swallowed by thick grey fig roots and a great trunk rising on the image LEFT as the backbone",
   HAND, "the pagoda's tiered silhouette, the gripping roots, the dark niche; final-handed LEFT wing; see-through gaps between trunk and tiers",
   AVOID, BG + "; portrait 1:2")),
 ("b: root-gripped trunk with offerings, right partner (Image node: a's output)", one_line(
   "the pagoda wing from sub-job a",
   "create its independently designed RIGHT partner: a massive fig trunk and aerial roots strangling a fallen stone pagoda tier, "
   "tattered white paper-cloth strips and one red ribbon tied round the roots, golden fallen leaves; backbone on the image RIGHT",
   HAND, "the same family, light and palette; final-handed RIGHT wing", "a mirror copy; " + AVOID, BG + "; portrait 1:2")),
 ("c: small stone stupa fragment pair (no input image)", one_line(
   "no input image; a smaller shrine fragment stage wing is required",
   "create a short broken stone stupa or pagoda tier on a root-wrapped plinth, guardian beast carving, moss, a few incense stubs and "
   "golden leaves; backbone on the image LEFT; then (second run) the RIGHT partner with a different fragment",
   HAND, "one coherent vertical mass, shorter than the pagoda (portrait 2:3)", AVOID, BG + "; portrait 2:3")),
 ("d: offerings sheet (no input image)", one_line(
   "no input image; a sheet of separate offering elements is required",
   "make 8-10 separate elements: tattered white paper-cloth strips and garlands, red ribbons and red cloth ties, small bundles of "
   "incense, folded paper offerings, each shaped to hang from branches, roots or a fence",
   HAND, "each element separate and complete, varied lengths", AVOID,
   "several separate small elements spread out on a plain flat background of colour #D6C8AA, not touching each other")),
]
write_job("34_P02_shrine_pagoda", "34 · P02 shrine end: root-gripped stone pagoda (Gary's photo, 5 Oct)",
  "Replaces the borrowed P04 ruins near the shrine. Gary's own photo is the reference (his rights). "
  "Offerings (d) can also hang on the lurid plants and fences near the shrine.", subs)
