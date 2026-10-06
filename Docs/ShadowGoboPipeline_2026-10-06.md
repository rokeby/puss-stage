# Shadow-puppet gobos: iPhone video to a stop-motion light function

**Written:** 6 Oct 2026, offline. **Status:** the offline tool is written and its self-test passes. Nothing has been
built in Unreal and nothing has been filmed.
**For:** Gary's request (6 Oct, ~02:00): "cheap stop motion animated gobos in front of lights that are made from basic
iphone videos of the shadow puppets being puppeted live".
**Builds on:** `Docs/ShadowPuppetCaptureSpec.md` (29 Sep; the shoot spec, still valid) and
`Docs/ScrimFeasibility_2026-09-29.md` (the cloth side).

Every claim carries a tier, per AGENTS.md:
- **[decl]** a header, shader or file we can read (cited);
- **[meas]** run here and read back;
- **[inf]** inferred, with the reason.

---

## The answer

**Use a flipbook atlas in a light-function material.** Drive its frame from a **Material Parameter Collection scalar
keyed by a Sequencer MPC track** in each Interaction sequence. Do not use a MediaTexture.

- **Why the flipbook:** the frame shown is a pure function of a keyed number. Scrubs, jumps, PIE and Movie Render Queue
  therefore all show the same frame at the same time. This needs no C++ and no media framework.
- **The existing spec already ruled media out:** "Media playback is not deterministic under transport scrub and jumps,
  and this show scrubs constantly" (`ShadowPuppetCaptureSpec.md:102-105`).

**Pipeline in one line:** phone video, then `Tools/ShadowGobo/make_gobo_flipbook.py` (ffmpeg crops it, steps it to 6–12
fps and flattens the lighting; one threshold makes a hard mask; the frames are packed into an atlas), then a texture
import, then `M_LF_ShadowGobo` and its MI on the shadow-play spot, then an MPC track in the Interaction sequence.

---

## 1. How Gary should film it

The 29 Sep spec covers the principles: an even screen, exposing for the screen, a locked-off camera, puppet distance, and
rods visible or hidden. These are the phone-specific additions.

**The rig, a backlit sheet:**
1. **The screen.** Use a white cotton sheet, tracing paper or a frosted shower liner. Pull it taut in a frame: wrinkles
   print into the matte as grey lines.
2. **The light goes behind the puppets.** Use one small, hard source, 2–3 m behind them: a bare clear LED bulb, a phone
   torch or a small LED spot.
   - A small source far away gives crisp edges.
   - A big or close source gives soft, doubled edges.
   - The puppets' distance from the sheet is the expressive control. Close to the sheet is sharp and small; farther away
     it is soft and large. This bakes into the plate (spec section 3).
3. **The phone goes in front of the sheet,** on the audience side, square to it.
   - Lock it on a tripod or clamp, at the height of the sheet's centre.
   - Fill the frame with the sheet, with a hand's width of sheet to spare on every side.
   - Mark the frame corners on the sheet with four small tape crosses. The crop then stays identical across takes.
4. **Use a dark room.** No light on the audience side of the sheet.

**The phone settings (iPhone):**
- **HDR Video OFF.** Go to Settings > Camera > Record Video and turn off HDR Video. Also set Formats > Most Compatible
  (H.264).
  - HDR (HLG) footage decodes with the sheet's grey levels remapped. The tool warns when it sees an HLG/PQ transfer [decl:
    `make_gobo_flipbook.py` `plan()`].
- **1080p at 30 fps** is plenty. The atlas cell is at most 512–800 px, so 4K buys nothing but file size.
- **Lock exposure and focus.** Long-press on the sheet until "AE/AF LOCK" shows. Then drag the sun slider down a little,
  so the sheet is bright but not blown out.
  - Without the lock, the phone re-exposes every time a puppet enters, and the sheet's brightness pumps. A single
    threshold is robust to a little of this, but not much.
- **Off:** Action mode, Cinematic, Night mode, and Macro auto-switching.

**Each take:**
1. **First, 2 seconds of EMPTY, lit sheet.** That is the clean plate, `--plate-seconds 2`. It removes the hot spot and
   the dark corners exactly.
2. Say the take number out loud, or show it on a card, then play.
3. Shoot long. The cut happens later, and the spec sized each play at about 13–15 s (spec section 5).
4. Hold still at the start and end of each move. Stop-motion steps read best with clear holds.

**Contrast check on the phone screen:**
- The puppet should be near black.
- The empty sheet should be bright, and even within about a stop from centre to corner (spec section 1).
- The flat field fixes the rest. The self-test's synthetic sheet falls off by more than a stop and comes out clean [meas,
  below].

---

## 2. The tool: `Tools/ShadowGobo/make_gobo_flipbook.py`

