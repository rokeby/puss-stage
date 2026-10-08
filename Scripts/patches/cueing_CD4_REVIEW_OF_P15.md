# CD4 video fallback: review of P15, and what CD4 changes (8 Oct)

**Gary, 8 Oct, my session:** "review P15 and add the use video checkbox". CD4 (`cueing_CD4_video_fallback.patch`)
**replaces** the held P15 bundle (`Scripts/patches/P15VideoTransitions/`). Do not apply both.

**Tags:**
- **[decl]**: read in the P15 source or in UE 5.8 headers.
- **[inf]**: not compiled and not run.

## P15 findings

| # | P15 problem | Evidence | CD4 |
|---|---|---|---|
| 1 | It reads its own placeholder registry (`DerivedAssets/P15VideoTransitions/placeholder_current.json`, with keys `playback_file`/`media_frames`/`audio_owner`), not the conductor's render contract | [decl] P15 cpp `LoadRegistry` vs `MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md` §6 | Reads `Renders/Fallbacks/current.json` schema 1 (`video`, optional `muxed`, `frames`, `fps`). The root can be changed with cvar `InfinityStage.VideoFallback.Root` |
| 2 | There is no live/video switch: any registered Scene always plays as video | [decl] `Tick`/`ResolveScene` | A per-Scene **Use video** checkbox in the Cue Director panel, stored as `use_video = S<n>` in `cue_director.txt` |
| 3 | The overlay is added in `Initialize`, when the PIE game viewport may not exist yet, so it might never show | [decl] `Initialize`; [inf] init order | The overlay is added lazily in `Tick`, once the viewport exists |
| 4 | Overlay ZOrder 10000 sits over everything, including the rehearsal bar | [decl] | ZOrder 5, under the rehearsal bar (20) |
| 5 | Fast-forward flickers black: a jump of more than one frame seeks and hides the image, and at 4× every tick is a jump | [decl] `SyncToFrame` `bJump` | The video follows the Master's **rate** (`SetRate`) and re-seeks only past a tolerance, at most every 0.3 s. The picture is never hidden for a seek |
| 6 | Double audio, and no GPU saving: the live Scene keeps rendering and playing underneath | [decl] (no world-render or Master-audio handling) | While the video is up: `bDisableWorldRendering` [decl GameViewportClient.h:99], and the Master's own audio is muted through `Transport->SetVideoAudioMuted`, which ORs into `SetManagedMasterAudioMuted` and so holds through fast-forward and rewind |
| 7 | Missing or failed media gives **black** | [decl] `ShowBlack` | Missing or failed media falls back to **LIVE**, with a warning (`INFINITY_VIDEO_FALLBACK …`). It retries the next time the Scene is entered |
| 8 | Wrong include: `Components/MediaSoundComponent.h` | [decl] the header is at `MediaAssets/Public/MediaSoundComponent.h` | Fixed |
| 9 | While a Scene is opening, P15 shows black | [decl] | The live Scene stays up until the file has opened: no black gap [inf] |

## Unverified; check in the window

- [inf] Whether WMF's `SetRate(4)` works for H.264 MP4. If it refuses, the tolerance re-seek still keeps the video in step, but stepwise.
- [inf] An ownerless `UMediaSoundComponent` registered with the world plays muxed audio. This is the same as P15.
- [inf] Whether disabling world rendering affects the camera claims or the HUD.
- The sound owner is decision 4: `video_audio = ue` (the default) uses `muxed` if present, otherwise the video plays silent and a warning is logged. `video_audio = desk` keeps UE silent, so Cameron plays the WAV.
