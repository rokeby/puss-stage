# Gary 5 Oct: "write these" (six architectural series for fanning / undulating wings) "then more natural forms like
# hills and termite mounds and trees and also shacks". 8 different subjects per series, one '~~' paste each.
# Run: python fuser_new_jobs.py fuser_specs/series8_more_2026-10-05.py
PERSP = ("painted in one-point perspective like a Baroque theatre flat: receding lines converge to ONE vanishing point "
         "beyond the wing's onstage edge, LOW, about one-sixth of the way up the image (the eye height of a small animal)")
P01H = ("Baroque scenic oil as painted on theatre flats, in the same hand as P01's rococo foliage wing: warm golden "
        "light, soft low-contrast chiaroscuro, rich greens, honey and rose, aged varnish; no outlines")
P02H = ("rich painted hand matching P02's Rousseau-like jungle wings, pushed slightly lurid and uncanny: deep shade, "
        "moss and lichen, an oily varnished sheen; painterly, not photographic; no outlines")
P03H = ("folk-horror pseudo-realism: photographic, stiff, bright, cool whites and straw yellow, hard clean daylight, "
        "like a museum object photograph; no outlines")
P04H = ("Baroque scenic distemper and oil on aged paper, in the same hand as P04's Coventry ruin wings: broad confident "
        "brushwork, leaden greys and black lead, cold English daylight, strong chiaroscuro; no outlines")
P05H = ("whimsical, a little sugary storybook landscape painting with the soft luminous volume of P05's clouds: sugared "
        "pastels, cream, sky blue, fresh greens, warm afternoon light, gentle and picaresque; no outlines")
AV = "people; text; cartoon; CGI sheen; crisp digital edges; photographic look"
AV3 = "people; text; cartoon; CGI sheen; painterly brushwork; gore; graffiti"
NOIMG = "no input image; "
# Fanning / undulating: several flats overlap, turn about a pivot or ripple, so the outline must read on its own and
# leave see-through gaps; a tall narrow mass keeps its read edge-on.
FAN_KEEP = ("one coherent tall, narrow vertical mass with a strong readable outline and see-through gaps where natural, "
            "so it still reads when several overlap or turn edge-on")
FAN_FRAME = BG + "; portrait 1:2"
WING = "create one stage wing: "


def S(job_id, title, notes, hand, avoid, items, keep=FAN_KEEP, frame=FAN_FRAME, inp=NOIMG + "an original stage wing is required"):
    series8(job_id, title, notes, inp, WING, items, hand, keep, avoid, frame)


# ---- architectural (57-62) ----
S("57_P01_colonnade_slices_series", "57 · Colonnade slices ×8 (fan)", "Single columns from one curved colonnade; fanned, they sweep.",
  P01H + "; " + PERSP, AV,
  [("ionic, garlanded", "one Ionic column with a length of curved entablature, a rose garland looped from it"),
   ("ionic, urn above", "one Ionic column carrying a curved cornice block with a stone urn on top"),
   ("paired columns", "two Ionic columns close together under one curved cornice block"),
   ("column with statue", "one column with a statue niche-figure on a bracket beside it, cornice above"),
   ("column, vine-wrapped", "one Ionic column wrapped in a climbing vine, cornice above"),
   ("column, broken cornice", "one Ionic column whose cornice block is cracked and tilting"),
   ("pier and column", "a square pier and a column side by side, a small arch springing between them"),
   ("end column", "the last column of the colonnade, a scroll volute buttress at its foot")])
