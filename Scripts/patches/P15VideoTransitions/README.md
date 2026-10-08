# P15 held runtime patch

Status: **HELD — not applied, not compiled, not opened in Unreal.**

This bundle proposes an auto-created `UTickableWorldSubsystem` so no Show Asset
or level mutation is needed. Copy the two source files into the InfinityStage
module and apply `InfinityStage.Build.cs.patch` only in a designated C++
integration session after taking the required `Backups/Pre<Thing>-<run>`
snapshot.

The subsystem reads `DerivedAssets/P15VideoTransitions/placeholder_current.json`,
finds the one existing `AInfinityStageShowRoot`, and treats its Transport/Master
playhead as the only clock. A Scene segment displays video; Passage and Sequence
(Interaction) segments do not. Entry, jumps, and scrubs seek from absolute Master
frame to Scene-local media frame. The view stays black while media is missing,
opening, or outside half a frame of the requested time.

Audio ownership is exclusive: `ue_muxed` enables the MediaSound component and
uses the muxed file; `desk` uses the video-only file and never enables UE media
audio. `fit` is the safe default for unknown LED geometry; the shared offline
display profile remains the authority for Game/MRQ output dimensions.

Required live gates before merge:

1. Compile Development Editor and packaged target.
2. Read the registry from a non-editor packaged build.
3. Observe Passage -> Scene frame 0 without a flash or duplicate audio.
4. Exercise direct jump, held pause, scrub, loop wrap, missing file, and Scene ->
   Interaction. Confirm black fallback and `P15_VIDEO_*` log markers.
5. Test the chosen LED pixel map and Gary-approved fit/fill policy.

