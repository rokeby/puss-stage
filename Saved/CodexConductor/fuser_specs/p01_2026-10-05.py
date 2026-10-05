# P01 (Gary 5 Oct): all current pieces stay; warm-grade the B/W pieces; 8+ pairs; new: more foliage variants,
# mossy statuary (standing urn figure, broken pillar covered in moss), beehive, ivy, flowers.
HAND = ("Baroque scenic oil as painted on theatre flats, in the same hand as P01's rococo foliage wing: warm golden "
        "light, soft low-contrast chiaroscuro, rich greens, honey and rose, aged varnish; no outlines")
AVOID = "people; animals except bees; text; cartoon; CGI sheen; crisp digital edges; symmetry"
REF = "Style reference: DerivedAssets/FlatV3/Overnight/Kept/flats/P01_L_1_roccoco_L/stage1_colour_key_art.png"
K = "DerivedAssets/FlatV3/Overnight/Kept/flats/"

def regrade(src, side):
    return one_line("an existing black-and-white stage wing of classical architecture (" + side + ")",
                    "recolour it only: warm golden afternoon light, honey limestone, sepia and ochre shadows, a little "
                    "moss green in the crevices; low contrast, as if painted for a warm fairytale opening",
                    "the same painted/photographic hand as the input, now warm and golden; no outlines",
                    "EVERY shape, edge, crack, window and silhouette exactly as the input; same framing and handedness",
                    "new elements; changed silhouette; cool or grey tones; high contrast; text",
                    "the same canvas, aspect and background as the input (no drift)")

write_job("26_P01_warm_regrade", "26 · P01 warm regrade of the B/W pieces (Gary 5 Oct: 'Warm-grade them')",
  "No-drift recolour. Image node = the listed source, one sub-job per source. Overlay at 50% to check drift.",
  [("a: pillar1 L (Image node: " + K + "P01_L_pillar1_bw_L/stage1_colour_key_art.png)", regrade("pillar1", "left")),
   ("b: pillar1 R (Image node: " + K + "P01_R_Pillar1_bw_R/stage1_colour_key_art.png)", regrade("pillar1", "right")),
   ("c: pillar2 L (Image node: " + K + "P01_L_Pillar2_bw_L/stage1_colour_key_art.png)", regrade("pillar2", "left")),
   ("d: pillar2 R (Image node: DerivedAssets/WingMateriality/SourceExports/GroupB/R_Pillar2_bw.png)", regrade("pillar2", "right")),
   ("e: ceiling slab (Image node: DerivedAssets/WingMateriality/SourceExports/GroupB/Ceiling_bw.png)", regrade("ceiling slab", "top"))])

write_job("27_P01_fruit_tree_pair", "27 · P01 foliage variant: Baroque fruit tree", REF,
  pair("", HAND, "tall Baroque orchard tree heavy with golden pears and quinces, gnarled trunk, dense warm foliage, a few blossoms",
       "a different fruit tree (apricot or pomegranate) with a twisting trunk and fruit-laden boughs", AVOID, style_ref=True))
write_job("28_P01_rose_bower_pair", "28 · P01 foliage variant: rose bower", REF,
  pair("", HAND, "towering cascade of old roses and climbing briar over a hidden arch, blooms in rose, cream and apricot, deep green shade",
       "a different rose and honeysuckle cascade with heavier blooms low down", AVOID, style_ref=True))
write_job("29_P01_ivy_flower_cascade_pair", "29 · P01 foliage variant: ivy and wildflower mass", REF,
  pair("", HAND, "tall mass of dark ivy, ferns and wildflowers (foxglove, campanula, poppies) climbing an unseen support",
       "a different ivy and flower mass with trailing tendrils and lilies", AVOID, style_ref=True))
write_job("30_P01_mossy_urn_figure_pair", "30 · P01 mossy statuary: standing urn figure", REF,
  pair("", HAND, "weathered Baroque garden statue of a standing draped figure holding a tilted urn, on a tall plinth, everything thick with moss, lichen and ivy, flowers at its feet",
       "a different standing urn-bearing statue, turned the other way, equally mossy", AVOID, style_ref=True))
write_job("31_P01_mossy_broken_pillar_pair", "31 · P01 mossy statuary: broken pillar", REF,
  pair("", HAND, "tall broken classical pillar, fluted column snapped at the top, smothered in moss, ivy and small flowers, a fallen capital at its base",
       "a different broken pillar with a cracked entablature fragment, ivy-hung and mossy", AVOID, style_ref=True))
write_job("32_P01_beehive_pair", "32 · P01 beehives (a quiet echo of S6's bees)", REF,
  pair("", HAND, "tall stack of old straw bee skeps on a mossy stone bee-bole pedestal, wild flowers and ivy around, a few golden bees in the air",
       "a different tower of straw skeps and a wooden hive box on a mossy plinth, honeysuckle around", AVOID, style_ref=True))
