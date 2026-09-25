# Stage Wing Director project handoff

The UE 5.8 `StageWingDirector` plugin is the authoritative editor-preview and
PIE system for the stage. `BP_StageConveyor` is no longer used by preview,
movement, or operator playback.

The complete current guide is:

- `Plugins/StageWingDirector/Docs/Authoring.md`
- `Plugins/StageWingDirector/README.md`

## Restart and first check

1. Restart Unreal Editor so the newly compiled native plugin loads.
2. Open `StageTest`, then choose **Tools > Stage Wing Director**. The Output Log
   fallback is `StageWingDirector.Open`.
3. Select `StageWingDirector_Main` and click **Use Selected Director**.
4. Select a Scene and click **Preview Selected**.
5. Use Right/Left for show GO changes and Page Down/Page Up for direct Scene
   navigation in PIE.

## Current interface

- **Show Order — Scenes** is performance order.
- **Look Cues within Scene** recall reusable Wing Sets.
- **Wing Asset Authoring — Sets / Pairs** owns meshes, panel corrections,
  reusable Pair lighting, and companion anchors.
- Drag the central divider to resize the show and asset sides.
- Director / Preview Tools, Camera Viewfinder, and Focused Editor can be
  minimized.
- The Focused Editor heading names the selected Scene, Look Cue, Set, or Pair.

The old setup/migration panel and redundant Show Asset and Director-stage-copy
buttons are removed. Hidden compatibility fields remain in native serialization
only so existing maps and assets continue to load.

## Contained piece and Sequencer flow

Create a Contained Piece Scene and its `StageContainedSceneRig`. Attach its
actors below that rig or add them to **Contained Actors**.

- **Auto-Assign Piece Playback** discovers attached/contained Level Sequence
  Actors, lights, effects, and audio.
- **Add Selected Sequencer** accepts a placed Level Sequence Actor or a Level
  Sequence asset selected in the Content Browser. It creates and attaches an
  actor when necessary and disables Auto Play.
- Prepare stops/rewinds managed playback.
- The curtain/backdrop reveal enables the static set and its lights.
- The next Right/GO starts Sequencer, audio, effects, and the Blueprint playback
  event.
- The following Right/GO closes the contained piece.

This gives a deliberate static reveal before animation begins.

## Moving ground

Click **Create / Select Moving Ground**. Assign the production ground mesh and a
material that adds the R/G channels of a Vector Parameter named
`StageGroundUVOffset` to its Texture Coordinate.

Set **Texture Repeat Distance** to the real-world centimetres represented by one
texture repeat. Choose U or V with **UV Scroll Direction**, negating the axis if
needed. The Director writes the same signed distance used by wing conveyor
travel, Set Piece steps, tunnel draining, and terminal curtain approach, so the
ground illusion follows speed and direction reversals.

## World Partition actors

Actors named `HLOD0_...`, `WorldDataLayers`, and `WorldPartitionMiniMap` belong
to Unreal World Partition. Use Unreal's HLOD delete/rebuild workflow for those.
Use **Remove Generated Rigs** only for Director-owned `WPR_...` preview actors.
