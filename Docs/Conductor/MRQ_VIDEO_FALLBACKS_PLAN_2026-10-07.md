# MRQ video fallbacks for Scenes S1–S6: plan, risks, tooling, schedule (7 Oct 2026)

**Status:** plan and offline tooling. **Nothing has run in Unreal**: no MCP, no editor launch, no render, no commit.
The offline harness passes 31/31, and 8 of 8 seeded mutations were caught (measured, 7 Oct).

**Gary's deadline (his own words, 7 Oct, conductor session):** "those scenes as videos ready to trigger", by
**Sun 11 Oct lunchtime**. The first rehearsal is Tue 13 Oct; the show is Sat 17 Oct. The spec:
- one clip per Scene, 1920×1080 at 25 fps;
- a separate WAV per Scene, not embedded.

The cueing stream adds trigger and playback (Cue Director **CD4**, `SPEC_PUSS_CUE_DIRECTOR_2026-10-07.md` §3.6). The
file contract they code against is in §6.

**Proof tiers, marked on every claim:**
- **[decl]** declaration-proven: a header, a source line or a config file, read on 7 Oct and cited `file:line`.
- **[bin]** binary-proven: a string found in an installed DLL.
- **[meas]** measured: a record, a byte scan or a command run today.
- **[inf]** inferred: not verified, with the reason given.

**UNCLEAR** means the question was searched and not settled; the search is named.

---

## 0. The recommendation in one paragraph

1. **Render the Master, not the Scene sequences.** Use one MRQ job per Scene on `LS_InfinityStage_V1Master`, with a
   custom range of `[scene_start − preroll, scene_end)` in Master frames.
2. **Render from the command line with the editor closed,** one job at a time, with Blender closed too.
3. **Render tier P first.** P is "PIE-match": TSR at 1 sample per frame, with the editor's scalability copied over.
   - It is the guaranteed deliverable, at an estimated 1.1–7.4 h for all six Scenes.
   - Do this on Thu night.
4. **Add tier C after Gary sees the S5 test.** C is "cinematic": 8 temporal samples and cinematic scalability, rendered in
   chunks, at an estimated 7.7–31 h.
5. **Encode offline with ffmpeg** (on disk [meas]). The video is an H.264 MP4; the WAV is PCM, trimmed by exactly the
   preroll's samples.
6. **Publish through one `current.json`,** which CD4 reads.

---

## 1. Inventory: what to render, per Scene

**Lengths** are the Scene sequences' playback ranges as read live at 13:13 today
(`Saved/CodexConductor/scene_exposure_weight_read.json` [meas]). They match the brief.

**Master ranges** are NOT on disk anywhere I could find. I searched `Saved/CodexConductor/**/*.json` for scene-section
master frames, and every hit was older Passage tick tables. The DRY reads them live from the Master's Scene track:
`UMovieSceneInfinitySceneTrack : UMovieSceneSubTrack` (`MovieSceneInfinitySceneTrack.h:27` [decl]).

| Scene | Sequence | Playback (own rate) | Seconds | Master frames @25 | Content |
|---|---|---|---|---|---|
| S1 Animals | `LS_DevScene_01` | 0–6176 @25 | 247.04 | 6176 | Our hangar intro, then Klara's nested `LS_Animals_1`, then our outro. Her LS is authored at **30 fps** (`KlaraIngest/census_report.md` S1 [meas]). |
| S2 Shrine | `LS_DevScene_02` | 0–2025 @25 | 81.00 | 2025 | **Our** S2. Japanese_Alley is streamed for viewing only, and LS_DevScene_02 was left untouched (`klara_hookin_stream_record.json` decided_by [meas]). **Its length may change:** Gary is asking Klara (CONDUCTOR5_LOG). |
| S3 Shore | `LS_DevScene_03` | 0–6240 @**24** | 260.00 | **6500** | Ours. The root has a Cinematic Shot track, Shots [−1, 1454) (`s3_narration_remove_record.json` [meas]). The vamp starts at `InfinityStage.VampStart`@3480 = 145.0 s (CONDUCTOR5_LOG, S3MARKERS) [meas]. |
| S4 Children | `LS_DevScene_04` | 0–4890 @25 | 195.60 | 4890 | Our intro, then her nested children sequence, then the outro. **The entry (v5) and the exit (20 s trim, shadow curtain) are being redesigned now.** |
| S5 | `LS_DevScene_05` | 0–1225 @25 | 49.00 | 1225 | Ours. The shortest, so it gets the test render. |
| S6 Void | `LS_DevScene_06` | 0–5489 @25 | 219.56 | 5489 | Klara's Void plus our hangar, which is hidden (`klara_void_s6_record.json`). |
| **Total** | | | **1052.2 s** | **26,305** | |

