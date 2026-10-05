# Gary 5 Oct: Fuser now runs 8 prompts per paste ('~~' between prompts). Series = one job, every field fixed except the
# subject, 8 different subjects (his answer: "Different subjects"). Each job folder gets BATCH8.txt, paste-ready.
# Run: python fuser_new_jobs.py fuser_specs/series8_2026-10-05.py
PERSP = ("painted in one-point perspective like a Baroque theatre flat: every receding cornice, coffer, step and arch "
         "converges to ONE vanishing point, LOW, about one-sixth of the way up the image "
         "(the eye height of a small animal walking down the centre of the stage), so a row of these flats reads as one deep receding space")
WIDE = BG
P01H = ("Baroque scenic oil as painted on theatre flats, warm golden light, honey limestone, gilt and soft rose, low contrast, "
        "aged varnish; no outlines")
P04H = ("Baroque scenic distemper and oil on aged paper, P04's leaden hand: broad brushwork, leaden greys and black lead, "
        "cold English daylight, strong chiaroscuro; no outlines")
P06H = "the same hand as P06's covered drapery pieces: smoky, ember-lit, grand and ruined; no outlines"
AV = "people; text; cartoon; CGI sheen; crisp digital edges; photographic look"
NOIMG = "no input image; "

# 49 -- P04 arch rings: they stack down a bay into a barrel vault.
RING_TAIL = ("; it rises from the floor at image left, curves up and over, and comes down at image right, leaving the whole "
             "centre OPEN (the camera passes through it); the band is about one-eighth of the image width thick")
series8("49_P04_arch_rings_series", "49 · P04 arch rings ×8 (series)",
  "Eight vault ribs in one hand; stacked down a bay they read as one ruined vault. Test in the P04 look-bench bay.",
  NOIMG + "a full-width arch-ring stage flat is required", "create ONE continuous arch band: ",
  [("chevron rib", "a heavy Norman stone rib carved with deep chevron moulding" + RING_TAIL),
   ("plain ashlar", "a plain ashlar stone rib of large dressed blocks, joints soot-darkened" + RING_TAIL),
   ("broken crown", "a Gothic stone rib whose crown has fallen away, two jagged ends almost meeting over a gap" + RING_TAIL),
   ("ivy-hung", "a pointed stone rib hung thickly with ivy and trailing creepers from the crown" + RING_TAIL),
   ("seminary timber", "a dark oak timber arch braced with iron straps and pegged beams" + RING_TAIL),
   ("iron girder", "a riveted Victorian iron girder arch, rust-bloomed, with a pierced quatrefoil web" + RING_TAIL),
   ("dogtooth", "a Gothic rib with a running dogtooth ornament and small carved corbel heads at the springing" + RING_TAIL),
   ("bomb-scarred", "a stone rib scorched black on one side, shrapnel-pitted, a few stones displaced but still standing" + RING_TAIL)],
  P04H + "; " + PERSP.replace("converges to ONE vanishing point", "converges to ONE vanishing point at the centre of the opening"),
  "a single near-symmetric arch band, open centre, solid outer outline", AV, WIDE + "; landscape 3:2")

# 50 -- P01 columns: single L-handed wings; R partners come later as edits.
COL_TASK = "create one classical stage wing: "
COL_TAIL = "; the straight backbone on the image LEFT, the form reaching right"
series8("50_P01_columns_series", "50 · P01 pillars and columns ×8 (series)",
  "LEFT-handed wings; the RIGHT partners follow as edit jobs once Gary picks. Same hand as the P01 pillar wings.",
  NOIMG + "an original stage wing is required", COL_TASK,
  [("fluted Corinthian", "a fluted Corinthian column on a tall pedestal, a scrap of entablature above" + COL_TAIL),
   ("twisted Solomonic", "a twisted Solomonic column wound with a gilt vine" + COL_TAIL),
   ("rusticated pier", "a heavy rusticated pier with a niche holding an urn" + COL_TAIL),
   ("paired pilasters", "two Ionic pilasters on a wall fragment with a swagged garland between them" + COL_TAIL),
   ("broken column", "a broken Doric column shaft, its capital lying at its foot among roses" + COL_TAIL),
   ("caryatid", "a stone caryatid carrying a cornice block on her head" + COL_TAIL),
   ("obelisk on plinth", "a slender obelisk on a carved plinth with a gilt ball finial" + COL_TAIL),
   ("trellis column", "a garden trellis column in painted green lattice, climbing roses through it" + COL_TAIL)],
  P01H + "; " + PERSP, "one coherent vertical mass, final-handed LEFT wing, see-through gaps where natural",
  AV, WIDE + "; portrait 1:2")

# 51 -- swag valances: borders across the top of a bay, mixed passages (one hand per variant via the subject text).
VAL_TAIL = ", hanging in deep swags across the full width with tasselled points"
series8("51_ALL_swag_valances_series", "51 · Swag valances ×8 (series)",
  "Borders hung across the top of a bay (ceiling-borders note). Subjects name their passage; the shared hand is a neutral Baroque scenic one.",
  NOIMG + "a theatre swag valance border is required", "create a long festoon valance: ",
  [("P01 crimson & gold", "deep crimson velvet with gold fringe and gold rope tassels, warm golden light" + VAL_TAIL),
   ("P01 rose garland", "a festoon of pink roses and leaves on gilt ribbons" + VAL_TAIL),
   ("P04 faded damask", "faded violet-grey ecclesiastical damask, dusty and moth-eaten, cold light" + VAL_TAIL),
   ("P04 mourning crape", "black mourning crape with dull jet beading, leaden light" + VAL_TAIL),
   ("P06 scorched silk", "once-grand silk scorched and half burnt away, ember-edged holes, smoke-stained gold fringe" + VAL_TAIL),
   ("P06 smouldering brocade", "heavy brocade smouldering at the hem, a faint glow along the burnt edge" + VAL_TAIL),
   ("P02 jungle vine", "a festoon of lurid jungle vines, orchids and hanging seed pods instead of cloth" + VAL_TAIL),
   ("P05 meadow bunting", "pale linen swags trimmed with dried meadow flowers and ribbons, soft daylight" + VAL_TAIL)],
  "Baroque scenic painting as on theatre borders, broad confident brushwork; no outlines",
  "a horizontal band, swagged lower edge, heavy folds, full width", AV, WIDE + "; landscape 6:1")

