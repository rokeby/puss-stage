# P02 (Gary 5 Oct): lurid colour passes on the plant sets, KEEPING the originals too for variation;
# creepers over fences/shutters (queued job 25 c); SET16 + SET18-20 kept as they are; shrine pieces pending Gary's ref.
SETS = "DerivedAssets/FlatV3/Overnight/P02Sets/flats/"
def lurid(side):
    return one_line("an existing painted jungle-plant stage wing in a Rousseau-like manner (" + side + "-handed)",
        "keep this plant mass and its shapes, but push it MORE lurid and poisonous: acid-green and bruise-purple leaves, "
        "oxblood flowers like open mouths, deeper shadow between the leaves, an oily varnished sheen",
        "the same painted hand as the input, richer and more saturated; no outlines",
        "the silhouette, main stems, leaf shapes and handedness exactly as the input; see-through gaps kept",
        "new background; animals; text; cartoon; CGI sheen; changed outline",
        BG + "; same aspect as the input")
subs = []
for s in ("SET01", "SET04", "SET06", "SET07"):
    for side in ("L", "R"):
        subs.append(("%s %s (Image node: %sP02_%s_%s/stage1_colour_key_art.png)" % (s, side, SETS, s, side, ) if False else
                     "%s %s (Image node: %sP02_%s_%s/stage1_colour_key_art.png)" % (s, side, SETS, s, side),
                     lurid("left" if side == "L" else "right")))
C3 = "DerivedAssets/GeneratedConcepts/Passage02Forest/RousseauApprovedIndividualSequenceV5/chroma/set_03/"
subs.append(("SET03 L (Image node: %sP02_SET03_L.png)" % C3, lurid("left")))
subs.append(("SET03 R (Image node: %sP02_SET03_R.png)" % C3, lurid("right")))
write_job("33_P02_lurid_variants_of_sets", "33 · P02 lurid variants of the plant sets (originals kept; Gary 5 Oct)",
  "One sub-job per existing set side; the output is a NEW lurid variant, the original stays in the show for variation. "
  "Creepers for the fences: run job 25 sub-job c.", subs)
