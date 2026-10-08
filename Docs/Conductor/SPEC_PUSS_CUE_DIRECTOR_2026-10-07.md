# Spec: Puss Cue Director (performance cueing). Cueing stream, 7 Oct

**Status:** spec. Nothing in this document is built. Gary's answers (7 Oct, questionnaire) are quoted where they decide something.

**Tags:** **[decl]** means read in source or in the sheet; **[inf]** means design or inference that has not been checked.

## 1. What Gary asked for

- **"Adapt the Stage Wing Director into a general Puss Cue Director."** Wings become one tool among several, used for building the show. **The cue list is not the wing list.** It follows the show's structure (Opening → P1 → S1 → I1 → P2 → …), and each part is split into many cues.
- **A cue sheet like QLab:** one Show cue sheet, numbered show-wide with decimals (12.5).
- **Departments are the people,** taken from Gary's answer:
  - Kirke, cello (DPA mic).
  - Cameron: sound desk, foley, the Boy's voice (mic).
  - Klara: cues and narration (mic, plus a lav during the pre-Unreal shadow puppetry). Klara also puts the boots on Puss after the mountains.
  - Gary: Puss's voice (mic and lav) and the robot dog's remote.
  - The robot dog on the treadmill (remote control).
  - The lighting tech, who runs the lighting states.
  - All other sound comes out of UE5.
- **His priorities, in his words:**
  - "easily shift timings ideally without an MCP run";
  - "those scenes as videos ready to trigger by next friday";
  - "control or at least fix levels … including exposure once we see things on the LED screen";
  - "the GO1 linkup working effectively on dog wifi";
  - "most importantly to know where we are in the script … so that we don't miss any cues";
  - "robustness and ability to adjust as we rehearse";
  - "press H twice to see script too".
- **Run the show from both** the Cue Desk plus the H HUD (for the director) and a separate operator window (for a stage manager).

## 2. What already exists [decl]

- **Director HUD:** H toggles a bottom-row text strip in PIE showing the segment, the Passage bay, the last and next GO, and times (`IS/Public/InfinityStageDirectorHud.h`, `InfinityStageShowGameMode.cpp:52`).
- **Transport:** GO holds and passes, → and Space as GO, vamps, a performance-mode interlock (Scene 3 only), and fast-forward with audio muting. `GoCues` holds the list of GO points.
- **Cue Desk:** its list is the **wing** list (`FInfinityCueListItem`: Cue and PassageHeader nodes). It also has transport buttons.
- **Gary's master cue sheet** (Google Sheet `Puss_Master_cue_sheet`, 99 rows read 7 Oct):
  - Columns: # | Light | Sound tech | Action | Sound cue | Video cue | Klara | Gary | Cameron | Beats | Notes.
  - The "Video cue" column names the digital segments: Opening, Passage 1, S1 Animals, Transition (= I1), Passage 2, Scene 2: Shrine, …
  - Beats B1–B6 subdivide the Scenes.

## 3. Design

### 3.1 One cue sheet, two sources merged by row

- **Gary's Google Sheet stays the writing tool** for the script, the department actions and the notes. Everyone already edits it.
- **The Cue Director imports it:** File → Download → CSV, saved to `Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv` (or a "Reload sheet" button reads that path). No MCP and no Show write are involved.
- **The timing anchors live in a small project file:** `CueSheet/anchors.json` (git-tracked, diffable). It is edited in the Cue Desk, not by hand.
  - Each sheet row that touches the digital stage gets an anchor: **segment + offset**, so it moves with retimes; the segment is named by the Video cue column.
  - An anchored row can be a **HOLD** (the show waits for GO), a **PASS** (shown, no wait), or **FOLLOW** (fires on its own after N s).
  - Matching between the sheet and anchors is by a stable row key: the cue number if it has one, otherwise the text of the row's first non-empty cell plus its position under the previous number. A re-import after Gary edits the sheet keeps anchors on the same lines. Rows that can't be matched are flagged, never dropped.
- **Why not a Show array:** editing a cue must not need an MCP run or a Show save, and must survive Gary re-exporting the sheet [inf, by design].

### 3.2 Where are we

- **Digital position** comes from the playhead, which sits between two anchored rows.
- **Script position** has a **line cursor** that the operator advances; GO also advances it.
- The two are reconciled: reaching an anchored row moves the cursor to it, and the cursor never goes backwards on its own.
- This covers the whole pre-Opening puppetry section: all script, no playhead.

### 3.3 Operator surfaces

1. **The H key in PIE cycles through three states:** off → HUD strip → **HUD + script panel** → off.
   - The script panel shows the current line (large), the next two lines, and **standby** for the next anchored cue, with its department lines coloured by person (KK, GZ, CAM, Kirke, LX, DOG).
2. **Cue Desk, Show tab** (a new tab; the wing list moves under a **Build** tab). It shows the sheet as a table grouped by segment (Opening, P1, S1 …).
   - The current row is highlighted.
   - Per row: anchor, mode, nudge (±1 frame, ±0.1 s, ±1 s), "anchor at playhead", jump, re-run and A–B loop.
   - Edits write `anchors.json` and mirror markers into the sequences only on request.
   - **This is the "shift timings without MCP" path.**
3. **Operator window:** a standalone Slate window, movable to a second monitor. It shows the same current/next/standby view at stage-manager size, plus big **GO / HOLD / BACK / PANIC** buttons and the live trims (§3.4).

### 3.4 Live trims (Gary: "fix levels … including exposure on the LED screen")

