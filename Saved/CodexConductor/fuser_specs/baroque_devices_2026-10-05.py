# Baroque stage devices (Gary 5 Oct refs: Cesky Krumlov theatre, opera vault, garden arcade): arch rings, swag valances,
# cut-throughs, a PERSPECTIVE edit pass on existing architectural wings, and painted passage-end curtains.
PERSP = ("painted in one-point perspective like a Baroque theatre flat: every receding cornice, coffer, step and arch "
         "converges to ONE vanishing point beyond the wing's onstage edge, LOW, about one-sixth of the way up the image "
         "(the eye height of a small animal walking down the centre of the stage), so a row of these flats reads as one deep receding space")
WIDE = "the subject complete and isolated on a plain flat background of colour #D6C8AA, touching no edge, with a clear gap all round (for cutting)"
P01H = ("Baroque scenic oil as painted on theatre flats, warm golden light, honey limestone, gilt and soft rose, low contrast, "
        "aged varnish; no outlines")
P04H = ("Baroque scenic distemper and oil on aged paper, P04's leaden hand: broad brushwork, leaden greys and black lead, "
        "cold English daylight, strong chiaroscuro; no outlines")
AV = "people; text; cartoon; CGI sheen; crisp digital edges; photographic look"


def ring(hand, subject, avoid):
    return one_line("no input image; a full-width arch-ring stage flat is required",
        "create ONE continuous arch band: " + subject + "; it rises from the floor at image left, curves up and over, and comes down "
        "at image right, leaving the whole centre OPEN (the camera passes through it); the band is about one-eighth of the image width thick",
        hand + "; " + PERSP.replace("beyond the wing's onstage edge", "at the centre of the opening"),
        "a single near-symmetric arch band, open centre, solid outer outline", avoid, WIDE + "; landscape 3:2")


write_job("44_ALL_arch_rings", "44 · Arch rings: one-piece arch flats that stack into a vault (Gary 5 Oct ref)",
  "Each output is ONE flat spanning L to top to R; repeated down a passage they build a barrel vault. Test in the P04 look-bench bay.",
  [("a: P01 garlanded classical arch ring", ring(P01H, "a warm classical arch of honey stone with a carved archivolt, hung with a garland of roses and leaves, small putti heads on the keystone", AV)),
   ("b: P04 broken stone vault rib", ring(P04H, "a heavy Gothic stone vault rib with chevron moulding, cracked, one section chipped away, ivy trailing from the crown", AV)),
   ("c: P04 seminary timber arch", ring(P04H, "a dark oak timber arch of the seminary, braced with iron straps and heavy pegged beams", AV)),
   ("d: P03 whitewashed convent arch", ring("folk-horror pseudo-realism: photographic, stiff, bright whitewash, hard clean daylight; no outlines",
       "a plain whitewashed round convent arch with a thin painted border line, a little damp staining", "people; text; cartoon; CGI sheen"))])


def valance(hand, subject):
    return one_line("no input image; a theatre swag valance border is required",
        "create a long festoon valance: " + subject + ", hanging in deep swags across the full width with tasselled points",
        hand, "a horizontal band, swagged lower edge, heavy folds, full width", AV, WIDE + "; landscape 6:1")


write_job("45_ALL_swag_valances", "45 · Swag valances (the festoon border across the top, Krumlov ref)",
  "Borders: hung vertically facing camera across the top of a bay (see the ceiling-borders note).",
  [("a: P01 / Opening red velvet festoon", valance(P01H, "deep crimson velvet with gold fringe and gold rope tassels")),
   ("b: P04 faded ecclesiastical drape", valance(P04H, "faded violet-grey ecclesiastical damask, dusty, moth-eaten, one tassel hanging by a thread")),
   ("c: P06 scorched festoon", valance("the same hand as P06's covered drapery pieces; no outlines",
        "a once-grand silk festoon scorched and half burnt away, ember-edged holes, smoke-stained gold fringe"))])


def cut(hand, subject):
    return one_line("no input image; a cut-through stage flat is required",
        "create a wall flat pierced by a large arch through which a deeper painted vista is seen: " + subject,
        hand + "; " + PERSP.replace("beyond the wing's onstage edge", "at the far end of the vista"),
        "the wall frame solid, the vista inside the arch kept as part of the image (not cut out)", AV, WIDE + "; portrait 2:3")


write_job("46_ALL_cut_throughs", "46 · Cut-through flats: a wall with an arch opening onto a deeper vista (Krumlov back-cloth ref)",
  "Used occasionally mid-passage so the eye always has somewhere deeper to go.",
  [("a: P01 garden vista", cut(P01H, "a rococo garden of clipped hedges, statues and a far fountain in golden light")),
   ("b: P04 nave vista", cut(P04H, "a long ruined nave with shafts of cold light falling through broken windows onto rubble"))])


