# P6 animated gobo shadow puppetry — UE 5.8 findings and offline delivery

**Status, 8 Oct 2026:** nothing in this delivery was run in Unreal, applied to a package, rendered, or visually
accepted. The editor/MCP/PIE/Blender prohibition was observed. **[measured: this run's command history]** The existing
shoot spec is present at `E:\PussStage\Docs\ShadowPuppetCaptureSpec.md` but is absent from this worktree and from its
tracked history; its worktree status is therefore **UNCLEAR** after checking `git log --all`, `git ls-files`, and
`Docs/`. **[measured]**

## Verdict

**Bench a keyed flipbook Light Function on the existing paired SpotLights first.** It is the only option here that is
both a real light modulation on the 5 x 3 m cloth and deterministic under Sequencer scrub. The new tool keys an MPC
scalar named `Frame`; the material floors that value to a row-major atlas cell. **[declaration-proven:
`Saved/CodexConductor/animated_gobo.py:69-90,415-555`]** The recommendation is **inferred** until Gary sees a rendered
cloth test, because atlas resolution, cone handedness, exposure, cloth folds, and haze are still unmeasured.

For a circular spot just covering 5 m width, the half-angle is about 22.6 degrees at 6 m and 14.0 degrees at 10 m.
**[measured: offline trigonometry]** The delivered 6 x 4 atlas gives 341 px per source frame, about 1.47 cm/pixel over
5 m. **[measured: generated atlas read-back]** If the UE light-function atlas path uses the header's 32 px default slot,
that becomes about 15.6 cm/pixel before filtering. **[declaration-proven default:
`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Renderer/Private/LightFunctionAtlas.h:127-131`; inferred projected
sampling]** Runtime slot size is **UNCLEAR** because the installed source lacks the atlas implementation `.cpp`; query
the cvars during the bench.

## Options judged for this show

### 1. SpotLight + Light Function flipbook — recommended bench

- A SpotLight light function receives projector-style 0..1 cone UVs. **[declaration-proven:
  `D:/Unreal Engine/UE_5.8/Engine/Shaders/Private/LightFunctionCommon.ush:39-50`]** Light functions are allowed on
  non-lightmapped lights and in volumetric fog for Directional, Point, and Spot lights. **[declaration-proven:
  `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Components/LightComponent.h:199-205`]**
- The material is marked atlas-compatible because its graph uses cone UVs, not world position/depth. The engine says
  that flag is the contract for atlas-safe UV manipulation and the fast batched path. **[declaration-proven:
  `D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Public/Materials/Material.h:920-927`]**
- The atlas path is soft/low-resolution by design: its setup header defaults to a 32 px slot and the render shader
  evaluates one sample per atlas pixel; a disabled 4-sample block remains behind `#else`. **[declaration-proven:
  `LightFunctionAtlas.h:127-131`; `Shaders/Private/LightFunctionAtlas/LightFunctionAtlasRender.usf:20-73`]** The
  material exposes both a five-tap `BlurUV` filter and a separate edge-transition `Softness`. **[declaration-proven:
  `Saved/CodexConductor/animated_gobo.py:80-90,454-505`]**
- Light-function fade distance explicitly exists to hide distant aliasing. **[declaration-proven:
  `LightComponent.h:229-234`]** At 6-10 m it should be kept beyond the cloth, then judged by eye. **[inferred]**
- Project settings enable ray tracing, Lumen hardware ray tracing, and VSM. **[declaration-proven:
  `Config/DefaultEngine.ini:18-25`]** Those settings do not turn the gobo into geometry. **[inferred from the LF direct
  lighting path]**

### Lumen GI precision (important correction)

“Light functions do not affect Lumen GI” is safe only if **GI means indirect bounce**. UE 5.8 source proves Lumen's
**direct-light** code samples the light-function atlas and multiplies the diffuse target/shadow factor.
**[declaration-proven: `Shaders/Private/Lumen/LumenSceneDirectLightingStochastic.usf:101-120,1043-1053`]** No matching
light-function reference was found in the installed Lumen indirect/radiance-cache files searched on 8 Oct.
**[measured absence; searched `Engine/Shaders/Private/Lumen` and `Source/Runtime/Renderer`]** Therefore expect the
moving silhouette in direct light, but do **not** promise a matching moving indirect bounce. **[inferred]**

### 2. IES/light profile — reject for animation

An IES profile is a `UTexture2D` subclass carrying a measured angular distribution and brightness. **[declaration-
proven: `Engine/Source/Runtime/Engine/Classes/Engine/TextureLightProfile.h:10-25`]** The light's IES texture property is
an asset reference without `interp`; only `IESBrightnessScale` is interpolatable. **[declaration-proven:
`LightComponent.h:217-227`]** It can shape a static beam, not play 24 silhouettes. **[inferred]**

### 3. Rect Light `SourceTexture` cookie — reject for the puppet, retain for static breakup

`SourceTexture`, its scale, and offset are non-`interp` RectLight properties. **[declaration-proven:
`Engine/Source/Runtime/Engine/Classes/Components/RectLightComponent.h:61-71`]** A RectLight light function is explicitly
unsupported in volumetric fog. **[declaration-proven: `LightComponent.h:199-203`]** This is appropriate for a static
source pattern, not a deterministic animated perspective gobo on the curtain. **[inferred]**

### 4. Projected decal/material on the curtain — viable fallback

A decal owns a `DecalMaterial` and projection size. **[declaration-proven:
`Engine/Source/Runtime/Engine/Classes/Components/DecalComponent.h:23-38,80-86`]** The same atlas/frame maths could be
used in a decal material, giving predictable surface animation on the cloth geometry. **[inferred]** It is not emitted
light, will not pattern the haze, and will read as an image treatment rather than a shadow if lighting/exposure moves.
**[inferred]** Use it if the 32 px LF atlas is visibly unacceptable.

### 5. Real cut-out shadow casters — highest physical fidelity, highest setup cost

Animated opaque/masked puppet meshes between the existing shadow-casting SpotLight and curtain produce actual dynamic
shadows; the existing spot templates are movable and shadow-casting. **[declaration-proven:
`Saved/CodexConductor/shadow_play_spot.py:895-924`]** Sharpness then comes from source radius and puppet/light/cloth
distance, and HWRT/VSM must process moving casters. **[inferred]** This is the strongest visual fallback if Light
Functions are too soft, but it needs authored puppet transforms and a rendered cost test.

## Delivered tool and test asset

- `Saved/CodexConductor/animated_gobo.py`: DRY/APPLY/VERIFY/REVERT, exact confirm strings, clean census, create-only
  material/MPC/texture/MI, named sequence packages only, backup + exclusive record before mutation, exact spot-label
  targeting, independent VERIFY success marker, and recoverable destructive REVERT. **[declaration-proven:
  `animated_gobo.py:51-90,231-295,415-589,590-756`]**
- `Tools/ShadowGobo/P6_TestBird/`: 24 frames, 8 fps, 3 seconds, 2048 atlas, 6 x 4 cells, visible operating rod, plus
  `preview.gif`, `contact.png`, and manifest. **[measured: generator read-back; source
  `Tools/ShadowGobo/make_p6_test_bird_flipbook.py:21-108`]**
- Offline harness (original): **57 passed / 0 failed**, including positive plan/state controls and negative range, path, label,
  dirty-package, drift, and safety controls. Existing flipbook pipeline self-test: **8 / 8 passed**, including its
  negative no-flat-field control. **[measured: `Tools/ShadowGobo/P6_TestBird/offline_harness_report.json:1-8`,
  `Tools/ShadowGobo/P6_TestBird/upstream_pipeline_selftest_report.json:1-16`; harness controls at
  `Saved/CodexConductor/test_animated_gobo_offline.py:59-167`]**

## Fixes after review, 8 Oct (branch `gobo-fixes`; still not run in Unreal)

The 48d30b1 tool would not have worked as delivered:

1. **UE 5.8 has no master-track Python API.** The tool called `get_master_tracks`, `add_master_track` and
   `remove_master_track`. The SequencerScripting plugin has no "master" symbol at all; only `GetTracks`, `AddTrack` and
   `RemoveTrack` exist (`MovieSceneSequenceExtensions.h:49,79,89`), and `MovieScene.h:1424` keeps only
   `MasterTracks_DEPRECATED`. **[declaration-proven]** DRY never called them, so it would have reported
   `apply_ready=1`, and APPLY would then have failed before mutating. **[inferred from the code path]** Fixed: the tool now
   uses `get_tracks`/`add_track`/`remove_track`, and DRY probes all three on the live sequence before anything else.
2. **Key times were in the wrong unit.** `add_scalar_parameter_key` is the raw section UFUNCTION taking an `FFrameNumber`
   (`MovieSceneParameterSection.h:346`) **[declaration-proven]**, so display frames 175/250 would most likely have landed
   as ticks, about 0.01 s into the sequence. **[inferred: the header does not name the unit]** Fixed: keys are display
   frame x (tick resolution / display rate), required to be an exact integer (29.97 fps refuses). They are read back
   through the scripting channel, whose `GetTime` defaults to display rate (`MovieSceneScriptingChannel.h:30`)
   **[declaration-proven]**, so a unit error fails the pre-save read-back. The section range `[start, end+1)` is also
   read back.
3. **The tool could run only once.** The master and MPC were create-only, and there was one global record. Now they are
   shared: they are created on first use, and later runs reuse them after a structural check (light-function domain,
   atlas flag, the exact scalar set, a single `FlipbookAtlas` texture parameter, MPC `Frame`, master referencing the
   MPC). Per-run texture and MI stay create-only. Plans and records live in `animated_gobo_plans/<run_id>.json` and
   `animated_gobo_records/<run_id>.json`. One gobo track per sequence is enforced in DRY. REVERT deletes only what that
   run created, and refuses while later runs still reference it (revert in reverse order).
4. **The last frame flashed.** The end key was `Frames-1`, which gave the last cell 1 of 76 frames. It is now `Frames`,
   so cells get 3-4 frames each and the shader clamps. **[measured: harness F09/F10]**
5. **Speed is reported.** DRY logs `ANIMATED_GOBO_TIMING` when the keyed range plays the flipbook more than 2% off its
   manifest fps, and gives `native_frame_end`. For example, 175-250 at 30 fps plays the 8 fps bird at 1.2x; native ends
   at 265. **[measured: harness F07]**
6. **Blur is bounded by the real gutter.** `BlurUV` above `gutter_px / atlas_px` is refused. The video pipeline's
   default 4 px gutter on a 4096 atlas allows 0.00098. **[measured: harness B13c/B13d]**

Still open: every gobo shares one MPC `Frame`, so two Interactions playing at once would show the same frame
**[inferred; not expected in this show]**. LF-atlas sharpness is unmeasured. Playback end is treated as exclusive
**[inferred]**.

Offline harness after the fixes: **99 passed / 0 failed**. **[measured]**

## Soft border, light-space UVs, atlas variant (8 Oct, branch `gobo-border`; not run in Unreal)

Gary's direction (via Finishing Touches): the light should be large, fill the curtain and have soft edges ("it can be a
rectangle too"), and the gobo should block light inside the beam and "take the boundaries of whatever that light is".

- **New master parameters** (group `03 Border`):
  - `BorderDepth`: 0 = off (default). Outside the image the beam passes, so the lit edge is the beam's own edge.
  - `BorderWidth`: image-width units.
  - `BorderAspect`: width / height.
  - `BorderFeather`: image-width units.
  - With `BorderDepth` at 1, the lit area is a feathered rectangle, black outside, whatever the beam's shape.
- **Scale limit:** for a spot, DRY refuses a `Scale` that would put the border's corners outside the circular cone.
  The limit is `1 / (W * sqrt(1 + 1/A^2))`: 0.7071 for a square, 0.8829 for the 1.88 drape. **[measured: harness
  G13-G16]**
- **`UVCentre` 0.5** is for lights whose light-function UVs are light-space and centred on 0. Non-spot lights fall back
  to `LightVector.xy` (`LightFunctionCommon.ush:41`). **[declaration-proven]** Its use on a RectLight is
  **[inferred, untested]**, and a RectLight light function does not reach volumetric fog (`LightComponent.h:199-203`).
  **[declaration-proven]**
- **`atlas_compatible: false`** builds and uses `M_ShadowGobo_LightFunction_NoAtlas`, created once and shared like the
  other master. The flag "forces all deferred lights to go the fast batched lighting code path"
  (`Material.h:920-925`). **[declaration-proven]** That leaving it off gives full screen-resolution detail is
  **[inferred]**. Live cvars read by Finishing Touches: `r.LightFunctionAtlas.SlotResolution 128`, and
  `r.MegaLights.LightFunctions 1`. **[measured, their run]** If MegaLights handles the spot, the atlas may be used anyway
  **[inferred]**, so judge sharpness on stills.
- **Resolution:** 128 px per slot. At Scale 0.7071 and a 17 m image that is about 90 px across the image, about 19 cm/px.
  **[inferred from the measured cvar]** At Scale 0.883 the cone could narrow from about 21.8 to 17.8 deg at 30 m and give
  about 25% more pixels per metre. **[measured: harness G21 trigonometry]**
- **Pipeline follow-up:** the atlas cells are square, so a 1.88 curtain leaves about 47% of each cell unused. Non-square
  cells would need `make_gobo_flipbook.py` and the shader to carry per-axis cell UVs. **[inferred; not done]**

Harness after the border work: **127 passed / 0 failed**. **[measured]**

## Video to flipbook (exists since 6 Oct)

`Tools/ShadowGobo/make_gobo_flipbook.py` turns a phone take into the atlas, preview GIF, contact sheet and manifest. See
`Docs/ShadowGoboPipeline_2026-10-06.md`. **Dark paper cutouts on a light background are its default polarity** (white
passes, black blocks; no `--invert`). Its self-test passed 8/8 again on 8 Oct, and its manifest plans cleanly in the fixed
tool (6x6 grid, 32 frames, 8 fps, 4 px gutter). **[measured]**

## Conductor run order (not run here)

1. Review `Tools/ShadowGobo/P6_TestBird/preview.gif`.
2. Copy this example to `Saved/CodexConductor/animated_gobo_args.json`, using one or both exact labels. `run_id` is
   required, and DRY and APPLY share it:

```json
{
  "mode": "DRY", "confirm": "DRY ANIMATED_GOBO", "run_id": "AG-I2-TEST-001",
  "sequence": "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips",
  "light_labels": ["Shadow Play Spot (Hangar)", "Shadow Play Spot (Mouth)"],
  "atlas_png": "E:/PussStage/Tools/ShadowGobo/P6_TestBird/T_Gobo_P6_TestBird_6x4.png",
  "manifest": "E:/PussStage/Tools/ShadowGobo/P6_TestBird/manifest.json",
  "mi_path": "/Game/InfinityStage/Lighting/Gobo/MI_ShadowGobo_P6_TestBird",
  "texture_path": "/Game/InfinityStage/Lighting/Gobo/T_Gobo_P6_TestBird_6x4",
  "frame_start": 175, "frame_end": 250,
  "params": {"BlurUV": 0.00075, "Softness": 0.08, "Contrast": 1.35, "Depth": 1.0, "Scale": 1.0, "FlipU": 0.0, "FlipV": 0.0}
}
```

3. Execute `animated_gobo_request.json`. Require `ANIMATED_GOBO_DRY_OK|run=AG-I2-TEST-001|apply_ready=1`, and read the
   `tpf=` and `reuse=` fields and any `ANIMATED_GOBO_TIMING` warning. **[inferred until run]**
4. Change mode/confirm to `APPLY` / `APPLY ANIMATED_GOBO`, keeping the same run_id and args, and execute. Require
   `ANIMATED_GOBO_APPLY_OK_PENDING_VERIFY|run=AG-I2-TEST-001`. **[inferred until run]**
5. In a **later MCP call**, set mode/confirm to `VERIFY` / `VERIFY ANIMATED_GOBO`, a NEW `run_id` (e.g. `AG-I2-TEST-001-V`)
   and `"apply_run": "AG-I2-TEST-001"`. Require `ANIMATED_GOBO_SUCCESS|run=AG-I2-TEST-001-V|... dirty=0`.
   **[inferred until run]**
6. Render frames 175, ~212 and 250 on the curtain, and query `r.LightFunctionAtlas`,
   `r.Deferred.UsesLightFunctionAtlas`, `r.VolumetricFog.LightFunction` and the runtime slot size. Check U/V
   handedness, haze, silhouette legibility, and whether both spots match across the sleight. **[inferred acceptance
   procedure]**
7. Revert only with `REVERT ANIMATED_GOBO DELETE CREATED ASSETS`, a new run_id and `apply_run`. The tool backs up the
   sequence and the created packages before deleting. **[declaration-proven: `run_revert` in `animated_gobo.py`]**

## Open questions for Gary / conductor

1. Are visible rods/hands wanted in the projected performance? The test intentionally includes a rod. **[inferred
   creative choice]**
2. Should a 3-second test loop/hold, or should Frame be keyed over the full ~60-second Interaction after real footage
   exists? **[inferred creative/timing choice]**
3. Is the LF-atlas softness acceptable on the actual velvet at 6-10 m? Only rendered review can decide. **[inferred]**
