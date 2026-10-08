# P15 — video transitions and aspect consistency (offline delivery, 8 Oct 2026)

## Verdict

- **[measured]** The current InfinityStage runtime has no video playback implementation: the offline search of `Plugins/InfinityStage/Source` found zero `MediaPlayer`, `MediaSource`, `FileMediaSource`, or `ImgMedia` hits. The earlier reveal audit independently records the same zero-hit result and calls its media-track route proposed/unverified (`Saved/CodexConductor/KlaraIngest/REVEAL_PLAN.md:137-150`).
- **[declaration-proven]** The Show already owns one Master `ULevelSequencePlayer`; Transport is initialized against it (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowRoot.cpp:21-53`). Passage-to-Scene autoplay intentionally uses one uninterrupted `PlayTo` across an adjacent boundary (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1158-1164,1194-1203`). The video clock must therefore follow Transport; it must not create another sequence player.
- **[measured]** A reproducible placeholder package was generated in `DerivedAssets/P15VideoTransitions/`: video-only H.264 1920×1080 25/1; separate stereo 48 kHz PCM s24 WAV; muxed H.264/AAC rehearsal copy; PNG preview; registry; shared display profile. The apply record contains byte sizes and SHA-256s (`DerivedAssets/P15VideoTransitions/p15_apply_record.json:77-117`).
- **[declaration-proven]** The Unreal integration is a held source bundle, not an applied change: `Scripts/patches/P15VideoTransitions/README.md:1-29`. It proposes an automatically created world subsystem and requires compile, packaged-build, cue-desk, and LED gates before merge.
- **[measured]** No Unreal, MCP, PIE, editor, Blender, Show Asset, level, or `Content/` mutation occurred. `Content/` is absent from this git worktree; the generated media and backup are ignored local derived artifacts.

## Playback hand-over

### Current path

- **[declaration-proven]** There is no current path. The previous plan suggested a per-Scene MediaTrack/MediaTexture and explicitly marked Master-scrub sync assumed, not checked in 5.8 (`Saved/CodexConductor/KlaraIngest/REVEAL_PLAN.md:139-150`).
- **[declaration-proven]** The fallback contract is one 1920×1080 25 fps clip plus a separate WAV per Scene (`Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md:6-12`), with video-only H.264, 48 kHz/24-bit PCM, optional muxed review copy, and `current.json` registry (`Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md:264-272,300-315`).
- **[declaration-proven]** Cue-desk scrubs pause and jump the Master playhead, clear rest/vamp state, and reclaim the segment camera (`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageTransportController.cpp:1672-1708`).

### Held behavior

- **[declaration-proven, new patch]** Passage → Scene: detect the Scene segment from `Transport->Segments`, derive `local_frame = master_frame - scene_start`, show black, open that Scene's registry file, seek local frame 0, then reveal only once media time is within half a frame (`Scripts/patches/P15VideoTransitions/InfinityStageVideoTransitionSubsystem.cpp:109-165,175-209`).
- **[declaration-proven, new patch]** Scene → next Interaction: because an Interaction is a `Sequence`, not a `Scene`, collapse the overlay and close media; Transport remains authoritative (`Scripts/patches/P15VideoTransitions/InfinityStageVideoTransitionSubsystem.cpp:212-247`).
- **[declaration-proven, new patch]** Direct jumps and scrubs: every tick derives requested media time from the absolute Master frame; discontinuities or drift over 0.5 frame hide the image and seek (`Scripts/patches/P15VideoTransitions/InfinityStageVideoTransitionSubsystem.cpp:175-209`). A paused Master pauses media after seeking, so a held cue displays the correct still.
- **[declaration-proven, new patch]** Missing/unregistered/open-failed/out-of-range media remains black and emits a deduplicated `P15_VIDEO_*` warning; it never blocks Transport (`Scripts/patches/P15VideoTransitions/InfinityStageVideoTransitionSubsystem.cpp:128-172,228-238`).
- **[declaration-proven, new patch]** Audio is exclusive. `ue_muxed` selects the muxed file and enables `MediaSound`; `desk` selects video-only and sets UE media volume to zero; any other owner stays black (`Scripts/patches/P15VideoTransitions/InfinityStageVideoTransitionSubsystem.cpp:128-159`; `DerivedAssets/P15VideoTransitions/placeholder_current.json:5-15`).
- **[inferred]** MP4 seeking may land on decoder/keyframe boundaries despite the half-frame gate. Frame-accurate cue-desk rehearsal should prefer the tool's PNG/ImgMedia fallback or production intra-frame/image-sequence media; this requires a live 5.8 test.

## Placeholder package