def persp_edit(desc):
    return one_line("an existing architectural stage wing (" + desc + ")",
        "redraw the SAME subject in Baroque theatre-flat perspective: " + PERSP,
        "the same hand, palette and light as the input; no outlines",
        "the subject's identity, materials, outline character, ornaments and handedness; the backbone side unchanged",
        "new subject matter; changed palette; people; text; cartoon; CGI sheen", BG + "; same aspect as the input")


K = "DerivedAssets/FlatV3/Overnight/Kept/flats/"
OV = "DerivedAssets/FlatV3/Overnight/flats/"
SRC3 = "DerivedAssets/GeneratedConcepts/SanatoriumToChinoiserie/Passage03_RC/"
P02S = "DerivedAssets/FlatV3/Overnight/P02Sets/flats/"
EDITS = [
    ("P01 pillar1 L", K + "P01_L_pillar1_bw_L/stage1_colour_key_art.png"),
    ("P01 pillar2 L", K + "P01_L_Pillar2_bw_L/stage1_colour_key_art.png"),
    ("P03 administration wall", SRC3 + "P03_SunWashedAdministration_01_R.png"),
    ("P03 sanatorium arches", SRC3 + "P03_RepeatingSanatoriumArches_01_R.png"),
    ("P03 glass-block classroom", SRC3 + "P03_GlassBlockClassroom_01_R.png"),
    ("P04 coventry ruin L v1", OV + "P04_coventry_ruin_L_v1/stage1_colour_key_art.png"),
    ("P04 coventry ruin R v1", OV + "P04_coventry_ruin_R_v1/stage1_colour_key_art.png"),
    ("P04 coventry interior L v1", OV + "P04_coventry_interior_L_v1/stage1_colour_key_art.png"),
    ("P02 SET19 concrete+pipe L", P02S + "P02_SET19_L/stage1_colour_key_art.png"),
    ("P06 grand pavilion L", OV + "P06_grand_pavilion_L_v1/stage1_colour_key_art.png"),
]
write_job("47_ALL_perspective_edits", "47 · Perspective edit pass on existing architectural wings (Gary 5 Oct: 'could be a game changer')",
  "Same art redrawn with a low one-point vanishing point on the stage axis. Mirror-handed partners follow once the look is "
  "approved. The P04 gallery joins after its curved recut.",
  [("%s (Image node: %s)" % (n, p), persp_edit(n)) for n, p in EDITS])

CURT = ("a painted theatre act-drop curtain, Baroque scenic painting on heavy cloth: painted swags and a painted frame round a "
        "central scene; the CENTRAL two-thirds kept calm and light-toned so shadow puppets projected on it read clearly")


def curtain(theme, palette):
    return one_line("no input image; a painted front-cloth curtain for the end of a passage is required",
        "paint the whole curtain: " + theme, CURT + "; palette: " + palette + "; no outlines",
        "the full rectangle of cloth edge to edge, a visible hem and soft vertical fold lines, symmetric frame",
        "people in the central field; text; logos; cartoon; CGI sheen",
        "the whole curtain filling the frame edge to edge (no background, no cut-out); landscape 16:9")


write_job("48_ALL_passage_end_curtains", "48 · Painted curtains at the end of each passage (Gary 5 Oct)",
  "One per passage: the curtain seen at the END of the passage before the hangar comes up. It must NOT show what is in the "
  "coming scene. It is NOT the shadow-play curtain (the red velvet drop in the hangar). Not cut out: a full rectangle. "
  "P06 has NO painted end curtain (Gary: only darkness, the curtain already on the ground on fire -- a staging/FX note).",
  [("P01 end", curtain("overgrown vegetation swallowing an old railway track that curves away into the distance in strong one-point perspective", "honey, moss green, rust, soft gold")),
   ("P02 end", curtain("a lurid jungle clearing, dense leaves framing an empty glade (no buildings)", "acid green, bruise purple, oxblood")),
   ("P03 end", curtain("a pale whitewashed convent window opening onto a bright cold shore with standing stones", "cool white, straw yellow, pale sky")),
   ("P04 end", curtain("a receding arcade of stone arches in strong one-point perspective, like a Baroque garden-arcade stage set, an empty floor between them", "leaden grey, black lead, cold white")),
   ("P05 end", curtain("a deer sniffing a red, poisonous-looking toadstool in a bucolic meadow, mountains in the distance", "cream, sky blue, fresh green, one vivid red"))])
