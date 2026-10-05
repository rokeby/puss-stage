# P04 (Gary 5 Oct): pigeon-nest mound (twigs, shiny plastic wrapper debris, wire, feathers); austere monastery-school
# bookshelves (old books, some empty); less ruined heavy-timber 17th/18th C French/English seminary architecture.
REF = "Style reference: DerivedAssets/FlatV3/Overnight/Kept/flats/P04_coventry_ruin_L_v1 (the Coventry ruin's leaden hand)"
HAND = ("Baroque scenic distemper and oil on aged paper, in the same hand as P04's Coventry ruin wings: broad confident "
        "brushwork, leaden greys and black lead, cold English daylight, strong chiaroscuro; no outlines")
AVOID = "people; text or legible titles; cartoon; CGI sheen; crisp digital edges; symmetry; colourful modern objects except the wrapper glints"
write_job("37_P04_pigeon_nest_mound_pair", "37 · P04 pigeon-nest mound (for the great pigeon of the coming scene)", REF,
  pair("", HAND, "towering lumpen nest mound of twigs, sticks, wire and grey feathers studded with crumpled shiny plastic sweet wrappers "
       "and foil that catch the light, built up against a broken stone pier",
       "a different nest heap trailing wire and string, more feathers and wrapper glints, a few eggshell fragments", AVOID, style_ref=True))
write_job("38_P04_monastery_bookshelves_pair", "38 · P04 austere monastery-school bookshelves", REF,
  pair("", HAND, "tall austere dark-oak monastery-school bookcase, rows of old leather-bound books with gaps and two shelves left empty, "
       "a ladder leaning on it, plaster wall flaking behind",
       "a different tall bookcase, half-emptied, books leaning and fallen, a lectern beside it", AVOID, style_ref=True))
write_job("39_P04_seminary_timber_pair", "39 · P04 heavy-timber 17th/18th C seminary architecture (less ruined, stable)", REF,
  pair("", HAND, "intact heavy-timber architectural feature from an old 17th/18th century French or English seminary: a tall dark oak "
       "panelled screen with a carved door case and heavy beams, sober and stable, a little worn",
       "a different seminary timber element: a massive oak staircase newel and balustrade section with a tall panelled wall, "
       "stable and austere", AVOID, style_ref=True))
