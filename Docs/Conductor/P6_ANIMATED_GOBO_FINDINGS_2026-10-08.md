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
- Offline harness: **57 passed / 0 failed**, including positive plan/state controls and negative range, path, label,
  dirty-package, drift, and safety controls. Existing flipbook pipeline self-test: **8 / 8 passed**, including its
  negative no-flat-field control. **[measured: `Tools/ShadowGobo/P6_TestBird/offline_harness_report.json:1-8`,
  `Tools/ShadowGobo/P6_TestBird/upstream_pipeline_selftest_report.json:1-16`; harness controls at
  `Saved/CodexConductor/test_animated_gobo_offline.py:59-167`]**

## Conductor run order (not run here)

1. Review `Tools/ShadowGobo/P6_TestBird/preview.gif`.
2. Copy this example to `Saved/CodexConductor/animated_gobo_args.json`; use one or both exact labels:

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

3. Execute `animated_gobo_request.json`; require `ANIMATED_GOBO_DRY_OK ... apply_ready=1`. **[inferred until run]**
4. Change mode/confirm to `APPLY` / `APPLY ANIMATED_GOBO`, keep the DRY run id/args, execute; require
   `ANIMATED_GOBO_APPLY_OK_PENDING_VERIFY`. **[inferred until run]**
5. In a **later MCP call**, change mode/confirm to `VERIFY` / `VERIFY ANIMATED_GOBO`; require
   `ANIMATED_GOBO_SUCCESS ... dirty=0`. **[inferred until run]**
6. Render frames 175, ~212, 250 on the curtain and query `r.LightFunctionAtlas`,
   `r.Deferred.UsesLightFunctionAtlas`, `r.VolumetricFog.LightFunction`, and runtime slot size. Check U/V handedness,
   haze, silhouette legibility, and whether both spots match across the sleight. **[inferred acceptance procedure]**
7. Revert only with `REVERT ANIMATED_GOBO DELETE CREATED ASSETS`; the tool backs up sequence and created packages before
   deletion. **[declaration-proven: `animated_gobo.py:693-756`]**

## Open questions for Gary / conductor

1. Are visible rods/hands wanted in the projected performance? The test intentionally includes a rod. **[inferred
   creative choice]**
2. Should a 3-second test loop/hold, or should Frame be keyed over the full ~60-second Interaction after real footage
   exists? **[inferred creative/timing choice]**
3. Is the LF-atlas softness acceptable on the actual velvet at 6-10 m? Only rendered review can decide. **[inferred]**
