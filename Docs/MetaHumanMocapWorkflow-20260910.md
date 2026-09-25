# Recorded video to MetaHuman animation — 10 September 2026

This guide covers Gary's shore/clam and Pigeon/schoolchildren recordings. It is a workflow guide and file-format audit, not evidence that animation has been solved or accepted.

## Confirmed starting point

- Active project: `E:\PussStage\PussStage.uproject`, associated with UE 5.8.
- Installed engine: `D:\Unreal Engine\UE_5.8`. The initial audit found 5.8.1; the later 10 September troubleshooting check finds **5.8.2**, changelist 56702186, matching the latest PussStage startup log.
- Source folder supplied by Gary: `G:\Shared drives\GZZ Studio Drive\Projects\2026. SHS 3 Evenings\mocap\mocap vids\260910 gary`.
- Eight MOV files, all carrying H.264 (`avc1`) video with encoded dimensions 1920 × 1080 and average frame rate approximately 29.997 fps. Sample timing varies slightly. Display rotation, image quality, framing, motion and audio synchronization have not yet been visually checked.
- **MetaHuman Animator Markerless Motion Capture** is installed at `Engine\Plugins\Marketplace\MetaHumanBodyTracker_5.8\MetaHumanBodyTracker.uplugin`; its internal name is `MetaHumanBodyTracker`. An earlier check found it disabled. The subsequent Editor session and full batch now have it enabled and loaded, confirmed through MCP and `PussStage_2.log`.
- Live Link Hub is present at `D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\LiveLinkHub.exe`.

| Original filename | Video-track duration | Intended group from filename |
| --- | ---: | --- |
| `shoreguy1.mov` | 87.877 s | Shore / clam |
| `shoreguy12.mov` | 87.977 s | Shore / clam |
| `shoreguy3.mov` | 88.310 s | Shore / clam |
| `shoreguy4.mov` | 118.678 s | Shore / clam |
| `shoreguy5.mov` | 86.442 s | Shore / clam |
| `shoreguy6.mov` | 91.443 s | Shore / clam |
| `child1.mov` | 205.753 s | Pigeon / schoolchildren |
| `child2.mov` | 180.485 s | Pigeon / schoolchildren |

Keep the original names, including `shoreguy12.mov`. The filenames have not been interpreted as specific actions or characters. Metadata was read directly from the MOV headers; source files were not modified.

## The route to use

**Video → Capture Data → MetaHuman Performance → Animation Sequence → character in a Level Sequence.**

The video contains a performance. The solver estimates the skeleton's motion. The MetaHuman supplies the character's appearance and rig. An Animation Sequence stores reusable movement; a Level Sequence places that movement, the character, cameras and sound on a scene timeline.

