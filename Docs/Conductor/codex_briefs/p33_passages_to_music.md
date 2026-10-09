# P33: Passage lengths = music lengths (Gary 9 Oct: "Passage lengths should = music lengths, yes")
Analysis + DRY plan exist: Tools/MusicAnalysis/p11_music_timing.py (DRY-only for Passage timing), Docs/Conductor/
P11_MUSIC_TIMING_2026-10-08.md (targets = selected music duration rounded up to the next 25 fps frame; total Master shrink
188.541 s; P05 186 -> ~42 s; hazard: P05 Camera.HeightOffsetCm keys past the new end; P06 WAV tail question).
Existing retime tool: Saved/CodexConductor/passage_retime_to_music.py (enforces a one-second fade tail, which conflicts with
exact length = music, P11 doc:50). Shrinking precedent: Saved/CodexSoftGoods/shrink_scene_playback.py (P24, offline-proven).
Job (offline): passages_to_music.py DRY/APPLY/REVERT that sets each Passage cue's length EXACTLY to its music length
(no fade tail; args allow a per-passage tail override, default 0), scaling LeadIn/intervals/Tail proportionally as P11 doc:51
describes, carrying Passage-relative keys (never silently scaling absolute keys: list them), Rebuild Master once, prove
downstream movement and relative key carry, save only Show + Master, read back. DRY must list per passage: old/new length,
every key/section/marker/Choreo item past the new end, and the P05 HeightOffset hazard resolution options. Harness +/-.
House rules incl. rule 9. Apply nothing; the conductor runs DRY tonight and Gary reviews before APPLY.