S("58_P01_arcade_bays_series", "58 · Arcade bays ×8 (undulate)", "One bay of a receding arcade per flat; undulating, the arcade breathes.",
  P01H + "; " + PERSP, AV,
  [("plain bay", "one round-arched bay of a stone arcade on two piers"),
   ("bay with lantern", "one arcade bay with an iron lantern hanging in the arch"),
   ("bay with balustrade", "one arcade bay with a low balustrade across its foot"),
   ("bay with fountain", "one arcade bay framing a small wall fountain"),
   ("bay with ivy", "one arcade bay half veiled in ivy"),
   ("bay with bust", "one arcade bay with a marble bust on a pedestal in the opening"),
   ("bay with shell niche", "one arcade bay whose back wall holds a shell niche"),
   ("bay, ruined", "one arcade bay whose arch has lost its keystone, the voussoirs slipping")])
S("59_P01_obelisks_spires_series", "59 · Obelisks and spires ×8 (fan)", "Tall narrow silhouettes, different heights; clean edge-on.",
  P01H, AV,
  [("plain obelisk", "a plain granite obelisk on a stepped plinth"),
   ("gilt-tipped obelisk", "a slender obelisk with a gilt pyramidion and a sunburst"),
   ("ball finial pier", "a tall gate pier topped by a stone ball finial"),
   ("pinnacle", "a crocketed Gothic pinnacle, tall and thin"),
   ("cypress urn", "a tall pedestal with an urn sprouting a clipped cypress"),
   ("column of fame", "a slim memorial column with a small winged figure on top"),
   ("bell spire", "a little open bell spire on four slim columns"),
   ("broken obelisk", "an obelisk snapped half way, its top lying askew at its foot")])
S("60_P01_balustrade_runs_series", "60 · Balustrade runs ×8 (undulate)", "Lengths of one long balustrade, some broken; a wave along the floor line.",
  P01H + "; " + PERSP, AV,
  [("plain run", "a length of stone balustrade with turned balusters and a heavy rail"),
   ("run with urn", "a length of balustrade with an urn on its end pier"),
   ("run with gap", "a length of balustrade with three balusters missing"),
   ("stair run", "a length of balustrade stepping down a short flight of stairs"),
   ("run with roses", "a length of balustrade overgrown with climbing roses"),
   ("run with putto", "a length of balustrade with a small stone putto on the end pier"),
   ("collapsed run", "a length of balustrade half collapsed, rail fallen, balusters strewn"),
   ("curved run", "a curved length of balustrade, convex toward the viewer")],
  keep="one coherent long low mass with a strong readable outline and gaps between the balusters",
  frame=BG + "; landscape 3:1")
S("61_P04_tracery_lancets_series", "61 · Gothic window tracery ×8 (fan)", "Pierced lancets; the gaps shift as they fan.",
  P04H, AV,
  [("single lancet", "one tall pointed lancet window frame of stone, empty of glass"),
   ("twin lancet", "two lancets under one pointed arch with a quatrefoil above"),
   ("rose fragment", "a tall window whose head holds a broken rose tracery"),
   ("perpendicular", "a tall Perpendicular window frame of thin stone mullions and transoms"),
   ("leaded remnant", "a lancet with a few shards of grey leaded glass still in it"),
   ("ivy lancet", "a lancet frame overgrown with ivy"),
   ("blown-out", "a window frame blasted open, one mullion missing, stones scorched"),
   ("timber tracery", "a seminary window of dark oak tracery and iron bars")])
S("62_P01_P05_topiary_series", "62 · Cypress, yew and topiary ×8 (fan)", "Clipped garden forms: architecture in plant form, for P01 and P05.",
  P01H, "people; animals; text; cartoon; CGI sheen; crisp digital edges",
  [("italian cypress", "a tall narrow Italian cypress"),
   ("yew cone", "a clipped yew cone on a square tub"),
   ("tiered yew", "a yew clipped into three stacked tiers"),
   ("yew arch pier", "a clipped yew pier with the start of a hedge arch"),
   ("spiral box", "a box tree clipped into a tall spiral"),
   ("peacock topiary", "a yew clipped into a peacock on a column"),
   ("overgrown topiary", "a once-clipped yew grown shaggy and lopsided"),
   ("hedge with niche", "a tall hedge panel with a niche holding a stone urn")])

