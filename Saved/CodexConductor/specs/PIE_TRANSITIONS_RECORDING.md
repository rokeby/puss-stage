# Record a PIE run-through of all TRANSITIONS, skipping Scene contents (Gary, 2 Oct night, his own words in the Conductor 4
# session: "record a pie runthrough, skipping over the contents of scenes ... but showing all the transitions"; "per frame
# screenshot (per 2 seconds?) is enough"; MHFat recorded its own PIE window).
Reference: E:/MHFat/Scripts/Conductor/record_clip.py (ddagrab of the PIE WINDOW's rect; needs display awake + unlocked).
Our failure: Docs/CodexUnrealMCPRunbook.md:236-252 (docked viewport doesn't present when not foreground; `shot` works).
## Safety (crash rules + PIE)
- Census clean and NO PIE active before starting (if Gary is in PIE: STOP). Start PIE ONLY via this script, record a flag
  file Saved/CodexConductor/pie_recording_owner.json; end ONLY that PIE at the end (editor_request_end_play), never anyone
  else's. Never quit the editor, never Save All, no saves at all. Census asserted clean after PIE ends (a PIE run leaves
  maps=[] content=[]: measured 30 Sep). Purge cached Saved/ modules. No unreal objects in module globals (store the tick
  callback handle in builtins like Saved/CodexSceneTransitions/stop_scene_probe.py does). Performance mode must be OFF.
## Mechanics
- Play mode: PIE in a NEW EDITOR WINDOW (LevelEditorPlaySettings -> floating window, ~1280x720), so it's a top-level window.
  Discover the Python API read-only first and report it.
- Driver: a slate post-tick callback that walks a schedule using the InfinityStageTransportController in the GAME world
  (JumpToSegment / PlayForwardToBoundary / segment frames from its Segments; read the segment table at PIE start and log it).
  Schedule ("transition windows"): Opening from 0 to P01 start + 10 s (curtain + walk-in); for each Passage: its last 15 s
  then the following Scene's first 30 s (hangar rise, roof, lattice, strike at +10 s / S6 dim); then jump to the Scene's last
  5 s, play through the Interaction and into the next Passage's first 10 s. Use jumps between windows; real-time (1x) play
  inside windows. Log every window start/end with Master frames: PIE_REC_WINDOW|i=..|label=..|from=..|to=..
- Capture A: ffmpeg ddagrab of the PIE window rect (as record_clip.py; 960 px wide, NVENC if present else libx264), one file
  per run. Capture B: a `shot` (HighResShot 1280x720 or `shot`) every 2.0 s of game time, filenames carrying the window label
  and Master frame. Outputs under Saved/CodexConductor/PieRecording/<stamp>/.
## THIS PASS = TEST ONLY: run just the Opening window (0 -> P01 start + 10 s) and the P02 -> Scene 2 window. Report: did
  ddagrab produce MOVING frames (measure: fraction of identical consecutive frames); did shots land at the right times;
  the API used for the floating PIE window. Then end our PIE, census, stop. FINAL MESSAGE tagged per AGENTS.md.

## From MHFat's conductor (2 Oct night; their measured/code facts)
- Start PIE over MCP with EditorAppToolset.StartPIE {playMode: "PlayMode_InEditorFloating"}; the window title contains
  "Preview [NetMode: Standalone 0]".
- ddagrab is a SCREEN-REGION grab: the PIE window must be ON TOP and unoccluded (bring it to the foreground with
  SetForegroundWindow / SetWindowPos HWND_TOPMOST for the take, then restore). A window over it gets recorded instead.
- Filter chain that worked: ddagrab=output_idx=0:framerate=N:offset_x=x:offset_y=y:video_size=WxH:draw_mouse=0,hwdownload,
  format=bgra,scale=960:-2,format=yuv420p -> h264_nvenc p5 VBR 1M (max 1.5M). Reference: E:/MHFat/Scripts/Conductor/record_clip.py.
- In-engine HighResShot works regardless of focus but is slow in the background (1-3 fps).

## FULL RUN (after test 20261003_040515 passed: 0% frozen frames, 36/36 shots on time)
Same mechanics as the test (New Editor Window PIE command, the ownership flag, transport-driven windows, ddagrab of the
"PussStage Preview [NetMode" window brought to the front, plus a shot every 2.0 s), ALL windows in the schedule: Opening ->
P01 +10 s; for each Passage P01..P06: last 15 s -> following Scene first 30 s; for each Scene S1..S5 (and S6 if an
Interaction/coda follows): last 5 s -> through the Interaction -> next Passage first 10 s. Before recording: console
`DisableAllScreenMessages` (restore with `EnableAllScreenMessages` after). Burn a small label per window into the video
(drawtext: the window label + Master time), or write a chapters file. Also stitch the shots into a 0.5 fps contact video and a
contact-sheet PNG per window. End only our PIE; census clean after.
