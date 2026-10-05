# P05 (Gary 5 Oct): first half more meadow, field and wildflower, "somewhere between Yorkshire and the Caucasus";
# second half rocky slopes with geology and greenery foreshadowing the mountains, alternating with the clouds above
# ("middle of valley feel", "a nice landscape effect"); 3 more cloud shapes. Gary may place Megascan rocks himself.
CLOUD = "DerivedAssets/FlatV3/Review_2026-10-03/clouds/cs_builds/P05_CloudRef07_R_R_r4_CR02/skin/T_P05_CloudRef07_R_R_r4_CR02_SkinColor.png"
HAND = ("whimsical, a little sugary storybook landscape painting with the soft luminous volume of P05's clouds: sugared "
        "pastels, cream, sky blue, fresh greens, warm afternoon light, gentle and picaresque; no outlines")
AVOID = "people; buildings; text; cartoon outlines; CGI sheen; dark or threatening mood; tidy symmetry"
REF = "Style reference (Image node b, for light and palette): " + CLOUD
write_job("40_P05_meadow_wildflower_pairs", "40 · P05 first half: meadow and wildflower banks (Yorkshire to Caucasus)", REF,
  pair("", HAND, "tall bank of meadow grasses and wildflowers (buttercups, cranesbill, harebells, tall Caucasian bellflowers and "
       "ox-eye daisies) rising up a grassy knoll with a fragment of grey dry-stone wall at its foot",
       "a different flowering meadow mass: alpine hay meadow with tall lilies, scabious and clover, a few butterflies, lush and airy",
       AVOID, style_ref=True)
  + pair("", HAND, "tall stand of field-edge wildflowers and seed heads (poppies, cornflowers, cow parsley, wild oats) against a hedgerow",
         "a different field-edge mass: foxgloves, meadowsweet and long grasses with a gate post half hidden", AVOID, style_ref=True))
write_job("41_P05_rocky_slope_pairs", "41 · P05 second half: rocky slopes with geology and greenery (foreshadowing the mountains)", REF,
  pair("", HAND, "tall rising mountain-slope fragment: tilted layered sedimentary rock strata and limestone outcrops with turf, moss, "
       "alpine flowers and a few rowan saplings in the clefts, a small scree fan at the foot",
       "a different slope fragment: folded rock strata, a craggy shoulder with grassy ledges and a thin waterfall thread", AVOID, style_ref=True)
  + pair("", HAND, "taller, bolder mountain flank fragment: great slabs of banded rock leaning inward, grass and wildflowers on every ledge, "
         "suggesting a mountain with character",
         "a different bold flank: a rounded rocky shoulder and a cliff with grassy terraces, slightly comic in its lean", AVOID, style_ref=True))
CL = ("the supplied reference image (an existing P05 cloud wing)",)
def cloud(desc):
    return one_line("the supplied reference image (an existing P05 cloud wing)",
        "create a NEW tall abstract cloud wing: " + desc,
        "the same luminous painted volume, sugared palette and soft light as the reference; no outlines",
        "one tall coherent vertical cloud mass, abstract, with see-through gaps; final-handed RIGHT (backbone on the image RIGHT)",
        "a copy of the reference; faces or figures in the cloud; " + AVOID, BG + "; portrait 1:2")
write_job("42_P05_new_cloud_shapes", "42 · P05 three new cloud shapes (Gary 5 Oct)", "Image node: " + CLOUD,
  [("a: towering cumulus column (Image node: reference)", cloud("a towering cumulus column with a flat anvil shelf near the top, cream and rose")),
   ("b: twisting cloud ribbon (Image node: reference)", cloud("a twisting ribbon of cloud spiralling upward, peach and lilac")),
   ("c: stacked cloud pebbles (Image node: reference)", cloud("a stack of round cloud puffs like soft pebbles balanced on each other, white and pale gold"))])
