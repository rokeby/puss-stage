# P47 — Passage "breath" mode as a HELD C++ patch (Cueing stream; offline, no build)

Read first: `_house_rules.md` (all, rule 9 included); `Docs/Conductor/PASSAGE_BREATH_PAUSE_DESIGN_2026-10-09.md`
(option A is this job); `Scripts/patches/` README habits (held patches, CRLF via `git apply`); the transport
(`Plugins/InfinityStage/Source/InfinityStage/{Public,Private}/InfinityStageTransportController.*`: GO holds, vamps,
fast-forward, `SetManagedMasterAudioMuted`), the Passage evaluation (`InfinityStagePassageActor.cpp` around
:1288-1420 mechanisms/squeaks and :1840-2010 lights/movers/bulbs), `InfinityStageMechanismSound.*`,
`InfinityStageShowGameMode.cpp` (keys live in `InfinityStageShowKeys`, with a no-duplicates test).

Gary, 9 Oct: "It would be really nice to be able for Puss to pause during a passage, and for the music to wind down,
slow down, de-pitch in a strange sort of way. And so Puss can look around and all we actually hear is the ambient sound
… The wings should continue to squeak and shatter … [if they stopped] it would feel like some weird time travel gag."

## Build (offline; you cannot compile, so design for reviewability)

1. **Transport BREATH state** (`UInfinityStageTransportController`): `BeginBreath()` / `EndBreath()` /
   `IsBreathing()`; only inside a Passage (refuse in Scenes/Interactions with a logged reason, result code like the
   interlock's); entering pauses the Master player exactly as a pause does, starts a breath clock (world real time,
   NOT dilated by play rate), and exiting resumes from the same Master frame. Fast-forward, scrub and segment jumps
   end the breath first. Never active in Performance mode unless a `bAllowBreathInPerformance` setting (default true:
   Gary wants it live) says otherwise; put that in the existing settings struct, not a new file.
2. **Breath clock into Passage evaluation:** `PhaseSeconds = ShowSeconds + BreathElapsed` for mechanism phase / rate
   integrals, gust completion (gusts already under way finish; no new CameraGust fires because the camera distance is
   frozen), squeak stepping (`ShowDeltaSeconds` from the breath clock while breathing), bulb flicker. Route position
   and camera distance stay frozen. Outside a breath every value must be bit-identical to today (prove it in tests).
3. **Music wind-down:** a small `FInfinityBreathAudio` ramp (pure: time → pitch, volume) applied to the Master's
   audio while breathing: pitch and volume ramp down over `BreathRampSeconds` (default 3.0) to a floor (pitch 0.5,
   volume 0) with an ease that "de-pitches in a strange way" (args; Gary will tune), then mute; on exit ramp back up
   over the same time. Implement on whatever the transport already controls (cite how `SetManagedMasterAudioMuted`
   works; if Sequencer audio cannot be pitch-ramped while paused, say so and implement the volume ramp + a
   documented hook for a future Music SoundClass, the deferred content step).
4. **Ambience is NOT stopped:** document which current ambience sources would stop with the Master (Sequencer audio
   tracks) and which keep playing; add nothing that stops world-placed audio.
5. **Input:** a key to toggle breath in PIE via `InfinityStageShowKeys` (suggest `P` = "pause/breath"; check every
   bound key and the existing no-duplicates test; extend that test). A GO (RIGHT) while breathing ends the breath.
6. **Hooks for the Cue Book:** GO markers labelled `GO <n> BREATH …` are currently NOT written by
   `Tools/CueBook/unreal/go_markers_sync.py` (it skips BREATH). Add transport parsing of `BREATH` in
   `InfinityStageGoCues::ParseMarkerLabel` as a mode that, when crossed, begins a breath (in Passages only), and note
   the one-line change in go_markers_sync to stop skipping it. Do not edit go_markers_sync.

## Deliverables

- `Scripts/patches/cueing_P47_passage_breath.patch`, made against current master, `git apply --check` clean.
- Automation tests (in the patch) in `InfinityStage.CueDirector.Breath*`: pure ramp table; a fake-clock test proving
  mechanism phase advances while the Master frame is frozen and is bit-identical outside a breath (negative control);
  refusal outside Passages; BREATH marker parse (positive) and garbage (negative); key test extended.
- A short `Docs/Conductor/P47_BREATH_NOTES.md`: what to tune, what cannot work without the Music SoundClass, and the
  order to try it in PIE after a build.

## Do not

Compile, start Unreal, MCP, Blender. Do not change behaviour outside a breath. Do not touch the surtitles branch,
SW1 or HUD1 (`Scripts/patches/cueing_HUD1_holding_at_go.patch` touches DirectorHud: keep clear of FormatLines).
If git cannot commit (sandbox index.lock), leave the files and list them.
