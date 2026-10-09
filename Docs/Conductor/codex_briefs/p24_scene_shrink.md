# P24: shorten a Scene/Sequence cue safely (F18: end Interaction 2 at the curtain fall)
Tool: Saved/CodexSoftGoods/extend_scene_playback.py (live-proven tonight for LENGTHENING S2: 2025 -> 3891, Master match 0.0 s).
It REFUSES new_end <= old_end for Sequence cues before its dry-run return (extend_scene_playback.py:345-346) and only moves cut
ends equal to the old end (:83-96). Gary's F18 (Docs/Conductor/GARY_FINISHING_NOTES_2026-10-08.md): "end I2 at the curtain
fall"; the I2 order DRY measured N = 1950 (mouth-drape GC FALL [1675,1925) + 1 s) in I2 frames @25.
Job (offline, worktree; write a NEW sibling tool shrink_scene_playback.py importing what it can; do NOT edit
extend_scene_playback.py):
1. Modes DRY | APPLY | REVERT, confirm "<MODE> SHRINK". Args {"cue_label", "new_end_frame"}.
2. DRY lists EVERYTHING past the new end in the cue sequence (sections, keys, camera cuts, audio, markers, sub-sequences,
   events) and in the Master for the following segments (Passage keys are ABSOLUTE: list multi-key channels that would be
   displaced; the extend tool's key-carry logic is the precedent).
3. APPLY: set_playback_end; trim (never delete) sections/cuts crossing the new end to end there; sections starting after it
   are DEACTIVATED (recorded); camera-cut coverage of [start, new_end) must be gap-free; Rebuild managed Master (library call,
   as the extend tool); key carry as the extend tool; save exactly cue sequence + Master (+ Show only if the rebuild dirtied
   it); read back segments: earlier ones unchanged, later ones shifted by exactly -delta; SavedMasterMatchesShow later.
4. REVERT restores range, section ends/actives, carried keys from the record.
5. Harness with +/- controls (crossing section trimmed; later section deactivated; cut gap refused; key-carry delta).
