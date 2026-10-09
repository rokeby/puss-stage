# P51 — Fix job 33 per Gary, then resume editor batch 1 (Codex --unreal, LIVE)

Read `_house_rules.md`, `Docs/CodexUnrealMCPRunbook.md`, `Docs/Conductor/codex_briefs/p49_postbake_editor_runner.md`
(ALL its HARD RULES apply unchanged) and job 49's stop: `P33-20261009-024222` DRY refused
(`Saved/CodexConductor/passages_to_music_dry.json` "refusals", read it with encoding utf-8).

## Gary's answers (9 Oct, his own, conductor session)
1. "P06's music: SW_P06_IntoVoid (what plays now)". P06's length = the duration of /Game/InfinityStage/Audio/Passages/
   SW_P06_IntoVoid (measure it live from the SoundWave, cite the value; whole-frame ceiling as the tool already does).
   Do NOT swap P06's sound. The Cameron Walking6 analysis is no longer P06's source.
2. "Move them inside" for every PAST_END item (P05 Camera.HeightOffsetCm ×2, P06 choreoSections ×1, and any others the
   new DRY reports): add a past_end action `MOVE_INSIDE` = rescale the item's keys/section times proportionally by
   new/old Passage length (relative to Passage start) so they land inside the shortened Passage; record originals; REVERT
   restores exactly. KEEP_UNPLAYED stays available but is NOT used.

## Do
A. Offline: patch `Saved/CodexConductor/passages_to_music.py` for 1+2 (sound source = live sound for P06 by default; a
   SOUND_CHANGED refusal must no longer fire when the source is the live sound), extend `test_passages_to_music.py`
   (+ MOVE_INSIDE lands inside and reverts exactly; − KEEP_UNPLAYED not chosen implicitly; − a past-end item left
   unresolved still refuses). Harness green before any live run.
B. Live: DRY → if `apply_ready=1`, APPLY (Gary approved music lengths without review) → read back → census clean.
C. Then continue job 49's batch 1 from item 2 (P06 retime — it reads the live P06 length) through item 8, same rules,
   stop at the first failure.
D. When the batch ends (done or stopped), write `Saved/CodexConductor/EDITOR_BATCH1_DONE.json`
   {"status": "done"|"stopped", "stop_reason": ..., "utc": ...} — this releases Hyper3D's GPU chain. Write it ONLY when
   no PIE is running and the census is clean.
Report: job 49's table format + the new P06 length and dusk time; list changed files (commit nothing).