# ---- natural forms and shacks (63-71) ----
S("63_P05_hills_series", "63 · Hills and landforms ×8 (P05)", "Rolling ground pieces; stacked in depth they make a landscape.",
  P05H, "people; buildings; text; cartoon outlines; CGI sheen; dark or threatening mood",
  [("round hill", "a single round green hill with a few sheep-tracks"),
   ("hill with copse", "a soft hill crowned by a small copse of round trees"),
   ("terraced hill", "a hill with grassy terraces like steps"),
   ("hayfield hill", "a gold hayfield hill with a hedge line"),
   ("alpine knoll", "a little alpine knoll with a boulder and gentians"),
   ("double hill", "two overlapping hills, the far one bluer"),
   ("cliff hill", "a hill broken into a small chalk cliff on one side"),
   ("mushroom hill", "a mossy hill studded with toadstools, one red")],
  keep="one coherent ground mass rising from a flat base, readable outline", frame=BG + "; landscape 3:1")
S("64_P02_termite_mounds_series", "64 · Termite mounds and earth towers ×8 (P02)", "Tall lumpen earth spires; they read edge-on.",
  P02H, "people; text or legible characters; cartoon; CGI sheen; crisp digital edges; tidy symmetry; modern buildings",
  [("cathedral mound", "a tall cathedral termite mound of red earth with fluted ribs"),
   ("cluster", "a cluster of three termite spires of different heights"),
   ("mound with tree", "a termite mound grown around a dead tree trunk"),
   ("chimney mound", "a slender chimney-like termite tower leaning slightly"),
   ("mossy mound", "an old termite mound furred with moss and ferns"),
   ("broken mound", "a termite mound broken open, its galleries showing"),
   ("fungus mound", "a mound with pale fungi sprouting from its flanks"),
   ("anthill heap", "a wide low ant heap of needles and earth with a stick standing in it")])
S("65_P02_jungle_trees_series", "65 · Jungle trees ×8 (P02)", "Rousseau-like trunks and crowns; backbone LEFT.",
  P02H, "people; text; cartoon; CGI sheen; crisp digital edges; tidy symmetry",
  [("buttress tree", "a huge buttress-rooted tree trunk with vines"),
   ("palm", "a tall leaning palm with ragged fronds"),
   ("banana", "a banana plant with huge torn leaves and a hanging flower"),
   ("strangler fig", "a strangler fig whose roots lattice a dead host"),
   ("tree fern", "a tall tree fern with an unfurling crown"),
   ("flame tree", "a tree with a crown of lurid red blossom"),
   ("bamboo clump", "a clump of thick bamboo canes leaning out"),
   ("dead giant", "a dead white jungle giant hung with lianas")],
  keep="one coherent vertical mass, backbone on the image LEFT, the crown reaching right, see-through gaps")
S("66_P05_meadow_trees_series", "66 · Meadow and alpine trees ×8 (P05)", "Storybook trees; backbone LEFT.",
  P05H, "people; buildings; text; cartoon outlines; CGI sheen; dark or threatening mood",
  [("round oak", "a round, cloud-like oak"),
   ("apple in blossom", "an apple tree in pink blossom"),
   ("larch", "a feathery alpine larch"),
   ("birch pair", "two slender birches leaning together"),
   ("willow", "a weeping willow by a sliver of water"),
   ("fir", "a tall dark-green fir with a snow-dusted tip"),
   ("pollard", "a knobbly pollarded willow with fresh shoots"),
   ("cherry", "a wild cherry with a few red cherries")],
  keep="one coherent vertical mass, backbone on the image LEFT, the crown reaching right, see-through gaps")