UE 5.8 adds single-camera body capture through the **MetaHuman Animator Markerless Motion Capture** plugin. It supports body-only or combined face/body processing on Windows, locally. Epic labels it experimental, so first prove a short representative section before processing the entire collection. See [Epic's workflow overview](https://dev.epicgames.com/documentation/metahuman/metahuman-animation-from-mono-video-capture-in-unreal-engine).

## 1. Prepare the tools and a preview character

1. Add Epic's free [MetaHuman Animator Markerless Motion Capture plugin](https://www.fab.com/listings/4095b8e0-3eff-44f1-acb4-cb40b99228b9) to your Fab library, then use the Epic Games Launcher to install it to UE 5.8.
2. In Unreal's **Edit → Plugins**, enable **MetaHuman Animator**, **MetaHuman Animator Markerless Motion Capture**, and **Capture Manager Editor**. Save affected work before the required Editor restart. Enable MetaHuman Creator if creating a preview character.
3. Use an existing assembled MetaHuman if available. Otherwise create a MetaHuman Character asset, choose a preset, download its textures, create the full rig and assemble it. A temporary character is sufficient to assess a performance; it need not look like Gary or the final cast.
4. Check that the project uses DirectX 12 before solving. Epic's recommended hardware includes 32 GB RAM and a GPU with at least 8 GB VRAM; actual memory demand depends on footage settings and duration.

References: [Plugin setup](https://dev.epicgames.com/documentation/metahuman/getting-started-with-metahuman-animator?lang=en-US), [preview character creation](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-01-import-your-footage-in-unreal-engine), [hardware](https://dev.epicgames.com/documentation/metahuman/metahuman-hardware-requirements-in-unreal-engine).

For PussStage authoring, follow `CodexUnrealMCPRunbook.md` before automation. Back up before changing Show data, save only affected assets, and keep character performance in the Scene sequence. A plugin installation or restart has not been performed by this audit.

## 2. Ingest one shore take

Use `shoreguy1.mov` as the first candidate, subject to viewing it. Keep originals on Drive and use local working storage for ingest and generated media, checking available space first.

In Unreal, open **Tools → Live Link Hub**. Switch its upper-left selector to **Capture Manager**. Under **Data Devices**, choose **Add → Mono Video Ingest**, then point the source path at the video folder. Select the take, **Add to Queue**, and **Start**. Ingest creates the Capture Data asset that the solver needs; importing a video as a media texture alone does not create animation.

The default transcoder uses Windows Media Framework. If MOV decoding or frame-rate detection fails, Live Link Hub supports **Settings → Use Third Party Encoder** with an `ffmpeg.exe` path. FFmpeg was not found on PATH or in the checked engine/runtime bundles; this does not establish whether another copy is installed elsewhere.

Reference: [Import Your Footage](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-01-import-your-footage-in-unreal-engine).

Do not convert the original files in place. Their slightly variable timing is a reason to verify ingest duration and synchronization, not evidence that the takes are unusable. If normalization is needed, create constant-frame-rate working copies that preserve elapsed time.

## 3. Solve a short section and export

Create **MetaHuman → MetaHuman Performance** in the Content Browser. Assign the ingested **Footage Capture Data**.

**Check this before turning facial tracking off:** Body Tracking must be available in the Performance asset's Processing Parameters. If it is missing, open **Edit → Plugins**, search **Markerless**, enable **MetaHuman Animator Markerless Motion Capture**, save affected work, and restart Unreal. Installing the plugin through Fab does not by itself enable it in PussStage. Reopen the Performance asset after restart. If the option is still absent, verify that the asset uses mono-video input and clear any Details-panel search filter before checking the plugin startup log.

If Facial Tracking is disabled while body tracking is unavailable or off, **Process can become grey because no tracking path is enabled**. Re-enabling Facial Tracking restores the face path only; it does not enable body capture. For the initial body test, once the body option is available:

- Enable **Body Tracking**.
- Then disable **Facial Tracking**.
- Set **Head Movement Mode** to **Disable**, as specified in Epic's body-only setup.
- Set the **Visualization Object** to the preview MetaHuman where supported.
- Select a useful 10–20-second timeline range and click **Process**.

Watch the result before exporting. Choose **Export Animation → Existing Skeleton**, selecting the assembled MetaHuman's skeletal mesh in **Target Skeleton or Skeletal Mesh**. This route applies the export retargeting automatically. **Performer Skeleton** instead creates a mesh based on the recorded performer's proportions, useful for later retargeting to another rig.

For a later combined face/body test, enable both tracking options and use **Small Face Detector** and **Small Face Solver**. Face detail in a wide shot still needs visual evaluation.

Reference: [Process and Export Your Animation](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-02-process-and-export-your-animation-in-unreal-engine).

## 4. Play the movement on a body

Create a separate test Level Sequence, place the assembled MetaHuman Blueprint in its level, and add the actor to Sequencer. In this fresh test sequence, remove the automatically added Control Rig tracks that would compete with animation playback. On the **Body** component track, add **Animation** and select the exported Animation Sequence. A combined face/body export is also assigned to the **Face** track.

Preview, scrub and replay. Later, use Control Rig to refine a working copy of the movement while retaining the initial export.

Reference: [Apply Your Animation to a MetaHuman](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-03-apply-your-animation-to-a-metahuman-in-unreal-engine).

## 5. Judge the pilot before processing all eight

### Troubleshooting: moving skeleton overlay, stationary character

The skeleton overlay is displayed separately from the visualization character. A moving overlay is useful solve evidence, but does not by itself verify that the selected mesh receives the animation.

During the later 10 September pilot, Gary reported that the skeleton followed the short take well while the Manny preview remained stationary. `Saved/Logs/PussStage_2.log` records completion of five processing stages and confirms the markerless plugin is loaded. It also reports that `/MetaHumanBodyTracker/SKM_Body` could not load `/MetaHumanCharacter/Body/IdentityTemplate/SKM_Body_DNA` because **MetaHuman Creator was disabled and not mounted**. The referenced asset was confirmed present on disk.

Gary subsequently confirmed that the selected Visualization Object is **`SK_Mannequin`**. This is a mannequin target rather than an assembled MetaHuman; displaying it does not establish that the captured motion has been retargeted to its rig.

First enable **MetaHuman Creator** in Edit → Plugins, save affected work, restart Unreal and reopen the saved Performance asset. This addresses the verified missing dependency; the preview still needs a visual check. Set **Visualization → Visualization Object** to an assembled MetaHuman Blueprint for the intended MetaHuman preview. If none exists, create a preset MetaHuman Character, create its full rig and assemble it to obtain the Blueprint.

Then export the existing short solve to the intended MetaHuman skeletal mesh and verify body playback in a test Level Sequence. Do not repeat the full capture solve solely because a preview mesh is stationary. The same startup log also reports missing old-path post-process/physics dependencies for the project's Manny assets; their causal role in the current preview has not been established.

For each scene, first select a short section containing the action that matters most. Check the source video alongside the animated body:

- Feet stay on the floor when planted; steps and turns retain their intent.
- Knees, hips and shoulders do not flip or drift.
- Hands reach the intended scene object, body part or partner.
- Facing direction and travel make sense in stage coordinates.
- Pausing, seeking and replaying produce consistent results.

For shore/clam, pay particular attention to any crouching, kneeling, folded poses, hand-to-ground contact or interaction with the clam. These are review targets, not claims about what the unseen clips contain. The solver produces the person's motion; animation of the clam, props, clothing and effects still needs scene authoring.

For schoolchildren, Gary's performance can supply the movement, but the final bodies' proportions determine stride length, reach and contacts. Confirm Klara's target assets. MetaHuman targets use the existing-skeleton route; a different rig needs retargeting. Review on the actual child character before accepting the clip.

Epic recommends a stable camera, the complete performer visible including feet, good limb/background contrast, and minimal occlusion. It recommends 60 fps capture, but this guide does not treat the existing approximately 30 fps recordings as automatically unsuitable. See [Video Capture Guidelines](https://dev.epicgames.com/documentation/metahuman/metahuman-animator-video-capture-guidelines-in-unreal-engine).

## 6. Organize and hand off the accepted animation

Use one record per useful performance excerpt: original filename, source in/out times, intended character/action, target skeletal mesh, solve settings, exported animation path, whether travel is retained, and any cleanup still needed. Distinguish raw exports from cleaned versions, for example `AS_ShoreGuy1_Body_RAW` and `AS_ShoreGuy1_Body_CLEAN_v01`.

For PussStage, the [Scene delivery contract](SceneDeliveryContract.md) requires **25 fps** display rate and **24000** tick resolution. Preserve the source performance's duration when evaluating on this timeline; do not relabel 30 source frames as 25, which would slow the action. Choose deliberately whether a clip supplies travel or the scene moves its actor; avoid applying the same travel twice.

Character animation belongs in each Scene's own Level Sequence or its performance subsequence. The managed Master is rebuilt and is not the place to author the performances. The delivered Scene's Camera Cut remains at its top level.

Klara should receive the agreed animation assets with their skeleton/character dependencies and a preview sequence. If she works in another Unreal project, use Unreal's **Asset Actions → Migrate** dependency workflow rather than copying isolated `.uasset` files. See [Klara's setup and handoff guide](KlaraDioramaLevelSetup.md). No message or files have been sent to Klara by this task.

## Batch workflow after the pilot succeeds

There are two batch stages: **ingest** converts the videos into Footage Capture Data; **solve and export** turns those assets into reusable animation. Capture Manager already supplies an ingest jobs queue. Multiple takes can be added before clicking Start. Solving and exporting can then be automated through Unreal's Python or Blueprint APIs. See [Epic's automation overview](https://dev.epicgames.com/documentation/metahuman/scripting-and-automating-metahuman-animator-in-unreal-engine) and [mono-footage solve/export workflow](https://dev.epicgames.com/documentation/metahuman/process-and-export-metahuman-animation-with-blueprints-in-unreal-engine).

For these eight takes, the recommended implementation is a project Python queue launched and monitored through **MCP → ExecuteProjectPythonFile** in the existing Editor. MCP sends the commands; Unreal's MetaHuman tools perform the solve. The same Python logic could later support an Editor Utility Widget for a visible queue and retry controls.

The proposed queue should:

1. Start from the successfully tested body solve/export settings and explicitly selected target skeletal mesh.
2. Record each take's Capture Data asset, intended source range, output name and target character. Frame ranges must be chosen per take, because the recordings have different lengths.
3. Create or configure a Performance asset for each take, explicitly enabling body tracking and setting face/head options to match the tested setup.
4. Process one take at a time, export a raw Animation Sequence, save the affected assets and verify the saved output before marking that take complete.
5. Report queued, processing, exported or failed status per take. A rerun should resume verified work and retry failures without silently overwriting cleaned animation.

For an interactive Editor, use completion callbacks and separate progress checks so that a single MCP request does not need to remain open for the whole collection. The executor's success marker alone does not prove that asynchronous processing finished. Review the rendered results before moving them into Scene sequences.

The installed engine includes `process_monocular_performance.py` and `export_performance.py` under `Engine/Plugins/MetaHuman/MetaHumanAnimator/Content/Python`. They are references to adapt: the inspected monocular example does not configure body tracking, and the export example explicitly targets the face archetype skeleton. They are not a ready-to-run body batch unchanged.

A separate Unreal process launched with `-ExecutePythonScript` is another supported automation approach. For PussStage, use it only with the interactive project closed, or against a separate processing project. Body-solve operation in such a batch process has not been verified here; do not assume the project's unrelated `-NullRHI` test command is suitable for GPU motion processing.

The batch runner was implemented and launched through MCP on 10 September after Gary approved the short skeleton result. See the automatically updated [batch report](MocapBatch-20260910.md). It creates new full-length assets, retains `Shore1`, and reloads saved results for verification. The input copies omit shorter audio tracks solely to prevent audio from trimming the body-only video processing range; originals are retained.

## First practical milestone

One short shore performance and one short schoolchild performance visibly playing on representative MetaHuman bodies, then saved and reopened successfully. Only after that should the full takes be processed and cleaned for their Scene sequences.

The first skeleton-only test was accepted by Gary, who then authorized the full eight-take batch using those settings. Ingest and plugin setup are complete. The [live batch report](MocapBatch-20260910.md) records solve, export and saved-package verification progress. Visual review of the full performances on the final characters, cleanup and Scene integration remain separate next steps.