# 52-56 -- passage-end curtains, 8 takes per passage. NEVER name the curtain (Gary 5 Oct). Must not show the coming scene.
# P06 has none (darkness; the curtain already on the ground, on fire).
CURT = ("Baroque scenic painting in the manner of an eighteenth-century theatre scene painter: broad confident brushwork, "
        "luminous depth, rich and complete across the whole picture")
CURT_KEEP = "one continuous scene filling the frame edge to edge, a clear deep composition"
CURT_AVOID = "frames; borders; architecture of a theatre; people; text; logos; cartoon; CGI sheen"
CURT_FRAME = "the painting fills the whole frame edge to edge (no background, no cut-out, no border); landscape 16:9"
ENDS = {
  "P01": ("honey, moss green, rust, soft gold", [
    ("railway curve", "overgrown vegetation swallowing an old railway track that curves away into the distance"),
    ("signal box", "a derelict signal box drowned in brambles beside a straight track running to the horizon"),
    ("viaduct", "a stone viaduct half buried in trees, the track on top vanishing into haze"),
    ("platform", "an abandoned country platform with a rose-covered canopy and rails running away"),
    ("tunnel mouth", "a tunnel mouth framed by ivy and fallen leaves, warm light beyond"),
    ("buffer stop", "a rusted buffer stop at the end of a line, a meadow of tall grasses beyond"),
    ("level crossing", "a level crossing gate thrown open, the road and rails both overgrown, golden evening"),
    ("goods wagons", "a line of rotting wooden goods wagons in a cutting, saplings growing through them")]),
  "P02": ("acid green, bruise purple, oxblood", [
    ("glade", "a lurid jungle clearing, dense leaves framing an empty glade"),
    ("pool", "a black jungle pool ringed with huge leaves and pale flowers"),
    ("fallen trunk", "a giant fallen trunk across a glade, furred with moss and fungus"),
    ("hanging roots", "a dense hanging veil of aerial roots with light breaking through"),
    ("swamp", "a steaming swamp of reeds and broad leaves, birds of paradise in the trees"),
    ("lily pads", "a glade carpeted with giant lily pads and one strange bloom"),
    ("canopy gap", "a gap in the canopy where a single shaft of light falls on bare earth"),
    ("night jungle", "the jungle at dusk, a huge pale moon behind dark fronds")]),
  "P03": ("cool white, straw yellow, pale sky", [
    ("window to shore", "a pale whitewashed window opening onto a bright cold shore with standing stones"),
    ("dunes", "pale dunes and marram grass under a vast white sky"),
    ("stone row", "a row of standing stones running to the sea"),
    ("cliff path", "a chalk cliff path with a straw-yellow field above"),
    ("harbour wall", "an empty harbour wall and a calm grey-white sea"),
    ("hayfield", "a cut hayfield with neat stooks under hard clean daylight"),
    ("lighthouse", "a small white lighthouse far off across flat sands"),
    ("chapel ruin", "a roofless whitewashed chapel on a headland")]),
  "P04": ("leaden grey, black lead, cold white", [
    ("arcade", "a receding arcade of stone arches like a Baroque garden-arcade stage set, an empty floor between them"),
    ("nave", "a long ruined nave open to a white sky, rubble on the floor"),
    ("cloister", "a cloister walk receding in perspective, one side open to a dead garden"),
    ("crypt", "a low vaulted crypt receding into darkness, a cold light at the far end"),
    ("stair", "a grand stone stair rising away into grey light, its balustrade broken"),
    ("bridge", "a stone bridge of many arches over a still leaden river"),
    ("colonnade", "a colonnade of black-lead columns under snow"),
    ("bombed street", "a street of gutted stone facades receding to a single vanishing point")]),
  "P05": ("cream, sky blue, fresh green, one vivid red", [
    ("deer & toadstool", "a deer sniffing a red, poisonous-looking toadstool in a bucolic meadow, mountains in the distance"),
    ("hare", "a hare sitting up in a buttercup meadow, a red-capped mushroom ring around it"),
    ("orchard", "an orchard in blossom with one red apple on the grass"),
    ("alpine lake", "a still alpine lake with a red boat on the shore"),
    ("hay meadow", "a hay meadow with a single red poppy patch, distant chalets"),
    ("brook", "a brook through a meadow with a fox drinking, red berries on the bank"),
    ("shepherd's hut", "an empty shepherd's hut in a high pasture, a red door, mountains beyond"),
    ("fawn asleep", "a fawn asleep in long grass beside a red, poisonous-looking toadstool")]),
}
for n, (passage, (palette, takes)) in enumerate(ENDS.items(), 52):
    series8("%d_%s_end_curtain_series" % (n, passage), "%d · %s passage-end painting ×8 (series)" % (n, passage),
      "Eight takes for the painting seen at the END of %s before the hangar comes up; Gary picks one. It must not show "
      "the coming scene and is not the shadow-play drop. A full rectangle, not cut out." % passage,
      NOIMG + "a full-bleed landscape painting is required", "paint the scene: ",
      takes, CURT + "; palette: " + palette + "; no outlines", CURT_KEEP, CURT_AVOID, CURT_FRAME)