- **The trims:**
  - Master UE audio level, in dB;
  - an exposure offset in EV, applied through an unbound PPV with weight 1 owned by the director;
  - an optional overall brightness/saturation trim for LED calibration.
- They are **runtime only by default**. A "keep" button saves them to `CueSheet/trims.json`; they are never written into the Show or level.

### 3.5 Robustness for improvising

- GO lockout of 0.5 s against a double tap.
- **BACK** (the previous anchored cue) and **JUMP** to any row.
- Hold anywhere: pause from the operator window, even in a Scene. Scene 3 stays performance-locked unless overridden.
- **PANIC:** fade to black over 1 s and mute UE audio; GO resumes.
- **Skip:** step over a stuck hold.
- Every GO, skip and panic is logged to `Saved/Logs/CueDirector_<date>.log` for rehearsal notes.

### 3.6 Video fallback (Gary: "scenes as videos ready to trigger by next friday")

- **Render each segment with Movie Render Queue** (the plugin already depends on MovieRenderPipeline [decl, `InfinityStage.uplugin`]).
- **A video mode in the operator window:** each segment row can play its pre-rendered file full-screen (Media Player) instead of live UE.
- This is a separate workstream, and the critical path for Friday because it needs render time.

### 3.7 Out of scope here

- The GO1 dog link (its own stream, `Docs/Go1TelemetryProgress.md`).
- Wing editing (it moves to the Build tab, unchanged).

## 4. Build order (proposed; Gary to confirm)

1. **CD1:** CSV import, the anchors file, the line cursor, and **H ×2 script panel**. Small C++: a new runtime module file plus a HUD patch. **The whole cast benefits at the next rehearsal.**
2. **CD2:** Cue Desk Show tab with anchor editing, nudges and jump (no-MCP timing).
3. **CD3:** operator window with GO/BACK/PANIC and live trims (levels and exposure).
4. **CD4:** video fallback (MRQ renders plus the play mode). If Friday's deadline is hard, start the renders now, in parallel.

## 5. Tests (named `InfinityStage.CueDirector.*`)

- **Import:** this sheet's header layout parses, departments map to people, and Video cue rows map to segments by label. Unmapped rows are flagged; the control is a renamed segment.
- **Re-import keeps anchors:** a row is inserted above, a line edited, and the anchor stays put. The control is a deleted row, which flags.
- **Cursor:** it never goes backwards on its own, reaching an anchor syncs it, and BACK moves it.
- **Lockout:** two GOs within 0.5 s produce one fire; the control is two GOs 0.6 s apart, which fire twice.
- **Trims:** they are not saved unless "keep" is pressed. The editor preview never dirties the level (the strobe lesson).

## 6. Gary's answers (7 Oct, second questionnaire, his words)

- **Sheet:** "sheet stays the source and shd be source of truth for the order of things but there may be discrepancies as my UE stage and cameron's sound and other things might not be fully consistent either".
  - So the importer **tolerates and flags** mismatches. A Video cue label that doesn't match a segment, or an anchor whose order disagrees with the sheet, is shown in amber, never blocked. The sheet decides the order; the stage decides the timing.
- **Build first:** the script panel plus the cue list (CD1, then CD2).
- **Deadline: "This sunday lunchtime actually. The first rehearsal is Tuesday and the show is saturday".**
  - Sun 11 Oct is the video fallbacks.
  - Tue 13 Oct is the first rehearsal.
  - Sat 17 Oct is the show.
  - **The video renders (CD4) are therefore on the critical path NOW and run in parallel** with CD1. They are an editor/render job for the conductor; they don't depend on the Cue Director code.
- **GO:** "Klara — and we need most things to run on and not need pressing go, we need to define where Go should be pressed, since the cellist during S3 might be one of the main human performance parts … if Klara's narration goes faster or slower maybe she can press GO or even pause or sth".
  - **Default mode is FOLLOW/PASS** (run on). HOLD only at rows marked "GO (Klara)".
  - Every HOLD row shows **who** presses GO. The default is Klara, and the sheet can name another person.
  - **Klara's pause/resume:** one key (or an operator-window button) that pauses or resumes anywhere outside Scene 3. Scene 3 follows the cellist (DeclaredUnpausable).
  - **A "Where GO is pressed" view:** a filtered list of the HOLD rows only, as Klara's own crib sheet.

## 7. Held patches as of 8 Oct, and one content step

**Build order:** CD1 → CD2 → UX1 → RB1. They go in after the conductor's vamp, fixtures and rehearsal-pref patches. None is built yet.

- **CD1 (07308d5):** imports the cue sheet CSV. Adds the script cursor (PageUp/PageDown), F5 to reload, and H to cycle the HUD strip, then strip plus script panel, then off.
- **CD2 (c554a48):** run-through with Klara's GO stops after chosen segments, plus GO holds kept where marked. Settings live in `cue_director.txt`. Adds the Puss Cue Director panel, opened from Cue Desk → View.
- **UX1 (520ce63):** Cue Desk panel toggles, splitters that actually resize, and resizable/hideable list columns. Removes the never-shown whole-Show details tree. Logs the open time.
- **RB1 (f0736f3):** the rehearsal bar, docked at the bottom of the Cue Desk and toggled with B in PIE. Adds the Show Trims actor.

**Content step needed before the Music/Ambience trims do anything:**
- Sequencer audio sections have no sound-class field [decl], so the music waves themselves must be assigned to a **Music** SoundClass, and that class set on the Show Trims actor's *Music Sound Class*. Do the same for an Ambience class if wanted.
- Until then only *Master Gain* acts on sound.
- This is an editor/content write, so it's the conductor's step, with Gary's OK.