- **[measured]** `ffprobe` found exactly one H.264 stream at 1920×1080 25/1 in the video-only file, H.264 plus stereo AAC 48 kHz in the review mux, and stereo PCM s24le 48 kHz in the WAV. The preview was visually checked: animated test pattern, time/frame counter, and 5%/10% guides.
- **[declaration-proven, new tool]** The tool defaults to DRY, requires exact `APPLY P15VIDEO` / `REVERT P15VIDEO`, snapshots every owned target first, writes read-back hashes, and reverts by moving applied bytes into the backup before restoring originals (`Tools/InfinityStage/p15_video_package.py:34-35,343-364,422-482`).
- **[declaration-proven, new tool]** If ffmpeg/ffprobe are missing, it generates a numbered PNG sequence plus 48 kHz s24 WAV and delegates audio to `desk`, because ImgMedia cannot contain embedded audio (`Tools/InfinityStage/p15_video_package.py:300-340,392-421`).
- **[measured]** Successful run: `P15VIDEO-20261008-085030`; pre-change record: `Backups/PreP15VideoTransitions-P15VIDEO-20261008-085030/preflight_record.json`; success marker: `P15VIDEO_APPLY_OK`.
- **[measured]** An earlier run `P15VIDEO-20261008-084549` was interrupted during a Windows fontconfig stall before any output file existed. Its preflight-only backup remains intact; no deletion was made.

## Aspect and output audit

| Scope | Filmback / lens / horizontal FOV | Aspect constraint / output | Proof |
|---|---|---|---|
| S1 entry, exit, Klara first/last | 23.76×13.365 mm; 25 mm / 35 mm / 23.8846 mm → 50.83° / 37.50° / 52.89° | 16:9 filmback; constraint flag not captured | **[measured]** `Saved/CodexConductor/KlaraIngest/klara_reveal_record_S1.json:10687-10736,10793-10796` |
| S4 entry, exit, Klara first/last | 23.76×13.365 mm; all 35 mm → 37.50° | 16:9 filmback; constraint flag not captured | **[measured]** `Saved/CodexConductor/KlaraIngest/klara_reveal_record_S4.json:6898-6961,7072-7075` |
| S3 entry/exit/sleight | lens 50/50/28 mm → 26.73°/26.73°/45.98° if 23.76 mm wide | filmback and constraint absent from this record | **[measured lenses; inferred FOV]** `Saved/CodexConductor/S3Shore/s3_shore_live_reads.json:626-665` |
| S3 twelve scene-camera templates | lenses/FOV: 35/37.50° ×4, 50/26.73° ×4, 85/15.91° ×2, 100/13.55° ×1, plus Actor 0 50/26.73°; every serialized `AspectRatio` = 1.77777779 | 16:9 aspect value; filmback and constraint flags omitted | **[measured]** `Saved/CodexConductor/S3Diag/ds03_now.json:308-532` |
| S6 Klara five cameras | five components key 35 mm, f/2.8, focus 100000 | filmback/aspect/constraint absent | **[measured]** `Saved/CodexConductor/KlaraIngest/S6_VOID_PLAN.md:23-28` |
| Legacy transition/stall camera | 23.76×13.365 mm, 15 mm → 76.76° | 16:9; this transition path is explicitly off | **[declaration-proven]** `Saved/CodexSoftGoods/curtain_place_opening_and_transitions.py:16,44,84-87` |
| Handoff builders | copy source filmback/lens/focus into boundary camera | constraint is not copied here; pilot does copy it separately | **[declaration-proven]** `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageSceneHandoffBuilder.cpp:128-151`; `Plugins/InfinityStage/Source/InfinityStageEditor/Private/InfinityStageCameraPilot.cpp:102` |
| Game output | no project `ResX/ResY` or `ResolutionSizeX/Y` setting found | current packaged/window resolution is **UNCLEAR** | **[measured absence]** searched `Config/**` and saved `.ini/.json/.py/.ps1`; MRQ runner's 1280×720 window is only a render-process window (`Saved/CodexConductor/MRQ/mrq_fallbacks.py:74`) |
| MRQ output | n/a | 1920×1080, 25/1 | **[declaration-proven]** `Saved/CodexConductor/MRQ/mrq_fallbacks.py:64-65`; plan `Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md:183-188` |
| Existing video assets | no pre-existing `.mp4/.mov/.avi/.mxf/.webm` found in this worktree | production S1–S6 resolutions therefore unmeasured | **[measured absence]** whole-worktree extension census before placeholder generation |

- **[measured] UNCLEAR:** A complete “every show camera” census is impossible from this worktree: binary `Content/` is deliberately absent, S2/S5 camera records were not found, S6 filmback is not recorded, and no saved result exists for the S1 probe that would have captured `constrain_aspect_ratio` (`Saved/CodexConductor/S1Snap/s1_entry_snap_probe.py:217`). These exact locations and all saved camera JSON/Markdown were searched.
- **[measured]** No 2.39 camera/output declaration was found. Available current evidence converges on 16:9, but the constraint flags and complete camera inventory remain unproved. The older stage-front document correctly labels its Super35 assumption unconfirmed (`Docs/StageFrontSpec_2026-09-28.md:14-25`).
- **[inferred]** The practical inconsistency is not presently 2.39 versus 16:9; it is uncontrolled game-window resolution plus incomplete filmback/constraint evidence. Changing focal lengths to “fix aspect” would alter composition and is not recommended.

## LED recommendation (dimensions still unknown)

