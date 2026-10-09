# PG3 — Shadow-puppet plan for Interactions I1–I5 (offline, document + pose lists)

Read `_house_rules.md` (rule 6 tiers, rule 7: creative values are Gary's — propose, don't decide). Offline only.

Gary 9 Oct: "This is just the start, we'll need boy, puss and props in various versions of this thru i1-i5."

## Sources (read them; cite file:line)
- `Docs/BoyCatInterstitialTransition.md` — the I1–I5 cue spine (Washing the boy / Turnips / Forgets his name / Gets a
  name / Becomes King) and the performance states.
- `Docs/CueSheet/PUSS_CUE_LIST.md` and `Docs/CueSheet/working.csv` — the actual narration and actions around each
  Interaction (whimpers, "Klara moves boy", turnips eaten, etc.).
- `Docs/ShadowPuppetCaptureSpec.md`, `Docs/ShadowGoboPipeline_2026-10-06.md`, `Docs/Conductor/P6_ANIMATED_GOBO_FINDINGS_2026-10-08.md`
  — the gobo constraints (one flipbook atlas per spot pair, held poses + real-time moves, 1.88 lit rectangle, the two
  spots Hangar/Mouth share the frame, handheld wobble is live).
- Puppets that exist: `Tools/ShadowGobo/Puppets/boy_rig.py` (boy: neck/shoulder/elbow joints, faces open/squint/shut/
  wide, brows, mouths pout/blubber/surprised/sad, tears) and `cat_rig.py` (Puss: 8 sitting poses, tail, leg, jaw,
  faces). Look at their pose sheets in `rig_v1/` and `cat_v3/`.

## Deliver `Docs/Conductor/SHADOW_PUPPET_PLAN_I1_I5.md`
Per Interaction:
1. The beat list from the cue sheet with cue ids (R00xx) and approximate seconds if derivable (say how; mark inferred).
2. Who is on the screen (boy, Puss, both) and staging: boy faces right, Puss faces left; where each stands in the 1.88
   frame; whether they share one flipbook frame (one atlas, both puppets drawn together) — recommend.
3. Poses needed per puppet, mapped to EXISTING poses where possible, and NEW poses/parts needed (name them, e.g.
   "boy kneeling", "boy eating turnip", "boy wearing crown", "Puss licking boy's head").
4. Props needed (turnip(s), washing cloth/tongue, the stolen page with "Cagliuso", a crown, the father's memory?),
   each as a cut-paper prop spec (size relative to the boy, which hand holds it, rod).
5. Moves list (held pose -> move -> held pose) with rough durations, and an atlas cell estimate at 25 fps real-time
   moves (use PG2's budget idea: holds = 1 cell, moves = 25 x seconds).
6. Open creative questions for Gary (numbered, short).
Also a one-page summary table at the top (Interaction x puppets x new poses x props x est. cells).
No code changes. Commit the doc (or list it if your sandbox cannot commit). Rule 8 final message.