S("67_P04_blasted_trees_series", "67 · Blasted and dead trees ×8 (P04)", "Leaden, bare, broken; backbone LEFT.",
  P04H, "people; text; cartoon; CGI sheen; crisp digital edges; symmetry",
  [("lightning oak", "an oak split by lightning, one half dead"),
   ("shattered stump", "a shattered tree stump with splinters standing up"),
   ("bare elm", "a tall bare elm with rooks' nests"),
   ("yew in churchyard", "an ancient hollow churchyard yew"),
   ("leaning poplar", "a leaning dead poplar with ivy"),
   ("burnt tree", "a charred tree, black and glossy"),
   ("pollard row end", "a stunted pollarded willow, its head a fist of stubs"),
   ("hung branches", "a dead tree whose branches hold torn rags of grey cloth")],
  keep="one coherent vertical mass, backbone on the image LEFT, the branches reaching right, see-through gaps")
S("68_P03_rock_stacks_series", "68 · Rock stacks, tors and standing stones ×8 (P03)", "Photographic museum-object hand.",
  P03H, AV3,
  [("standing stone", "a single tall lichen-spotted standing stone"),
   ("holed stone", "a standing stone pierced by a round hole"),
   ("tor", "a granite tor of stacked rounded slabs"),
   ("sea stack", "a narrow sea stack of pale rock with a bird on top"),
   ("cairn", "a tall drystone cairn"),
   ("dolmen", "a small dolmen of three uprights and a capstone"),
   ("chalk pinnacle", "a white chalk pinnacle streaked with flint"),
   ("split boulder", "a boulder split cleanly in two, a sapling in the crack")])
S("69_P02_jungle_shacks_series", "69 · Jungle shacks ×8 (P02)", "Corrugated tin and timber; backbone LEFT.",
  P02H, "people; text or legible characters; cartoon; CGI sheen; crisp digital edges; tidy symmetry",
  [("stilt hut", "a timber hut on stilts with a rusted tin roof"),
   ("tin lean-to", "a corrugated tin lean-to against a tree, rust and moss"),
   ("thatched hut", "a palm-thatched hut half swallowed by leaves"),
   ("shrine shack", "a tiny tin shack with offerings at its door"),
   ("water tank", "a rusted water tank on a timber tower"),
   ("collapsed shack", "a shack collapsed sideways, roof sheets hanging"),
   ("boat shed", "a boat shed on stilts over black water"),
   ("signal hut", "a little tin hut with a crooked chimney pipe smoking")],
  keep="one coherent vertical mass, backbone on the image LEFT, see-through gaps where natural")
S("70_P03_sheds_huts_series", "70 · Sheds, huts and outbuildings ×8 (P03)", "Folk-horror outbuildings, photographic.",
  P03H, AV3,
  [("whitewashed bothy", "a small whitewashed stone bothy with a black door"),
   ("bathing hut", "a striped wooden bathing hut on wheels"),
   ("hen house", "a tarred timber hen house on legs"),
   ("net shed", "a tall black-tarred fishermen's net shed"),
   ("straw hut", "a beehive hut of bound straw"),
   ("well house", "a little roofed well house with a bucket"),
   ("privy", "a narrow whitewashed privy with a heart cut in the door"),
   ("drying rack", "a timber drying rack hung with pale fish and rope")])
S("71_P01_railway_huts_series", "71 · Railway huts and lineside sheds ×8 (P01)", "For the overgrown railway; backbone LEFT.",
  P01H, AV,
  [("platelayers' hut", "a brick platelayers' hut with a stove chimney, overgrown"),
   ("lamp hut", "a tiny corrugated lamp hut, rusted, roses through the roof"),
   ("water crane", "a cast-iron water crane with a leather hose"),
   ("signal post", "a lattice signal post with a semaphore arm, ivy-clad"),
   ("tool shed", "a timber tool shed with a sagging roof"),
   ("ground frame", "a small ground-frame cabin with levers showing"),
   ("waiting shelter", "a little wooden waiting shelter with a fretwork valance"),
   ("coal stage", "a timber coal stage with a heap of black coal and weeds")],
  keep="one coherent vertical mass, backbone on the image LEFT, see-through gaps where natural")
