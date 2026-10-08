# P15: Transitions into Scene videos + camera/video aspect consistency for the LED screen
Context:
- Scene video fallbacks (S1-S6, 1080p25 + WAV) are due Sun 11 Oct (Docs/Conductor/MRQ_VIDEO_FALLBACKS_PLAN_2026-10-07.md, Saved/CodexConductor/MRQ/).
- S5 IS a video (Rob, animator, sends the village tomorrow); we transition into it in-level.
- Gary: robustness of transitions "especially into the videos that we don't yet have. Down to consistency details, such as the aspect ratio of how our cameras come out between videos and in-game cameras and how they might present best on an LED screen, of which I must check the dimensions."
Job (offline):
1. **Video playback path.** How does a Scene play a video in the show today, if at all? Grep MediaPlayer, MediaSource, FileMediaSource and ImgMedia in Plugins/, Content-path refs in tools and Docs. Design (and implement as DRY/APPLY tools or held patches) a robust hand-over: Passage end → video Scene → next Interaction. It needs:
   - a PLACEHOLDER media (generate a 1920x1080 25 fps test-card clip with a timecode burn-in and a 1 kHz tone, with ffmpeg if available, else PNG sequence + WAV) so transitions can be rehearsed before Rob's and the fallback videos exist;
   - correct audio ownership (no double audio);
   - a plan for a missing or late file: the fallback is black + log, never a crash or hang;
   - frame-accurate start;
   - correct behaviour on jumps/scrubs from the cue desk.
2. **Aspect ratio audit.** Gather and tabulate:
   - every show camera's filmback/sensor, aspect constraint and FOV (CineCameraActor settings in tools/probes/records; Klara's sequences' cameras via her copies; S3 shots);
   - the game viewport/output resolution;
   - MRQ output settings;
   - any video assets' resolution.
   Find inconsistencies (e.g. constrained 2.39 vs 16:9, letterboxing, Super35 vs full frame — Docs/StageFrontSpec_2026-09-28.md says the filmback is unconfirmed).
3. **LED screen presentation.** The dimensions are UNKNOWN (Gary will check). Write a parametric recommendation: given LED pixel W×H and physical size, which render resolution, aspect handling (pillar/letterbox vs crop vs native) and camera filmback to use, plus a single project-wide setting/tool to switch output aspect consistently for game and MRQ. List the exact questions to ask the venue.
Deliver Docs/Conductor/P15_VIDEO_TRANSITIONS_ASPECT_2026-10-08.md + tools/patches with harnesses.