```
python Tools/ShadowGobo/make_gobo_flipbook.py --input IMG_0412.MOV --name I1_boy_cat \
       --start 6.0 --duration 15 --crop 1080:1080:420:0 --fps 8 --plate-seconds 2 --plate-start 0
python Tools/ShadowGobo/make_gobo_flipbook.py --input IMG_0412.MOV --dry-run      # the plan only, writes nothing
python Tools/ShadowGobo/make_gobo_flipbook.py --self-test --out <scratch dir>     # synthetic take + controls
```

**What it does, in order:**
1. **ffmpeg** (found on PATH: `ffmpeg 9.0.2` gyan.dev build [meas: `where ffmpeg`]).
   - It decodes the take, crops it (`W:H:X:Y`, or `square` for the centred square), steps it with `fps=` and
     letterboxes it into a white working square.
   - The fps filter both holds and drops frames, so a variable-frame-rate phone file comes out constant [inf: the fps
     filter's documented behaviour].
2. **Flat field.**
   - The clean plate is the median of the empty-sheet seconds, or else the 90th percentile of the take per pixel.
   - It is blurred into a smooth illumination field, and every frame is divided by it.
3. **One threshold for the whole take** (Otsu over every frame, or `--threshold`). A single value means the matte cannot
   flicker from frame to frame.
   - White means light passes (the sheet).
   - Black means blocked (the puppet).
   - `--invert` swaps them, for a "light puppet".
4. **Cleanup.** A 3×3 median removes grain, then `--feather` (default 1 px) softens the edge.
5. **The atlas.**
   - It is exactly `--atlas` px square (default 4096), with the grid auto-sized (the smallest square) or set by
     `--grid CxR`.
   - Frames run row-major from the top-left.
   - Every cell has a `--gutter` (default 4 px) of edge-replicated pixels, so bilinear sampling never bleeds into the
     next frame.
6. **Outputs**, to `DerivedAssets/ShadowGobo/<name>/`, which is git-ignored [decl: `.gitignore:3,11`; `git check-ignore` confirms]:
   - `T_Gobo_<name>_<C>x<R>.png`
   - `preview.gif` at the playback rate (Gary's stop-motion check)
   - `contact.png`
   - `manifest.json`, holding the MI parameters (`GoboCols/Rows/Frames/FPS/GutterUV/CellUV/Loop`), the threshold, the
     flat-field method, and the source's SHA-256
   - optionally `frames/` (per-frame PNGs, for the media comparison only)

**Self-test [meas, 6 Oct]:** `--self-test` returned `GOBO_SELFTEST_OK|checks=8` in about 7 s.
- **The synthetic take:** 640×360 H.264 at 30 fps, 4 s. It has a hot-spot sheet (235 at the centre, about 140 in the
  corners), grain, and a cat head on a rod crossing left to right.

| Check | Result |
| --- | --- |
| Frames = 4 s × 8 fps | 32 = 32 |
| Atlas size | 2048 × 2048 |
| Hard matte | 99.4% of pixels at 0 or 255 |
| Sheet corners read as light after the flat field | mean 251/255 |
| Puppet centroid moves right every frame | yes |
| Puppet area | 4.0–7.0% of the cell |
| Gutters replicate their cell edges | yes |
| **Negative control:** no flat field, fixed threshold 0.75 | the corners go **black** (0/255) |

- The control proves the corner check can fail, and that the flat field is what passes it.
- The first self-test run also failed honestly: a 6×6 grid on 2048 px made a 2046 px atlas. That is fixed. The atlas is
  now always the requested power of two, and the material steps cells by `GoboCellUV`.
- `--dry-run` on the synthetic file printed the plan (crop, the ffmpeg command, a 5×5 grid of 819 px cells at 6 fps) and
  wrote nothing [meas].

**Sizing (frames are the cost; spec section 4):**

| Take | fps | Frames | Atlas | Grid | Cell |
| --- | --- | --- | --- | --- | --- |
| 15 s | 8 | 120 | 4096 | 11×11 | 372 px |
| 15 s | 12 | 180 | 4096 | 14×14 | 292 px |
| 15 s | 12 | 180 | 8192 | 14×14 | 585 px |
| 30 s | 8 | 240 | 8192 | 16×16 | 512 px |

- **Memory.** One-channel BC4 is 0.5 byte/px, so 4096² is 8 MB and 8192² is 32 MB, with no mips [inf: BC4 rate].
- **Detail.** At about 6 m of spot width, 372 px is roughly 1.6 cm per pixel, which is finer than a shadow-play edge
  needs.
- **Limit.** The working square is 768 px, so cells above about 768 px gain nothing.

---

## 3. The material: `M_LF_ShadowGobo` (create-only; not built)

- **Domain:** Light Function.
- **Output:** Emissive, as in `M_LF_StageFlicker` [decl: `Saved/CodexLighting/rebuild_flicker_master.py:8,40`].
- **Shape of the graph:** one Custom node for the frame and cell maths, in the style of `velvet_v2_build.py`.
- **Do not copy the flicker builder's `delete_all_material_expressions` call (`rebuild_flicker_master.py:7`).** The memory rule *ue58-python-material-authoring*
  bans deleting nodes on pre-existing assets. Create a NEW master only.

**Inputs:**
- **UV = TexCoord[0].** For a spot light the engine fills every texcoord with UVs that run from 0 to 1 across the cone,
  "like a projector" [decl: `UE_5.8/Engine/Shaders/Private/LightFunctionCommon.ush:45-50, 61-65`]. No world-position
  maths is needed, and none should be used (see the atlas, section 5).
- **Time = `MPC_ShadowGobo.GoboSeconds`** (new MPC, one scalar). It is keyed by a Sequencer **Material Parameter
  Collection track** [decl: the track class exists, `UE_5.8/Engine/Source/Runtime/MovieSceneTracks/Public/Tracks/MovieSceneMaterialParameterCollectionTrack.h:17`].
  - Nothing in the plugin drives an MPC today. `MaterialParameterCollection` has no hits in
    `Plugins/InfinityStage/Source` [decl: grep 6 Oct].
  - So it is keyed in each Interaction sequence. That is linear keys from 0 at the play start (I1: frame 175,
    `shadow_play_spot.py` header) to the play's length in seconds at the GO HOLD.
- **Passages, if a gobo is ever wanted there:** the Passage actor already computes Master seconds in game worlds
  (`ShowSeconds = MasterFrame / TickResolution`, `InfinityStagePassageActor.cpp:1630`). Setting the same MPC scalar there
  would be about one line of C++. It is NOT needed for the Interactions.
- **Do not use the Time node** for the frame. `M_LF_StageFlicker` uses it [decl: `rebuild_flicker_master.py:18`], so its
  flicker runs on world time and is not scrub-deterministic. That is fine for a flicker and wrong for puppetry.

**Parameters** (from `manifest.json` → `light_function_params`): `GoboCols`, `GoboRows`, `GoboFrames`, `GoboFPS`,
`GoboGutterUV`, `GoboCellUV`, `GoboLoop` (1 loops, 0 holds the last frame), plus:
- `GoboFrameOffset`: where in the take to start;
- `GoboDepth`, 0–1: shadow density, `out = lerp(1, mask, GoboDepth)`, the same form as the flicker's `Depth`;
- `GoboFlipU` and `GoboFlipV`: the cone UV's handedness on screen is [inf], so check it on the bench;
- `GoboScale`: zoom about the centre; outside the frame the value is 1, i.e. light passes.

**The Custom node's maths:**
```
float f = floor(Seconds * FPS) + Offset;
f = (Loop > 0.5) ? fmod(fmod(f, Frames) + Frames, Frames) : clamp(f, 0, Frames - 1);
float col = fmod(f, Cols), row = floor(f / Cols);
float2 uv = (UV - 0.5) / Scale + 0.5;  uv = lerp(uv, 1 - uv, float2(FlipU, FlipV));
float inside = all(uv >= 0) && all(uv <= 1);
uv = saturate(uv) * (1 - 2 * Gutter) + Gutter;          // stay inside the cell's gutter
float2 a = (float2(col, row) + uv) * CellUV;            // CellUV = cell px / atlas px
return lerp(1, lerp(1, Tex.SampleLevel(TexSampler, a, 0).r, inside), Depth);
```

**The texture:**
- Compression Grayscale (BC4), sRGB off, **No Mipmaps**, **Never Stream**, Clamp, Bilinear.
- No mips because the cells would bleed into each other at lower mips.
- Never Stream because the streamer may not see light-function use and could leave the gobo on a blurry low mip
  [inf: light functions are not primitives].

**Where it plugs in:** `shadow_play_spot.py` spawns two matched SpotLights per Interaction ("Hangar" and "Mouth", the twin
pair across the sleight cut) [decl: its header].
- Both take the same gobo MI, so both read the same MPC and stay in frame sync across the cut [inf].
- `LightFunctionMaterial` is a plain `EditAnywhere` property, not `Interp` [decl:
  `UE_5.8/.../Components/LightComponent.h:204-205`]. So it is set on the spawnable template, not keyed.
- Adding it is a small extension to `shadow_play_spot.py` (the Conductor's file; not done here).

---

## 4. Flipbook vs MediaTexture

| | Flipbook + MPC track (recommended) | MediaTexture in the light function |
|---|---|---|
| Can a light function sample it? | Yes: an ordinary Texture2D [inf: as `M_LF_StageFlicker`-style LF materials sample any texture] | **Probably yes:** `UMediaTexture` derives from `UTexture` [decl: `MediaTexture.h:36-41`], so a Texture Sample can hold it [inf; not tested] |
| Scrub / jump / PIE / MRQ | **Exact.** The frame is `floor(keyed seconds × fps)`; Sequencer evaluates the MPC track on every scrub [inf: standard track evaluation] | **Not exact.** The player seeks asynchronously; the frame after a jump can be stale. Img Media (PNG sequences) is the best case, still async loading [inf]. The 29 Sep spec ruled media out for this reason |
| Determinism vs the Master | Same as any keyed track: the Interaction sequence's time | Player clock; must be slaved through a Media track |
| Cost per frame | One extra light-function pass per light; one BC4 texture (8–32 MB) [inf] | Decode (H.264 hardware decode, or PNG decode on a loader thread), a texture upload per frame, plus MediaPlayer/Source/Texture assets per take [inf] |
| Length limit | About 120–256 frames per atlas (section 2); longer means a second MI/light or a lower fps | Effectively unlimited |
| Authoring | One import per take; parameters from `manifest.json` | One import per take plus player wiring |
| VSM | Neither interacts. A light function multiplies the light after shadowing; it is not geometry, so it cannot invalidate VSM pages [inf]. The project runs VSM [decl: `Config/DefaultEngine.ini:22`] | Same |

---

## 5. The Light Function Atlas: what to check before trusting the look

- **What the atlas is.** When it is on, each light's function is rendered once into a fixed-size slot of a shared atlas,
  and lighting samples the slot.
- **What that does to a gobo.**
  - The atlas pass evaluates the material with **no world position** and builds the light vector from the slot UV alone
    [decl: `LightFunctionAtlasRender.usf:27,36,52`: `TranslatedWorldPosition = 0`, UVs from `SvPosition`].
  - It is greyscale unless the format is set to RGB [decl: `ELightFunctionAtlasPixelFormat` LFAPF_R8 / LFAPF_R8G8B8,
    `RendererSettings.h:239-245, 1077-1081`].
  - A UV-only flipbook works under the atlas. Its **resolution is capped at the slot size**, which may be well under the
    372–585 px cell [inf; the slot-size default is in private .cpp, not on disk].
- **Which paths use it.** Deferred lighting, volumetric fog, water and translucency each opt in by setting [decl:
  `r.Deferred.UsesLightFunctionAtlas`, `r.VolumetricFog.LightFunction`, ..., `RendererSettings.h:1083-1115`].
- **The trade-off.**
  - A gobo in the **haze beam** (volumetric fog) needs the atlas [decl: `RendererSettings.h:1084-1089`, "when the light
    function atlas is enabled"]. That is an attractive look for shadow play in haze.
  - The atlas also softens the projection on the cloth.
  - Without it, deferred light functions run per light at screen resolution, with full detail [inf].
- **This project's state is UNCLEAR.**
  - What was searched: `Config/DefaultEngine.ini` sets none of these cvars, and the engine defaults are in private .cpp.
  - Read them in the editor console before the bench: `r.LightFunctionAtlas`, `r.Deferred.UsesLightFunctionAtlas`,
    `r.VolumetricFog.LightFunction`, `r.LightFunctionAtlas.Format`, and the slot-size cvar (find it with
    `r.LightFunctionAtlas.` + Tab).
  - MegaLights requires the atlas; it is not enabled in the project config [decl: absent from DefaultEngine.ini].

---

## 6. Bench, then show (not run; each step its own MCP call, Don't-Save restart after)

1. **Offline.** Run the tool on the real take and check `preview.gif` with Gary.
2. **Import** the atlas create-only to `/Game/InfinityStage/Lighting/Gobo/`, with the texture settings in section 3.
   - Build `M_LF_ShadowGobo`, `MPC_ShadowGobo` and `MI_LF_Gobo_<take>`, all create-only.
   - Then read every parameter back.
3. **Bench at I1** (`velvet_v2_bench.py`'s `spot_on shadowplay_narrow` gives a transient narrow spot aimed at the
   bench drape).
   - Set the LF on the transient spot.
   - Set `GoboSeconds` to 0, 1.0 and 2.0 by hand and capture each.
   - **Scrub test:** capture the same `GoboSeconds` twice, reached from below and from above. The pixels must be
     identical; a stale frame is the failure mode.
   - Check the handedness (FlipU/FlipV) against `contact.png`.
4. **Show.** Extend `shadow_play_spot.py`: set the LF material on both spawnable spots, and add the MPC track keyed
   play start → GO HOLD. Then DRY, APPLY and read back per Interaction, as its existing modes do.
