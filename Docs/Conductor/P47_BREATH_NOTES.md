# P47 Passage breath — held integration notes

Status: **HELD; not applied, compiled, opened in Unreal, or exercised in PIE.** [measured: `Scripts/patches/cueing_P47_passage_breath.patch`; the patch check recorded below is the only executed integration gate]

Offline evidence at delivery: `git apply --check --whitespace=nowarn` passed in a clean ZIP export of master `ffb0a331576fda3b863ea501a4cc59cd3964ed50`; patch SHA-256 `1f863a4cb4d4d5db5309d083933a6c7bee02843234ad8ac80ff39888f59ae17d`. Static acceptance found all 12 required tokens and zero HUD1/SW1/CueBook-tool overlaps. Four `InfinityStage.CueDirector.Breath*` automation cases contain 27 positive and 5 negative/control assertions; they were authored but not executed because this job forbids compilation. [measured: `Scripts/patches/cueing_P47_passage_breath.patch:1-1276`; declaration-proven test inventory: `Plugins/InfinityStage/Source/InfinityStageTests/Private/InfinityStageBreathTests.cpp:6-126`]

## What to tune

- `BreathAudio.RampSeconds` (3.0 s), `PitchFloor` (0.5), `VolumeFloor` (0), `EaseExponent` (2.0), and `StrangePitchDip` (0.08) are Gary-facing defaults on the existing Transport component. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTransportController.h:53-69`]
- `bAllowBreathInPerformance` defaults true in the existing Cue Director settings and is applied to Transport; set `allow_breath_in_performance = false` only when the live key/marker must be locked out. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageCueSheet.h:100`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageCueSheet.cpp:329-332,377-378`]
- P toggles breath; RIGHT/GO exits it. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowGameMode.cpp:83,122,185-191`]

## Audio boundary

- The current managed music is a Sequencer track. Pausing its owning Master stops that source immediately, so it cannot audibly wind down while paused. The patch still computes the pure pitch/volume envelope and applies it to the existing Show Trims `MusicSoundClass` override; this becomes audible only after the music assets are routed to that independently controlled class/source. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:3075-3096`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowTrims.cpp:93-101,134-154`; inferred: content routing is not verified offline]
- Sequencer audio tracks stop with the paused Master. World-placed looping audio is not stopped by the breath path; the breath mix changes Music only and leaves the separate Ambience SoundClass at pitch 1.0. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageShowTrims.h:81-87`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowTrims.cpp:153-159`; inferred: which production ambience assets are world-placed was not inspectable from source]

## Integration and PIE order

1. Apply `Scripts/patches/cueing_P47_passage_breath.patch` in the designated C++ integration session after the required `Backups/PreBreath-<run>` snapshot. Do **not** also apply `cueing_GO_BREATH_annotation.patch`; it deliberately rejects BREATH and is superseded. [declaration-proven: `Scripts/patches/cueing_GO_BREATH_annotation.patch:9-14`]
2. In `Tools/CueBook/unreal/go_markers_sync.py`, remove the BREATH skip at lines 118-121 and add `BREATH` to `GO_RE` at line 51 so read-back recognizes the mode. This job intentionally does not edit that tool. [declaration-proven: `Tools/CueBook/unreal/go_markers_sync.py:51,118-121`]
3. Build, prove a new UTF-16 `INFINITY_BREATH_BEGIN` literal in the linked DLL, then run `InfinityStage.CueDirector.Breath*` plus the full suite. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1859`; `Plugins/InfinityStage/Source/InfinityStageTests/Private/InfinityStageBreathTests.cpp:6-124`]
4. In PIE enter a Passage, press P, and verify: Master frame/camera distance stay fixed; wings, underway gusts, squeaks, movers and bulb flicker continue; no later gust triggers; world ambience continues. Press RIGHT and verify playback resumes from the same Master frame and the mix rises over the configured ramp. [inferred: designed by `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:1330-1545,1885-1926`; live verification requires the prohibited build/PIE step]
5. Negative controls: P in a Scene and Interaction must report `BreathNotAllowed`; fast-forward, scrub, Next/Previous, and direct segment jumps must clear breath before moving. [declaration-proven: `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1524,1602,1789-1814,1953-1984,2069-2103`; inferred: live behavior remains unmeasured]

> **HELD (Cueing, 9 Oct):** Gary chose the AUTHORED breath (finishing touches P36/P45), not this live transport
> BREATH. Out of every build unless Gary explicitly asks for a live breath. Conflicts with
> Scripts/patches/cueing_GO_BREATH_annotation.patch (both edit ParseMarkerLabel).
