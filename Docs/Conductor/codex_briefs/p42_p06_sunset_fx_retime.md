# P42 — P06 sunset + FX + bee/car re-time to the music-length P06 (Codex, offline)

Read `_house_rules.md`. Offline only. Codex job 33 (`Saved/CodexConductor/passages_to_music.py`) relengths P06 from
126.001 s to 110.561125 s (passages_to_music.py:10-11). Gary 9 Oct: passages = music lengths; the sunset SCALES
proportionally (conductor decision, so dusk keeps its place in the music).
Patch K is in source (P36 report): moved SECTIONS carry keys; keys INSIDE P06 stay where they are unless rescaled.

Build a DRY/APPLY/REVERT tool `p06_retime.py` that, AFTER job 33 has applied, rescales by k = new/old P06 length:
1. the P06 sunset keys (records `Saved/CodexConductor/p06_sunset_record.json`, dry `p06_sunset_dry.json`; fade 21.85 /
   horizon 37 / dark 52 / black 90 s);
2. the P06 FX set (`P06FX_20261008/p06_fx_set_record.json`: motes Wing 052, fire Wing 049) if its activation is time-keyed
   (it may be distance-gated — prove which, cite file:line);
3. the car (68.55 s, `place_p06_car_light_record.json`) and bee glints (80/100/118 s, `Effects_20261007/p06_bee_glints_record.json`).
Read the post-33 P06 length LIVE; refuse if job 33 hasn't applied (length still 126.001). Never touch the topple chains
(W&T re-times chain A; job 37b owns chain B). Print the new dusk time (horizon) for W&T's make_keys --slam-s.
Harness +/- controls; tiered report; deliver in your worktree.
