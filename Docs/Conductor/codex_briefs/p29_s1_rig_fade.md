# P29: S1 3:44 rig lights fade instead of snap (Gary F5, Docs/Conductor/GARY_FINISHING_NOTES_2026-10-08.md)
Gary: at S1 3:44 the rig lights "turn off/disappear, jolted into disappearance" as her street-lamp lights light the trees; "the
transition is fine but it shouldn't snap". Find which tracks switch the rig lights off near S1 3:44 (LS_DevScene_01 @ its
display rate; candidates: klara_reveal.py "Klara Reveal - Hide: S1 Lattice Bulb ..." visibility bindings, rig light intensity
tracks, hangar rise intensity tracks in LS_S1_HangarRise; the S1 hookin "Ours Off" set). Offline: read the tools/records that
authored them (Saved/CodexConductor/KlaraIngest/klara_reveal*.json/py, *_record_S1*.json) and DESIGN a fade: where a light is
switched by VISIBILITY, replace the step with an intensity ramp (1-2 s, args) ending at 0, then visibility off at the ramp end;
where by intensity keys, retime the step into a ramp. Tool: s1_rig_fade.py DRY/APPLY/REVERT, house rules incl. rule 9.
DRY must print every light it would ramp with its current switch frame and mechanism. Harness +/- controls.
