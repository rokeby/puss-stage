# Cueing build A: held patches for review (4 Oct 2026)

**What this is.** Three held patches, written in the worktree `E:\PussStage_cueing` (branch `cueing/build-a`). The main tree is not touched.

**Status.** None of this has been compiled or run. Every behaviour below is designed, not measured, until the build window.

**Patch check.** At 5556beb, `git apply --check` passed for each patch on its own and for all three together, applied in the order A1 → A2 → A3. A3 reads `PassageSettings.Choreography`, which A2 adds, so A3 depends on A2.

**Tiers used below:**
- **[decl]** — a declaration in a UE 5.8 header (`D:\Unreal Engine\UE_5.8\Engine\Source\Runtime\…`) or in plugin source.
- **[inf]** — inferred, and not measured.

**Applying them in the main tree (build window only):**

```
git apply Scripts/patches/cueing_A1_attachment_binding.patch Scripts/patches/cueing_A2_choreo_nest.patch Scripts/patches/cueing_A3_go_holds_ff_mute.patch
```

## A1. Attachment binding and capture guard (`cueing_A1_attachment_binding.patch`)

**Files:**
- New: `IS/Public/InfinityStageAttachmentBinding.h`, `IS/Private/InfinityStageAttachmentBinding.cpp`, `IST/InfinityStageAttachmentBindingTests.cpp`.
- Changed:
  - `ISE/Private/InfinityStageSequencerBridge.h/.cpp`: adds `CollectAnimatedInOpenSequencers`.
  - `ISE/Private/InfinityStageEditorModule.cpp`: the capture guard.

**The binding.** `UInfinityStageAttachmentBinding : UMovieSceneCustomBinding` resolves an actor by its tag `InfinityStage.Attachment.<cue>|<att>`. That tag is minted at `InfinityStagePassageActor.cpp:967-970` [decl].