**Why the Master, and not LS_DevScene_0N on its own:**
1. **Timing.** The live show plays every Scene through the 25 fps Master. A sub-section maps S3's 24 fps and S1's nested
   30 fps content in real time. Rendering the Master at 25 fps therefore samples exactly what the show samples.
   - S3 comes out as 6500 frames lasting 260.0 s, with no frame-rate override.
   - This is harness-proven for the arithmetic only [meas offline]. That the live show resamples this way is [inf],
     from standard sub-section semantics.
2. **Shots.** S3's root Shot track, read as an MRQ shot list, could limit a direct S3 render to [−1, 1454) and restart
   warm-up per shot. That reading of MRQ's shot semantics is [inf]: it is not visible in the 5.8 headers. The Master's
   top level has no Cinematic Shot track, only the custom Scene, Passage and audio tracks (`InfinityStageSequenceBuilderLibrary.cpp:600-608` [decl]).
3. **The preroll needs the preceding Passage.** See §2, R7 and R18.

**Audio per Scene.** These sources come from records (each dated). The DRY lists every audio section to depth 4, with
its active and eval-disabled flags, plus the Master-level audio.
- **S1:**
  - `/Game/Scenes/Animal_Voices_1` inside `LS_Animals_1`, at Scene 12.29–208.63 s (`s1_audio_probe.json`, 6 Oct 00:18,
    taken before S1's relength) [meas, stale].
  - The narration stand-in is muted: Gary's 7 Oct hookin answers say "Drop it for now" → mute [meas record].
  - Her closure also contains `Animals_Project_CLICK`, a 149 s click track (`census_report.md` S1 [meas]). **The DRY warns
    if it is active**, because it would end up in the WAV.
- **S2:** the Shrine narration stand-in, 74.75 s, starting at the landing (`scene_narration_standin_record.json` [meas]).
- **S3:** the narration stand-in has been REMOVED (`s3_narration_remove_record.json`), and the Shore score
  `S03_Shore_People_Stereo.wav` is **not imported** (`scene_audio_import_args.json` s3_later_note) [meas].
  - So the S3 WAV holds the UE mix only: waves, mechanisms and the like. It may be close to silent (see the decision list).
- **S4, S5:** no record found. I searched `Saved/**/*.json` for `MovieSceneAudioTrack`. **UNCLEAR → the DRY lists them.**
- **S6:** the "Scene Score" track `SW_S6_The_Void_Live`, Scene frames 104–4804, 188 s (`scene_audio_import_S6_record.json`
  [meas]).
- **All Scenes:** UE renders at 48 kHz (`Config/DefaultEngine.ini:38` [decl]). That is exactly 1920 samples per frame at
  25 fps, which is why every trim is sample-exact.

---

## 2. Where MRQ output can differ from PIE, and how each case is handled

**The structural fact behind most of this table [decl]:**
- `AInfinityStageShowRoot` is a level actor. At BeginPlay in **any** game world it creates its **own**
  `ULevelSequencePlayer` on the Master and initializes the transport on it (`InfinityStageShowRoot.cpp:21-49, 56-64`).
- An MRQ command-line render is a game world. The comment `InfinityStageEffectSource.cpp:707` reads
  "Game worlds (PIE, Movie Render Queue)".
- So **two players** exist on the Master:
  - MRQ's, which is the one rendered;
  - the ShowRoot's, which holds at frame 0, the Opening. Without the Cue Desk nothing moves it. The C++ default is
    `bAutoPlay=false` (`ShowRoot.cpp:18`); the level instance's value is unread, so the DRY reads it and refuses `true`.
- **The transport therefore drives nothing in the render.** Its holds and vamps act on its own player
  (`InfinityStageTransportController.cpp:866-871`), and its frame stays at 0.

| # | Risk | Tier | Handling |
|---|---|---|---|
| R1 | Actors clocked by the transport read the ShowRoot's frame (0), not MRQ's: the strobe (`InfinityStageStrobeLight.cpp:111-137`), sweep lights (`InfinityStageSweepLight.cpp:193-226`) and light events (`InfinityStageLightEvents.cpp:315`). In a Scene they would be frozen, or gated off. | [decl] | The level holds **1 strobe** ("P04 Strobe") **and 2 sweep lights** [meas: byte scan of `L_InfinityStage_V1VerticalSlice.umap`, 7 Oct]. That they are Passage-only is [inf]. **The DRY lists each one's `active_segment_guids` against the Show labels and warns on any Scene or "all segments" actor.** If one matters, there are two options, both Gary's: accept it, or have a held C++ "render follower" patch (the ShowRoot adopts MRQ's player; not written; needs a build window). |
| R2 | A legacy curtain that follows the camera: the ShowRoot spawns `AInfinityStageCurtainRig` (`bFollowPlayerCamera=true`, `InfinityStageCurtainRig.h:41`) if any non-Passage cue has a curtain mode it does not own (`ShowRoot.cpp:177-205`). Its state would be frame 0's, i.e. a closed curtain over every rendered frame. | [decl] | On 27 Aug all seven Sequence cues owned their curtain (`CodexCurtainAuthoring/persist_show_sequence_ownership.json` [meas, old]). **The DRY re-reads every cue and REFUSES `LEGACY_CAMERA_CURTAIN`.** |
| R3 | View-target claims: `InitializeTransport` claims frame 0's camera (`Transport.cpp:1138-1144`). The reassert only fires inside a WingPair segment (`:2253-2258`), and frame 0 is the Opening, a Sequence cue. The Passage track does not claim the view while a transport is registered (`MovieSceneInfinityPassageTrack.cpp:157-209`). | [decl] / [inf] | So **MRQ's own Scene camera cuts decide the view.** The preroll frames, whose view is undefined, are discarded. If `bAutoPlay` were true, the ShowRoot would play into P01 and its reassert would fight the cuts, so the DRY refuses that. |
| R4 | **Camera authority differs from PIE.** In PIE the transport claims the Scene's Entry camera at the crossing (`Transport.cpp:876-885`). On 30 Sep Scene 1's nested cuts never took the view in PIE (memory `puss-camera-handover-facts`, UNCLEAR there). In MRQ only Sequencer's cuts act. | [inf] | Where PIE stayed on a transport claim, **the video may show the authored cuts instead.** QC compares the video with a PIE still at entry+5 s, mid and exit−5 s for every Scene (the `PSTILLS` tool). Gary judges which one is right. |
| R5 | The Cue Desk PIE hook: `HandlePostPieStarted` jumps the ShowRoot to the Cue Desk playhead in every PIE world (`SInfinityStageCueDesk.cpp:5404-5421`; `bPieStartsAtPlayhead = true`, `.h:266`). That includes MRQ's PIE executor. | [decl] | If the playhead sat inside the Scene being rendered, two players would evaluate it [inf]: duplicate spawnables, doubled audio. **Hence the command line** (an Editor-type module is not loaded in `-game` [inf, standard module rules]). `RENDER_PIE` refuses unless `cue_desk_closed_ack` is set. |
| R6 | The Director HUD is on in PIE: the `-1` auto default (`InfinityStageDirectorHud.cpp:28-32`). | [decl] + [bin] | `InfinityStage.DirectorHud 0` goes into every config. The cvar string is present in `UnrealEditor-InfinityStage.dll`. |
| R7 | Stale GeometryCache frames: decoding is asynchronous, and the frame after a jump is stale. | [meas 30 Sep, memory] | MRQ evaluates continuously from the preroll start, so the stale first frames land in the discarded preroll [inf]. QC: the backcloth must not be frozen. |
| R8 | Exposure. | [meas 30 Sep] / [decl] | No MRQ exposure setting is used; the scene's PPVs apply as in PIE. The show's EV100 −3 is an unbound Histogram volume with min = max (memory `puss-capture-exposure-convention`). S3's white-out fix is a sequence float hold (CONDUCTOR5_LOG [meas]), so it renders. **The DRY warns on adaptive volumes (min ≠ max)**, and QC flags a washed-out share above 5%. |
| R9 | Lumen, VSM, TSR history and the SkyLight recapture. | [decl] / [bin] | The preroll is 50 frames (2 s), or 125 for S3. Render warm-up runs 16 (P) or 8 (C) frames (`MoviePipelineAntiAliasingSetting.h:82`). `r.SkyLight.RealTimeReflectionCapture.TimeSlice 0` is set; the cvar string is in `UnrealEditor-Renderer.dll`. Her streamed levels each bring a SkyLight (CONDUCTOR5_LOG probe_sky [meas]). |
| R10 | Klara's streamed levels in a render world. They are `LevelStreamingDynamic` with `initially_loaded` true and `initially_visible` false (`KlaraIngest/klara_reveal.py:3263-3267`), made visible by Level Visibility tracks in the Scene sequences (`:3190`). | [decl] | MRQ flushes level streaming before each frame (`MoviePipeline.h:257-258`) [decl]. So the video shows them **on the first frame**, where PIE may pop a frame late [inf]. The DRY lists every level with its streaming flags. |
| R11 | Live Chaos cloth (S3 sack) and Niagara both start at the render start; temporal samples change the substeps. | [inf] | S3 gets a 5 s preroll. QC watches the sack and the foam. |
| R12 | Audio capture. | [bin] / [decl] | `.wav` output needs deterministic audio. MRQ's own new-process executor passes `-NoLoadingScreen -FixedSeed -log -Unattended -MRQInstance -deterministicaudio -audiomixer -AudioCallbackBufferFrameSize=32 -AudioNumBuffersToEnqueue=2` [bin, `UnrealEditor-MovieRenderPipelineCore.dll`], and the launcher uses the same arguments. The WAV is UE's mix only. The DRY warns on an active CLICK track. **Tier C has no WAV:** its audio is the P render's WAV, from the same Master range and the same clock. |
| R13 | Vamps and GO holds. | [decl] / [inf] | They live in the ShowRoot's transport, so **the video plays straight through** S3's vamp region (Scene 3480–4200 @24 = 145.0–175.0 s) once. Looping it is CD4's job, using `markers_video_s` in the sidecar. |
| R14 | GO1 telemetry. Go1Input listens on UDP 9876 (`Go1Input` header `:78`), and the Scenes' camera owner is DOG_FREE_LOOK (memory, 30 Sep). | [decl] / [inf] | **The dog's bridge must be off during renders.** The render window starts minimized; don't touch the mouse. |
| R15 | Gait bob, the shadow cat and the camera rig. | [decl] / [meas] | These run in Passages only, deterministically on Master time (memory, patch MR). They act only in the preroll. |
| R16 | The hangar arrival pre-drive and its initial pose. The Arrival is evaluated from Passage frames (`PassageTrack.cpp:241-245`), its float drives are game-world only (`InfinityStageArrival.cpp:1277-1283`), and BeginPlay sets the initial pose and the backcloth to sample 0 (`:954-969`). | [decl] | **This is exactly why the preroll exists:** the end of the preceding Passage drives them as it does live. |
| R17 | Only saved state renders. A command line loads the map and assets from disk. | [inf, standard] | Unsaved edits are invisible. The DRY's census must be clean. |
| R18 | The Master changes after BUILD. The ranges are baked into the configs. | [decl, own code] | `mrq_render.ps1` hashes the Master `.uasset` and refuses on a change (`MASTER_CHANGED_SINCE_BUILD`). Re-run the DRY, and BUILD v02 if the ranges moved. Any Scene relength or Master rebuild means a new version. |
| R19 | Sub-frame alignment. A Scene section can start between 25 fps frames: an old P01 table ends at tick 4624705, which is frame 4817.4. | [meas, old record] | Up to 40 ms of sampling offset, the same as live [inf]. No action. UNCLEAR whether today's sections are frame-aligned; the DRY reads display frames only. |
| R20 | Memory. The machine crashed today with the editor at ~21 GB and Blender at up to 17 GB on 64 GB (brief; CONDUCTOR5_LOG) [meas]. The render process's size is UNMEASURED. | — | The launcher refuses if the editor or Blender is running or free RAM is under 40 GB. A watchdog kills **only its own** render tree if free RAM stays under 6 GB. The S5 test measures the peak. |
| R21 | VRAM. Fully-load texture streaming meets the new 8K textures (millstone, PearlClam) on a 16 GB RTX 5070 Ti (nvidia-smi [meas]). | [inf] | The test watches for this. The fallback is `texture_streaming` NONE, which would need a BUILD of v02. |
| R22 | Disk. E: has 152 GB free (`df`, 7 Oct [meas]). PNGs are estimated at 3.5 MB per frame [inf]: P ≈ 91 GB and C ≈ 95 GB at the upper estimate. | [meas] / [inf] | The launcher's disk gate refuses at 1.3 × the estimate + 5 GB. The S5 test measures the real size. **Both tiers may not fit:** see decision 7. |
| R23 | The existing Cue Desk "Render Selection" path rebuilds the Master and **saves the Show, the Master and a wrapper** (`SInfinityStageCueDesk.cpp:6113, 6141`). | [decl] | **Do not use it** for the fallbacks. |
| R24 | Game mode. | [decl] | Keep MRQ's default `AMoviePipelineGameMode`: cinematic mode, HUD hidden, no input (`MoviePipelineGameMode.h`, `MoviePipelineGameOverrideSetting.h:83`). The ShowRoot does not depend on the game mode; it is a level actor. The harness refuses a game-mode override. |

**Must MRQ render through the Show Root to get the Show's behaviour?** No, as far as the source shows [decl].
- Every Scene behaviour found is sequence-evaluated, so MRQ's player reproduces it: cuts, hangar holds, float/visibility
  holds, Klara level visibility, audio, Arrival via the preroll.
- The exceptions are the transport-clocked actors (R1) and the camera-authority difference (R4). Both are surfaced, by
  the DRY and by QC respectively.
- The ranges are per Scene on the Master, as planned.

---

## 3. Tooling (`Saved/CodexConductor/MRQ/`, offline-written, NOT RUN)

| File | Role |
|---|---|
| `mrq_fallbacks.py` | The editor tool: SURVEY / DRY / BUILD / RENDER_PIE. Pure planning functions are importable without `unreal`; `python mrq_fallbacks.py PLAN facts.json` works offline. |
| `mrq_fallbacks_run.py`, `_args.json` (mode DRY), `_request.json` | The MCP runner. It purges stale `Saved/` modules first and keeps no UE objects at module level (memory crash rule 4). |
| `mrq_render.ps1` | The command-line launcher for ONE job. Preflight, a dependency-hash manifest, the watchdog, and success asserted from frames on disk. |
| `mrq_post.py` | Offline encode, QC, stale check, and promote to `current.json`. |
| `test_mrq_fallbacks_offline.py` | The harness: 31 cases, each with + and − controls. 31/31 pass, and 8/8 seeded mutations are caught (preroll off-by-one, range end+1, no tail merge, rate gate, length tolerance, HUD cvar, autoplay gate, audio samples) [meas]. |

**Modes.** Markers are `MRQFB_<MODE>_OK|run=…` or `MRQFB_STOPPED|run=…|reason=…`.

- **SURVEY: read-only.** It uses plain property reads only and never the SequencerTools bound-object query (memory crash
  #5). The census before and after is asserted equal. It reads:
  - the Master's Scene sections (range, play rate, start offset) and each Scene's playback, rate and markers;
  - audio to depth 4, and the Master's own audio;
  - the strobe and sweep actors with their segment labels, and every PPV's exposure mode and min/max;
  - the streaming levels and their flags;
  - the ShowRoot's `auto_play`, `prepare_on_begin_play`, Master and `performance_mode`;
  - each cue's `curtain_mode` and `sequence_owns_curtain`;
  - the editor's `sg.*` scalability, and which MRQ classes exist (ProRes/DNx/MP4 included).
- **DRY:** SURVEY, then `plan_jobs` and the gates, then one **transient** config per tier.
  - The transient configs exercise the real 5.8 setters and read-back without creating a package. The census is
    asserted again.
  - Output: `mrq_dry_<run>.json`, with the jobs, command lines, hour and disk estimates, warnings and refusals.
- **BUILD: create-only.** It needs `confirm "BUILD MRQFB"`, a `decided_by`, a clean census at the start, and none of the
  target assets existing; the preflight is all-or-nothing.
  - For each job it builds a transient config, verifies it, writes it with
    `MoviePipelineEditorBlueprintLibrary.export_config_to_asset(…, save=True)` (`MoviePipelineEditorBlueprintLibrary.h:29`
    [decl]), and reads the saved asset back.
  - It runs GC between jobs (memory `ue58-bulk-import-oom-crash`) and asserts the census after equals the census before.
  - It writes `mrq_jobs_built.json`, which carries the Master's sha256.
  - Assets go under **`/Game/ZZ_Render/MRQFallbacks/MRQC_FB_<S>_<tier>_<ver>[_kNN|_t10]`**.
- **RENDER_PIE: not recommended.** It runs a transient queue through `RenderQueueInstanceWithExecutor`
  (`MoviePipelineQueueSubsystem.h:71` [decl]) and leaves the user's MRQ queue untouched. It refuses without
  `cue_desk_closed_ack` (R5). Audio rendered in-editor is non-deterministic [inf].

**What every job contains** (`settings_spec`, read back by BUILD; the harness checks every invariant):

| Setting | P "PIE-match" | C "Cinematic" |
|---|---|---|
| Deferred pass + PNG (8-bit, no alpha) | yes | yes |
| `.wav` | yes (`PussFB_<job>_raw`) | no (P's WAV is the audio master) |
| Resolution / rate | 1920×1080, custom 25/1 | same |
| Range | custom `[start − preroll, end)` in Master display frames (`MoviePipelineOutputSetting.h:82-90` [decl]) | same, chunked ≤ 1500 frames (a short tail merges) |
| File name | `PussFB_<job>.{frame_number}`, 6-digit absolute Master frame | same, one folder per chunk |
| AA | TS 1, engine AA (TSR), warm-up 16 | TS 8, AA none, warm-up 8 |
| Game override | cinematic quality off, normal LODs, fully-load textures, flush streaming managers | cinematic quality on, high-quality shadows, LOD 0 |
| Cvars | DirectorHud 0, SkyLight TimeSlice 0, plus 11 `sg.*` copied from the editor | DirectorHud 0, SkyLight TimeSlice 0 |
| Game mode | MRQ default | MRQ default |

**Codecs.** ProRes and DNx exist as **engine** plugins (`D:\Unreal Engine\UE_5.8\Engine\Plugins\Media\AppleProResMedia`
and `\AvidDNxMedia`, both with Win64 DLLs [meas]). Both are `EnabledByDefault: false` and absent from
`PussStage.uproject` [decl]; enabling one is a `.uproject` edit plus a restart.
- **Not needed:** ffmpeg 9.0.2 (gyan.dev full build, at `%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe`, with
  libx264, prores_ks and h264_nvenc) is on disk [meas].
- MRQ's built-in H.264 encoder exists (`MoviePipelineMP4EncoderOutput.h` [decl]) and is unused. Separate frames plus an
  offline encode keep crash-resumable chunks and exact control.
- `MovieRenderPipeline` is enabled in `PussStage.uproject:44` and required by `InfinityStage.uplugin:15` [decl].

**Command line** (generated per job by `command_line()`; quoted exactly by `mrq_render.ps1`). Example for S5 P:
```
"D:\Unreal Engine\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" E:\PussStage\PussStage.uproject
  /Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice -game
  -LevelSequence="/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master.LS_InfinityStage_V1Master"
  -MoviePipelineConfig="/Game/ZZ_Render/MRQFallbacks/MRQC_FB_S5_P_v01.MRQC_FB_S5_P_v01"
  -NoLoadingScreen -FixedSeed -log -Unattended -MRQInstance -deterministicaudio -audiomixer
  -AudioCallbackBufferFrameSize=32 -AudioNumBuffersToEnqueue=2 -windowed -ResX=1280 -ResY=720 -nosplash
  -stdout -FullStdOutLogOutput -abslog="E:\PussStage\Renders\Fallbacks\S5\P_v01\logs\S5_P_v01.log"
```
- The `-LevelSequence=` / `-MoviePipelineConfig=` forms and their format messages are [bin], in
  `UnrealEditor-MovieRenderPipelineCore.dll`.
- MRQ's own error string says a Queue asset may also be passed as `-LevelSequence=` [bin]. That form is unused.
- **Inferred, and settled by the S5 test's frame-count assertion:** `custom_end_frame` is exclusive, and
  `{frame_number}` is the absolute Master frame.

---

## 4. Time and disk budget

**Basis:** 26,305 Scene frames. The preroll adds about 1.4% (P) or 5% (C, which prerolls every chunk). The
fixture-plan totals come from the harness [meas, offline arithmetic]. The rates per frame are the brief's assumptions for
C and mine for P [inf]; **the S5 test replaces them with measured numbers.**

| Tier | Frames rendered | s/frame (low / mid / high) | Hours (low / mid / high) | PNG disk (3.5 MB/frame) |
|---|---|---|---|---|
| P | ≈ 26,700 | 0.15 / 0.4 / 1.0 | **1.1 / 3.0 / 7.4** | ≈ 91 GB |
| C | ≈ 27,700 (≈ 20 chunks) | 1 / 2 / 4 | **7.7 / 15.4 / 30.8** | ≈ 95 GB |

- **Startup** costs 3–15 min per job [inf]: first-run shader and DDC work, then the map load. For C's ~20 chunks that is
  ≈ 1–2 h more.
- **Encode** is fast. libx264 `slow`/CRF 14 at 1080p25 runs at ≈ 30–60 fps on this CPU [inf], so ≈ 10–20 min for all six.
  QC runs signalstats and volumedetect, ≈ 5 min.

**Schedule.** Renders run with the machine to themselves: no editor, no Blender, no builds (memory
`puss-build-gate-is-machine-wide`), and no MCP.

| Slot | What | Order and why |
|---|---|---|
| **Thu 8, first editor slot** (~30 min editor + ~45 min render) | 1. **DRY** (MCP, read-only). 2. **BUILD** (create-only configs). 3. Editor closed: Don't Save is never needed, because BUILD leaves the census clean. 4. **T1** `S5_P_v01_t10` (300 frames). 5. **T2** `S5_C_v01_t10`. 6. Encode and QC both, then show Gary the contact sheets and clips. | S5 is the shortest Scene. The test measures s/frame, the RAM peak, PNG size, frame-count semantics, WAV validity and the look of each tier. |
| **Thu 8 night, 22:00–08:00** | **P v01, all six Scenes**: S5, S2, S4, S6, S1, S3. Then C for S5 and S2 if time remains. | Shortest first, so the most clips finish if something fails. This set is the **safety net**, even though S3 and S4 are still changing. |
| **Fri 9 morning** | Encode and QC the P set, promote it as "v01 safety" after Gary signs off, and hand `current.json` to the cueing stream. | CD4 integrates against real files on Friday. |
| **Fri 9 day** | Freeze check per Scene (`mrq_post.py stale`). | Target freezes: S5/S6 Thu 18:00; S1/S2/S4 Fri 18:00; S3 Sat 18:00 (decision 3). |
| **Fri 9 night** | P re-renders of every Scene changed since Thu, then C for the frozen Scenes (S6, S1, S2). | C costs ≈ 3–13 h for these. |
| **Sat 10 day** | QC, and Gary reviews C against P. | |
| **Sat 10 night** | C for S3 and S4, plus any P re-renders. | ≈ 3–13 h. |
| **Sun 11, 06:00–11:00** | **Slack:** re-render failed chunks (a chunk costs ≤ ~1 h at C) or the last P fixes (S3 P ≈ 0.3–1.8 h). Then encode, QC and promote by 11:30; hand over by 12:00. | |

**If the test measures C above 2 s/frame,** C is cut back to S5, S2 and S6, or dropped. **P is the deliverable either
way.**

**Disk.** After an MP4 and WAV are promoted, that Scene's PNG frames can go: about 45–90 GB per tier. Deleting them is
Gary's call (decision 7). Tools never delete; the launcher only renames an old take aside.

---

## 5. Encode and QC

**Encode** (`mrq_post.py encode --scene N --tier P [--mux]`):
- **Video:**
  - Keeps exactly the Scene's Master frames and drops the preroll.
  - Chunks are hard-linked into one numbered folder on the same drive; nothing is copied.
  - H.264 High, 4:2:0, BT.709 limited range, CFR 25, `keyint=25:scenecut=0` (one keyframe per second, so CD4 can seek
    and loop exactly), `+faststart`, CRF 14.
- **Audio:** cut from the P job's raw WAV with `atrim=start_sample=preroll×1920:end_sample=…`, sample-exact, as 24-bit
  PCM at 48 kHz.
- **Sidecar:** `PussFB_S<n>_<tier>_<ver>.json`, holding frames, seconds, the Master keep range, the sample count, the
  markers in **video seconds** (for example S3 `InfinityStage.VampStart` = 145.0 s), the jobs used, and sha256 sums.
- **Optional `_muxed.mp4`** (AAC 320k), as a convenience for a plain media player.

**QC.** Hard failures block promotion; soft findings go to a human.
- **Hard:** the frame count equals the Scene's frames, and the audio and video lengths are within one frame of
  frames/25. The video must be 1920×1080 at `25/1`.
- **Soft:**
  - black stretches of 0.5 s or more (authored darkness is expected; Gary judges);
  - a black first frame;
  - frame-to-frame luma jumps of ΔY ≥ 40 (candidates for cuts, streaming pops or a stale cache);
  - a washed-out share above 5% (the S3 white-out lesson);
  - audio clipping at −0.1 dB, or a near-silent mean below −60 dB;
  - silences of 2 s or more.
- **Contact sheet:** 24 frames.
- **Human checklist, written into `_qc.json`:**
  - exposure matches a PIE still at entry+5 s, mid and exit−5 s;
  - her streamed sets are present;
  - no HUD or debug text;
  - the camera follows the authored cut list (R4);
  - the GeometryCache cloth is not frozen;
  - audio is in sync at a strike or clap marker;
  - no click track.

**Stale check** (`mrq_post.py stale`): for each take, the dependency hashes recorded by the launcher before rendering (the
Master, the Show, the map, the Scene and its nested sequences, the sounds, her levels) are compared with the files now on
disk. The output is FRESH, or STALE with the changed files listed.

---

## 6. File contract with the cueing stream (CD4)

```
E:\PussStage\Renders\Fallbacks\            (git-ignored: .gitignore ignores the root by default)
  current.json                             <- CD4 reads ONLY this
  S<n>\PussFB_S<n>_<tier>_<ver>.mp4        video, 1920x1080 25p H.264, no audio
  S<n>\PussFB_S<n>_<tier>_<ver>.wav        PCM 24-bit 48 kHz, exactly frames x 1920 samples
  S<n>\PussFB_S<n>_<tier>_<ver>.json       sidecar (frames, seconds, markers_video_s, sha256)
  S<n>\PussFB_S<n>_<tier>_<ver>_qc.json / _sheet.png / [_muxed.mp4]
  S<n>\<tier>_<ver>[_t10]\frames[_kNN]\    raw PNGs + raw WAV, logs\, deps_manifest_*.json, render_result_*.json
```

**`current.json` (schema 1)** holds `scenes.S<n> = {video, audio, sidecar, frames, seconds, fps, tier, version, sha256,
markers_video_s, approved_by, promoted_utc, previous}`, with paths relative to `Renders\Fallbacks`.
- It is written only by `mrq_post.py promote --by "<who>"`, after hard QC passes and the sha256 sums still match.
- **CD4 should:**
  - start video and WAV on the same frame (the WAV holds exactly frames×1920 samples);
  - seek on whole seconds or keyframes;
  - loop S3's vamp, if wanted, with the sidecar's times.
- **Who plays the WAV** (UE, or Cameron's desk) is decision 4.

---

## 7. What is proved and what is not (summary)

**Proved:**
- [decl] the source and header facts in §2 and §3;
- [bin] the cvar names and MRQ's command-line forms and process arguments;
- [meas] ffmpeg on disk, the plugin DLLs, disk space, the GPU, the Scene playback lengths (13:13 today), the strobe and
  sweep counts in the map;
- the harness at 31/31, with 8/8 mutations caught.

**Not proved (all inferred until the S5 test):**
- the MRQ semantics: shot-track handling, an exclusive custom end, `{frame_number}` being absolute, preroll sufficiency;
- the render process's RAM and VRAM;
- the real s/frame and PNG size;
- whether the 5.8 Python property names in `_apply_and_verify` all exist. The DRY's transient probe tests these before
  BUILD.

**UNCLEAR:**
- today's Master Scene ranges (none on disk; the DRY reads them);
- the S4 and S5 audio (no record);
- whether any strobe or sweep light is active in a Scene (the DRY lists them);
- the ShowRoot's saved `bAutoPlay` (the DRY reads it).
