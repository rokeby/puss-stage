# Gary 5 Oct: "another good batch would be gobos or shadow figures for the lights". Masks for light functions / gobo
# textures, not paintings. Never name the device ("gobo", "slide", "disc"): the generator paints the metal disc INTO
# the picture (same trap as "curtain"). Describe only the black-and-white pattern, full frame.
# Run: python fuser_new_jobs.py fuser_specs/series8_gobos_2026-10-05.py
NOIMG = "no input image; "
MASK_HAND = ("a pure black-and-white stencil mask: white where light passes, black where it is blocked, no colour, "
             "flat graphic, no shading inside shapes, edges slightly soft as if cut by hand")
MASK_KEEP = "high contrast, roughly half the area white, the pattern touching every edge so it tiles into darkness cleanly"
MASK_AVOID = ("colour; grey gradients; a circle, ring, disc, frame or border around the pattern; metal; photographic texture; "
              "text; logos; people")
MASK_FRAME = "the pattern fills the whole square frame edge to edge; square 1:1"
FIG_HAND = ("a pure black silhouette on a pure white ground, as a shadow cast on a wall in a shadow-puppet play: "
            "crisp but slightly soft edge, no interior detail, no colour")
FIG_KEEP = "one readable silhouette, centred, clear negative spaces (gaps between limbs) so it reads instantly as a shadow"
FIG_AVOID = "colour; grey; interior detail; a frame or border; a background scene; text; logos"
FIG_FRAME = "the silhouette complete with a clear white margin all round; square 1:1"


def mask(job, title, notes, items):
    series8(job, title, notes, NOIMG + "a black-and-white light mask image is required", "make the mask pattern: ",
            items, MASK_HAND, MASK_KEEP, MASK_AVOID, MASK_FRAME)


def figs(job, title, notes, items, avoid=FIG_AVOID):
    series8(job, title, notes, NOIMG + "a single black silhouette image is required", "make the silhouette: ",
            items, FIG_HAND, FIG_KEEP, avoid, FIG_FRAME)


mask("72_P01_P05_foliage_dapple_masks_series", "72 · Foliage dapple masks ×8 (P01, P05)",
  "Light through leaves. White = light. For spots and the sun's light function.",
  [("oak leaves", "sunlight breaking through a canopy of oak leaves"),
   ("rose trellis", "a rose-covered trellis, lattice and leaves"),
   ("willow fronds", "hanging willow fronds in vertical strands"),
   ("birch dapple", "small scattered birch-leaf dapples"),
   ("vine pergola", "a vine pergola, beams and big leaves"),
   ("fir branches", "fir branches in layered sprays"),
   ("blossom", "apple blossom clusters and twigs"),
   ("ivy wall", "a wall of ivy with a few gaps")])
mask("73_P03_P04_window_masks_series", "73 · Window and tracery masks ×8 (P03, P04)",
  "Light shapes through architecture: the classic window-on-the-floor.",
  [("cross pane", "a four-pane window with a cross-shaped glazing bar"),
   ("gothic lancet pair", "two pointed Gothic lancets with a quatrefoil above"),
   ("rose window", "a rose window's radiating tracery"),
   ("leaded diamonds", "diamond-leaded glazing, several panes broken out"),
   ("barred cell", "a small window crossed by iron bars"),
   ("venetian blind", "a venetian blind's slats, slightly uneven"),
   ("broken frame", "a blasted window frame with jagged shards"),
   ("convent grille", "a convent window's square iron grille with a cross")])
mask("74_P02_jungle_masks_series", "74 · Jungle leaf masks ×8 (P02)", "Big lurid leaf shapes for P02's spots.",
  [("monstera", "split monstera leaves overlapping"),
   ("palm fronds", "palm fronds radiating"),
   ("banana leaves", "torn banana leaves"),
   ("lianas", "hanging lianas and loops"),
   ("fern fronds", "fern fronds unfurling"),
   ("bamboo", "bamboo canes and narrow leaves"),
   ("hanging roots", "a mass of hanging aerial roots"),
   ("orchids", "orchid sprays among broad leaves")])
mask("75_ALL_breakup_masks_series", "75 · Breakup and texture masks ×8", "Atmospheric breakups: water, cloud, fire, haze.",
  [("water caustics", "the wavering net of light reflected off water"),
   ("cloud shadow", "soft-edged drifting cloud shapes"),
   ("fire flicker", "tall licking flame tongues"),
   ("rain streaks", "slanting rain streaks"),
   ("broken breakup", "irregular broken shards of light, an abstract breakup"),
   ("smoke wisps", "curling smoke wisps"),
   ("snowflakes", "scattered snowflakes of different sizes"),
   ("ripples", "concentric ripples spreading from several points")])
figs("76_ALL_shadow_animals_series", "76 · Shadow figures: animals ×8",
  "Cast shadows for the lights. White ground becomes no light; the silhouette is the shadow.",
  [("cat walking", "a cat walking, tail up"),
   ("cat stretching", "a cat in a long stretch"),
   ("great pigeon", "a huge pigeon, puffed, side view"),
   ("deer", "a deer lifting its head, antlers"),
   ("hare", "a hare sitting up, ears tall"),
   ("rook flock", "a few rooks taking off"),
   ("fox", "a fox trotting"),
   ("moth", "a large moth, wings open")])
figs("77_ALL_shadow_figures_series", "77 · Shadow figures: uncanny ×8",
  "Theatrical shadows: puppets, giants and things that should not be there.",
  [("hand bird", "two hands making a bird, as a hand-shadow game"),
   ("hand dog", "hands making a barking dog's head"),
   ("giant figure", "a huge figure in a long coat and tall hat, seen from the side"),
   ("witch", "a crooked figure with a pointed hat and a broom"),
   ("puppet king", "a shadow-puppet king on rods, crowned, jointed arms"),
   ("tree hand", "a bare tree whose branches end like grasping fingers"),
   ("dancer", "a dancer mid-leap"),
   ("procession", "a small procession of hooded figures")],
  avoid="colour; grey; interior detail; a frame or border; a background scene; text; logos")
