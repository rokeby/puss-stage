# P13: Opening lighting proposal (final jobs 4.2, 1.1, 1.4)
Gary 8 Oct: the opening lighting is "too large and washy. There's no reason for it to wash like that. It should be tighter, soft edge spots that move into the center, perhaps, and some lights in the upper left and right corners that dramatize the flurries of music. And ... the curtain doesn't come down in the final flurry ... the music is running and we're seeing a dark stage with only the first parts lit by the opening stage light."
His cue list: "(1) second flurry/wave: curtain falls; (2) second flurry/wave: lights come on; (3) third flurry, end of opening: perspective adjustment" (the first two both say "second": keep the flurry index an arg).
Read Docs/Conductor/OPENING_SEQUENCE_PLAN_2026-10-04.md, the opening's current cues in the Show (grep tools that author Opening cues and lights), and the P11 music analysis if it lands in DerivedAssets/MusicAnalysis/ (if it doesn't, take flurry times as args).
Build a DRY/APPLY/REVERT tool that:
- replaces the wash with N tight, soft-edged spots (narrow cones, high falloff exponent, soft penumbra) whose aims travel from the edges into centre stage;
- adds upper-left and upper-right corner fixtures that pulse on each flurry;
- moves the curtain drop and the lights-on to the flurry args, and puts the perspective adjustment on flurry 3;
- authors through the Show asset (the authority): cues and attachments.
Every intensity, angle, colour and timing is an arg with a default. Deliver a top/front diagram PNG of the rig and a cue timeline PNG over the music envelope. Apply nothing.
Deliver Docs/Conductor/P13_OPENING_LIGHTING_2026-10-08.md.