**The cache.**
- It is kept per world.
- A stale entry triggers one scan of `AInfinityStagePassageActor::ManagedAttachmentActors` (`InfinityStagePassageActor.h:100`) [decl]. It never iterates the whole world.
- A missing tag is scanned at most once per `GFrameCounter`.
- `GetScanCount()` exposes the scan counter (conductor's note).
- Dead PIE worlds are purged once the cache holds more than 8 worlds.

**The capture guard** meets the conductor's condition: hand edits are still written, and keyed values are not.
- **Property edits** (`HandleObjectPropertyChanged`):
  1. Capture runs as before.
  2. If an open Sequencer binds the lamp, each *animated* property (read from the binding's property tracks and those of its child component bindings) is put back to the Show's authored value.
  3. Every other setting is written, so a hand edit to an un-keyed setting reaches the Show.
  4. An animated property with no known mapping → **nothing** is written, and `INFINITY_CAPTURE_SKIPPED_SEQUENCER unmapped=…` is logged.
  5. The relative transform is not written if a transform track animates the lamp.
- **Gizmo moves** (`HandleActorsMoved`) are skipped **only** when a transform track animates the lamp.
- **No open Sequencer binds the lamp:** the guard does nothing, and behaviour is identical to today.

**Engine calls:**
- `UMovieSceneCustomBinding::ResolveBinding / SupportsBindingCreationFromObject / CreateNewCustomBinding / GetBoundObjectClass / SupportsConversionFromBinding / CreateCustomBindingFromBinding / GetBindingTypePrettyName / GetDesiredBindingName / GetCustomBindingPriority`, `BaseCustomPriority` [decl, `MovieScene/Public/Bindings/MovieSceneCustomBinding.h:59-170`].
- `FMovieSceneBindingResolveParams::Context` [decl, `MovieSceneBindingReferences.h:46-63`].
- `FMovieSceneBindingResolveResult::Objects` [decl, `MovieSceneCustomBinding.h:26-37`].
- `UMovieSceneSequence::GetBindingReferences()` [decl, `MovieSceneSequence.h:97,102`].
- `FMovieSceneBindingReferences::GetAllReferences / AddBinding(Guid, CustomBinding)` and `FMovieSceneBindingReference::ID / CustomBinding` [decl, `MovieSceneBindingReferences.h`].
- `UMovieScene::GetTracks` (`:706`), `FindBinding` (`:733/741`), `GetPossessableCount/GetPossessable` (`:503/496`), `AddPossessable` (`:452`), `FindPossessable` (`:480`), and `AddTrack<T>(Guid)` (`:540`) [decl, `MovieScene.h`].
- `FMovieScenePossessable::GetParent` (`:153`) and `SetParent(Guid, Owner)` (`:166`) [decl].
- `FMovieSceneBinding::GetTracks` [decl, `MovieSceneBinding.h:118`].
- `UMovieScenePropertyTrack::GetPropertyName / SetPropertyNameAndPath` [decl, `MovieSceneTracks/Public/Tracks/MovieScenePropertyTrack.h:83,80`].
- `UMovieSceneSubTrack::AddSequence` [decl, `MovieSceneSubTrack.h:46`].
- `UMovieSceneSubSection::GetSequence` [decl, `MovieSceneSubSection.h:111`].
- `ISequencer::GetRootMovieSceneSequence` [decl, already used at `InfinityStageSequencerBridge.cpp:56`].

**Inferred behaviour, to measure in the window:**
- Sequencer calls our `ResolveBinding` for bindings inside **nested** sequences, in both the editor and PIE [inf].
- Dragging a stage lamp into Sequencer picks this binding type (`BaseCustomPriority`, `SupportsBindingCreationFromObject`). The fallback is the Sequencer right-click menu "Change binding type", whose menu builder is declared at `LevelSequenceEditorSubsystem.h:367` [decl], or the Python call `ConvertToCustomBinding` (`:177`) [decl].
- Sequencer *evaluation* does not broadcast `OnObjectPropertyChanged`, so the guard only ever sees hand edits [inf].

**Editor worlds.** On the conductor's "negative control on editor worlds": this binding is meant to resolve in editor worlds, because that is what lets Gary see his keys while directing. The editor-world trap here is the capture write-back. `Capture.KeyedValueKeptOutOfShow` covers it, with a positive control (a hand edit is written) and two negative controls (an unbound lamp is untouched, and an unmapped key refuses the capture).

**Tests:**
- `InfinityStage.Cueing.Binding.ResolvesByTagAcrossRespawn`: it counts scans. The first resolve costs 1 scan, a cached resolve costs 0, and a stale entry costs exactly 1.
- `InfinityStage.Cueing.Binding.SurvivesRealMaterialize`: it materializes the Passage twice and checks that the tag resolves to the new actor.
- `InfinityStage.Cueing.Binding.CreatedOnlyForAttachments`.
- `InfinityStage.Cueing.Binding.SequenceBindsTagFindsNested`.
- `InfinityStage.Cueing.Capture.KeyedValueKeptOutOfShow`.

## A2. Choreo nesting (`cueing_A2_choreo_nest.patch`)

**Files:**
- New: `IS/Public/MovieSceneInfinityChoreoTrack.h`, `IS/Private/MovieSceneInfinityChoreoTrack.cpp`, `ISE/Private/InfinityStageChoreoTests.cpp`.
- Changed:
  - `IS/Public/InfinityStageTypes.h`: adds `FInfinityPassageSettings::Choreography`, a `TSoftObjectPtr<ULevelSequence>`.
  - `ISE/Private/InfinityStageSequenceBuilderLibrary.cpp`: a new managed block after the Scene block.
  - `ISE/Private/InfinityStagePassageResizeLibrary.cpp`: `IsManagedTrackForShow` now counts the Choreo track.

**What the rebuild does.**
- It writes a **separate** `UMovieSceneInfinityChoreoTrack`. It is deliberately not the Scene track, because the handoff, cut-binding and fit checks read Scene sections as Scene cues.
- Each section is keyed by the Passage's GUID and spans the segment, so the Choreo's 0:00 is the Passage start (Gary, Q2).
- If no Passage has a Choreo, no track is created at all.
- If a Choreo is shorter than its Passage, the rebuild logs a warning, `INFINITY_CHOREO_SHORT`. It never edits the Choreo asset.

**Bit-identical with no Choreo:**
- `InfinityStage.Cueing.Choreo.AbsentLeavesMasterUnchanged` checks that no Choreo track exists and that the track list keeps the same objects in the same order across rebuilds.
- The existing `ManagedMasterIdempotence` test also covers it.
- To confirm in the build: `PassageKeysFollowSection`, `SavedMasterMatchesShow` and `SceneCutBindingsResolve` stay green. The saved Show has no Choreos yet, so the A2 code path is skipped entirely [inf until run].

**Test:** `InfinityStage.Cueing.Choreo.FollowsRetime`. A Scene grows by 10 s; the Choreo section is the same object and has moved by +10 s. The control is an absolute sub-section, which does **not** move.

**Engine calls.** `UMovieSceneSubSection::SetSequence/SetRange` and `UMovieScene::FindTrack/AddTrack` are the same calls the Scene block already makes (`SequenceBuilderLibrary.cpp:312-365`) [decl].

## A3. GO holds and fast-forward muting all audio (`cueing_A3_go_holds_ff_mute.patch`)

**Files:** `IS/Public/InfinityStageTransportController.h`, `IS/Private/InfinityStageTransportController.cpp`, `IS/Private/InfinityStageShowGameMode.cpp`, and the new `IST/InfinityStageGoCueTests.cpp`.

**GO markers.**
- A GO marker is a marked frame labelled `GO <number> [HOLD|PASS] <label>`.
- They are collected from Scene/Sequence cue sequences, where the default mode is HOLD, and from Passage Choreos, where the default is PASS.
- Offsets are measured from the playback start, the way vamps and handoffs are.
- They are stored in `GoCues` in frame order.

**`FInfinityGoHoldState`** is pure logic:
- A hold arms only when forward playback crosses its frame.
- Navigation never arms one.
- A released hold re-arms once the playhead is back before it.

**On a hold:** fast-forward stops, the player pauses, the playhead jumps to the GO frame, and `INFINITY_GO_HOLD` is logged. The hold check runs before the vamp check.

**How GO coexists with → and Space.** This is the conductor's question. Right and Space were already bound (`ShowGameMode.cpp:44-47`) [decl].
- **→ with a hold active:** GO. It is the whole gesture, exactly like a vamp release today. Its key-up never becomes an advance or a fast-forward.
- **→ with no hold active:** **unchanged.** A tap steps the shot or advances to the next segment; holding it fast-forwards; inside a vamp it releases the vamp.
- **Space with a hold active:** GO.
- **Space with no hold active:** **unchanged**, i.e. play/pause. The exception is `bSpaceNeverPauses`: when set, Space while playing does nothing and logs it. It defaults to **false**, so rehearsal is unchanged, and Gary can switch it on for performance.
  - Gary asked for "pause only from the Cue Desk". The flag lets that coexist with the conductor's "unchanged without GO markers".
- **With no GO markers at all:** `HandleGoHold` returns at once (`GoCues.IsEmpty()`), and `ReleaseActiveHold()` returns false. Every pre-existing path runs exactly as today. The tests to re-run are the existing vamp, interlock (result=4) and shot-step tests.

**Fast-forward muting.**
- On fast-forward start, every `UMovieSceneAudioTrack` in the Master and its nested sequences (Scene and Choreo audio) is muted. The managed music track keeps its existing path.
- Each track's prior local-mute flag is recorded and restored **exactly**. The same transient `SetLocalEvalDisabled` call the Master path uses is applied in the editor, and `SetEvalDisabled` when packaged [decl, `MovieSceneTrack.h:440-460`].
- Volumes are never written; only the evaluation flag changes. "Restore after the jump" therefore means each flag goes back to what it was.

**Engine calls:**
- `UMovieSceneSequencePlayer::Pause / SetPlaybackPosition / IsPlaying / IsReversed`. `SetPlaybackPosition`, `IsPlaying` and `IsReversed` are already used in this file [decl, by use]. `Pause` is new [inf: standard player API, not re-read today].
- `UMovieSceneTrack::IsLocalEvalDisabled / SetLocalEvalDisabled / IsEvalDisabled / SetEvalDisabled / MarkAsChanged` [decl].

**Inferred behaviour:**
- Pausing and then jumping lands exactly on the GO frame [inf].
- Muting nested tracks takes effect on the next evaluation, as it does for the Master music [inf; the Master-mute mechanism is the one FFV shipped in 467d2c8].

**Tests:**
- `InfinityStage.Cueing.GO.MarkerLabelParses`, with controls: a vamp marker, `GOAT`, and a bare `GO`.
- `InfinityStage.Cueing.GO.HoldArmsReleasesAndReruns`, with controls: paused, a jump over holds, and no markers at all.
