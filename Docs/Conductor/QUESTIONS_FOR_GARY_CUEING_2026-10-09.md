# Cueing questions for Gary (morning, 9 Oct)

Asked as a questionnaire when Gary is next at the PC or on his phone. Recommendation first.

1. **The GO hold before each curtain drop (I1–I5, "GO n curtain" at 67 s).** Your I2 note asked for it to play
   straight through. Which interactions should?
   - I2 only (your note) — recommended until you've watched the others
   - All five
   - I2 and I3
   - Keep the holds for performance; only skip them in rehearsal (run-through mode does this once tonight's build lands)
   Tool ready, not run: `Saved/CodexCueing/go_mode_relabel.py` (DRY). Conductor 5 runs it in an editor slot.

2. **May the Cue Book move GO points, or only add and rename them?**
   - Add and rename freely; a move needs an explicit confirm (recommended)
   - Add, rename and move freely
   - Only rename; GO points are placed in Unreal

3. **Where are surtitles edited?**
   - Only in the Cue Book; it writes the file Unreal reads (recommended; one writer, as the Surtitle session asked)
   - In the Cue Book and the master Google Sheet, merged like the cue list

## Answers (Gary, this session, 9 Oct)

1. "key interaction should play through the hold because even in rehearsal mode … we need to be sure looks smooth and
   the pause causes the texture to glitch" → read as EACH interaction (I1–I5): `go_mode_relabel_request.json` now
   targets all five (DRY; APPLY in an editor slot). If he meant one, he says which; REVERT restores.
2. "Yes, the cue book can move go points. Overall, go points are not too critical … We could do the show without,
   except maybe the live music part and something to help Klara pace her live narration." → cb1: moves allowed
   without an extra confirm; DRY still lists them.
3. "The surtitles should be editable in the cue book, but also editable in Unreal because it's in Unreal that we'll
   understand the real time codes …" → two editors: cb3 export becomes a three-way merge (Key column + base file);
   Unreal-side editing is the Surtitle session's later C++.
