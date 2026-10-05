# P03 (Gary 5 Oct): broken variants of the convent flats (originals kept); wicker/stones/pyres enough as is; add beds.
SRC = "DerivedAssets/GeneratedConcepts/SanatoriumToChinoiserie/Passage03_RC/"
HAND = ("folk-horror pseudo-realism: photographic, stiff, bright, cool whites and straw yellow, hard clean daylight, "
        "like a museum object photograph; no outlines")
AVOID = "people; text; cartoon; CGI sheen; painterly brushwork; gore; graffiti"
def broken(name):
    return one_line("an existing clean rectilinear convent/sanatorium wall wing (" + name + ")",
        "make a DAMAGED variant of exactly this wall: two or three ragged holes where bright light peeps through, rotten timber "
        "edges, a strip of exposed lath and studwork, flaking whitewash, a little damp staining; it should feel quietly wrong",
        HAND, "the overall outline, proportions, door/window/curtain/cabinet elements and palette of the input; same handedness",
        "a completely different wall; colour change; " + AVOID, BG + "; same aspect as the input")
subs = [("%s (Image node: %s%s_01_R.png)" % (n, SRC, n), broken(n)) for n in
        ("P03_SunWashedAdministration", "P03_YellowCurtainThreshold", "P03_GlassBlockClassroom", "P03_RepeatingSanatoriumArches")]
write_job("35_P03_convent_broken_variants", "35 · P03 broken variants of the convent flats (originals kept; Gary 5 Oct)",
  "Each output is a NEW damaged variant to mix in as the run moves toward the stones. Sources are R-handed; mirror at build for L.", subs)
write_job("36_P03_beds_pair", "36 · P03 uncanny domestic: beds (Gary 5 Oct: 'Some beds is nice')", "",
  pair("", HAND, "tall stack of white-painted iron sanatorium beds stood on end against each other, starched sheets half pulled off, one pillow on the floor",
       "a different arrangement: a single tall iron bed frame stood upright with a straw mattress and a folded blanket, a chamber pot beside it",
       AVOID))
