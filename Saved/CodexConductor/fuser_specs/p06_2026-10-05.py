# P06 (Gary 5 Oct): chinoiserie kept but used only ~3x each as a strange glimpse (placement change, not art);
# DOUBLE DOWN on scaffolding and drapery wings: some on fire / burning, some fallen over; bring in the lit Blender
# scaffold bay (DerivedAssets/FlatV3/BlenderTest/FlatV3_ScaffoldBay.blend -- geometry, not a Fuser job).
SO = "DerivedAssets/GeneratedConcepts/StageOpening/"
KEEP_HAND = "the same photographic/painterly hand, palette and lighting as the input; no outlines"
AVOID = "people; text; cartoon; CGI sheen; gore; explosions; smoke hiding the whole form"
def burning(name):
    return one_line("an existing draped/covered stage wing (" + name + ")",
        "make a BURNING variant of exactly this form: the drapery catching fire from one lower edge, real flames licking up "
        "one side, charred and blistered cloth, glowing ember edges round burnt holes revealing the dark structure beneath, a thin trail of smoke",
        KEEP_HAND, "the overall silhouette, folds and handedness of the input; the fire on ONE side only so the form stays legible",
        "a different object; " + AVOID, BG + "; same aspect as the input")
def fallen(name):
    return one_line("an existing draped/covered stage wing (" + name + ")",
        "make a FALLEN-OVER variant: the same covered form toppled and lying at a steep diagonal against its neighbour, "
        "cloth sliding off and pooling on the floor, a glimpse of the structure inside",
        KEEP_HAND, "the same cloth, colour and object identity as the input, now tilted about 35-55 degrees",
        "a different object; upright pose; " + AVOID, BG + "; same canvas aspect, the form fitting inside the frame")
subs = []
for n in ("CoveredPillar_01_L", "CoveredPillar_01_R", "CoveredBiomechCeramic_01_L_rococo-painterly", "GauzeLattice_01_R"):
    subs.append(("burning: %s (Image node: %s%s.png)" % (n, SO, n), burning(n)))
for n in ("CoveredPillar_01_R", "CoveredBiomechCeramic_01_L_exposed-rococo-painterly"):
    subs.append(("fallen: %s (Image node: %s%s.png)" % (n, SO, n), fallen(n)))
for n in ("BambooScaffold_01_L", "SteelScaffold_01_R"):
    subs.append(("scaffold with burning tarp: %s (Image node: %s%s.png)" % (n, SO, n), one_line(
        "an existing scaffolding stage wing (" + n + ")",
        "drape a torn black construction net and a scorched tarp over part of this scaffold, one corner of the tarp burning with "
        "real flames and glowing edges, a work lamp hanging from a pole",
        KEEP_HAND, "the scaffold's members, proportions and handedness exactly as the input",
        "a different structure; " + AVOID, BG + "; same aspect as the input")))
write_job("43_P06_burning_and_fallen_drapes", "43 · P06 burning and fallen-over drapes and scaffold (Gary 5 Oct: double down)",
  "Variants of existing P06 pieces; originals stay. Fire in the art is a static image -- live fire comes from BurnProgress/effects.", subs)