- **[declaration-proven, new tool]** Make `display_profile.json` the one source for content W×H×fps, LED pixel W×H, fit mode, Game launch args, MRQ resolution, and camera policy (`Tools/InfinityStage/p15_video_package.py:99-165`; generated example `DerivedAssets/P15VideoTransitions/display_profile.json:1-24`).
- **[inferred recommendation]** Default until venue confirmation: 1920×1080 25p, `fit`, black bars, preserve horizontal FOV, 23.76 mm sensor width and 13.365 mm height. This avoids cropping authored composition. Do not change camera filmback merely to fill the wall.
- **[declaration-proven, formula]** For content aspect `Ac=Wc/Hc` and LED aspect `Al=Wl/Hl`: `fit` scale is `min(Wl/Wc,Hl/Hc)` (pillar/letterbox); `fill` is `max(...)` (symmetric crop); `native` requires identical pixel dimensions. The tool prints exact bar/crop values and refuses incomplete or invalid geometry (`Tools/InfinityStage/p15_video_package.py:99-134`).
- **[inferred recommendation]** If the processor accepts a 16:9 raster inside a non-16:9 wall, keep a 16:9 logical canvas and map it with fit at the LED processor. Use native only when the wall raster and delivery raster match. Use fill only after Gary signs off on the reported crop.
- **[inferred recommendation]** Physical W×H does not choose render aspect; it supplies pixel pitch (`physical_width/pixel_width`, `physical_height/pixel_height`) and viewing-density checks. Non-square or unequal pitch is a venue/processor issue, not a camera-filmback fix.

### Exact venue questions

1. **[inferred requirement]** What is the active LED pixel raster W×H, and are pixels square?
2. **[inferred requirement]** What is the lit physical width×height, pixel pitch, processor model, and exact input/canvas mapping?
3. **[inferred requirement]** Which inputs, resolutions, refresh rates, scan modes, bit depths, chroma formats, and color ranges are accepted at 25 fps?
4. **[inferred requirement]** Must delivery fill the wall, or are black pillar/letter bars acceptable? If fill, may top/bottom or sides be cropped, and by how much?
5. **[inferred requirement]** Is scaling done by UE, playback software, or the LED processor; is overscan/edge crop enabled?
6. **[inferred requirement]** What color space/EOTF/white point/peak luminance are calibrated, and is a LUT required?
7. **[inferred requirement]** What is end-to-end video latency and genlock/frame-sync arrangement? Is audio embedded, analog/AES, or separately triggered at Cameron's desk?
8. **[inferred requirement]** Can the venue supply an exact test pattern capture and a safe-area/crop map before rehearsal?

## Harnesses and acceptance gates

- **[measured]** `test_p15_video_package.py`: `P15_HARNESS_OK|passed=27|positive=18|negative=9`; it covers fit/fill/native geometry, invalid dimensions, FOV, ffmpeg absence, frame-0/loop/end mapping, exclusive audio, backup/revert round-trip, and missing confirmations (`Tools/InfinityStage/test_p15_video_package.py:34-108`).
- **[measured]** `test_p15_runtime_patch.py`: `P15_RUNTIME_PATCH_OK|positive=10|negative=4`; it checks one Master clock, Scene-only activation, seek/black/audio/aspect invariants and negative controls against a second player, Transport mutation, unconditional UE audio, and editor ticking (`Tools/InfinityStage/test_p15_runtime_patch.py:11-34`).
- **[inferred/open gate]** Static checks are not a UE compile, packaged runtime, decoder, rendered seam, audio-routing, or LED acceptance. Run every gate in the held bundle README before merge.

## Commands

- **[declaration-proven]** DRY: `python Tools/InfinityStage/p15_video_package.py --mode DRY --args Tools/InfinityStage/p15_video_package_args.json`
- **[declaration-proven]** APPLY derived package only: `python Tools/InfinityStage/p15_video_package.py --mode APPLY --confirm "APPLY P15VIDEO" --args Tools/InfinityStage/p15_video_package_args.json`
- **[declaration-proven]** REVERT: put the recorded `apply_record.json` path in args (or pass an args copy), then use `--mode REVERT --confirm "REVERT P15VIDEO"`; applied bytes are archived, not deleted.
- **[declaration-proven]** Harnesses: `python Tools/InfinityStage/test_p15_video_package.py` and `python Tools/InfinityStage/test_p15_runtime_patch.py`.

## Decisions still needed

- **[inferred/open]** Gary: venue answers, fit versus fill, and whether the production media replaces the in-engine Scene for its whole segment or only the Klara slot.
- **[inferred/open]** Cameron/Gary: one production audio owner (`ue_muxed` or `desk`). The placeholder selects `ue_muxed` for self-contained rehearsal; production must choose explicitly.
- **[inferred/open]** Integration owner: whether to adapt schema-1 `Renders/Fallbacks/current.json` directly or promote the P15 schema-2 registry adapter into CD4.
- **[inferred/open]** Camera/look: capture every active camera's filmback, `bConstrainAspectRatio`, overscan, lens keys, and first/last Scene seam stills from the live UE5.8 Show before changing any camera.
