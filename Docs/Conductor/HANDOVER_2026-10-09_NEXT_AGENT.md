# Handover: PussStage, for the next agent (Codex or another team)

**Written:** 9 Oct 2026, ~22:45 UTC, by Claude (Conductor 5). Claude usage is nearly exhausted, and this document lets a different agent pick the repo up cold.

**Tiers** (AGENTS.md):
- **measured**: run and read back.
- **declared**: stated by a file or record.
- **inferred**: not verified; the reason is given.

---

## 1. What this is

*PussStage* is an Unreal Engine 5.8 project (`E:\PussStage`, Windows) for a live theatre show, *Puss*, directed by Gary.

A live GO1 robot dog carries a camera through **Passages** (P01–P06): long "infinity stage" corridors of painted flat wings. Between them are **Scenes** (S1–S6), mostly Klara's sequences in streamed levels, and **Interactions** (I1–I5), short curtain/shadow-puppet transitions.

The **Show asset** (Infinity Stage Show) is the authoring authority for cues and attachments. The **Master** level sequence owns time and camera.

Unreal is used for **cinematic footage**: recording video comes first.

## 2. Read these first (in order)
1. `AGENTS.md`: project rules. They are binding, especially the **proof-tier rule**: every claim is marked declared / binary / measured / inferred.
2. `README.md`, then `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md`.
3. `Docs/CodexUnrealMCPRunbook.md`: how to drive the open editor.
4. `Docs/WindowsBuildProcedure.md`: build and tests. The test filter is **`InfinityStage`**, never `PussStage`.
5. `Docs/Conductor/codex_briefs/_house_rules.md` and `p49_postbake_editor_runner.md`: the editor-runner HARD RULES.
6. Tonight's notes: `Docs/Conductor/GARY_PIE_NOTES_2026-10-09_evening.md` (E1–E25 with routing).
7. The live-queue brief now running: `Docs/Conductor/codex_briefs/p102_live_queue_evening.md`. Its report will land at `Docs/Conductor/LIVE_QUEUE_REPORT_2026-10-09.md`.
8. Claude's memory notes, which hold hard-won traps: `C:\Users\Administrator\.claude\projects\E--PussStage\memory\*.md` (index in `MEMORY.md`). The most important are copied in §6.

## 3. Version control and backups
- **git**: source, tools, docs. Remote: private `rokeby/puss-stage` (origin); push after each commit.
  - `Content/` is excluded. Curated Blueprints are added with `git add -f`.
  - **Never `commit -a`, never `stash`**: other streams keep uncommitted work in the shared tree. Add explicit paths only.
- **Binary content**: full snapshots to `D:\PussStageBackups` (also `F:\`), plus timestamped `Backups/Pre<Thing>-YYYYMMDD-HHMM` folders.
  - Take one before C++ edits or Show/level mutation that has no record-based REVERT.
- **Held C++ edits** live as patches in `Scripts/patches/`. Any build compiles the working tree.
  - Apply a patch only in a build window with **no UnrealEditor.exe running anywhere on the machine**.
  - Build, run tests, and revert on red.

## 4. How work is done
- **Codex jobs** run through `Scripts/codex.sh`:
  - `--worktree` for offline tool-writing (no Unreal, no Blender).
  - `--unreal` for live editor runs (`CODEX_EFFORT=high`).
  - `--build` for build windows only.
- Each job delivers:
  - a **DRY / APPLY / REVERT** tool with records, keyed by cue GUID
  - an exact dirty-package census, targeted saves (never Save All), read-back, and a success marker carrying a run id in `Saved/Logs/PussStage.log`
  - an offline harness with − and + controls
  - a tiered report
- **Importing a worktree job:**
  1. `git -C <wt> diff` → `git apply --check` → `git apply`.
  2. Copy untracked **and ignored** files (`ls-files --others --ignored --exclude-standard`); args JSONs are often ignored.
  3. Rerun the harness in the main tree.
  4. `git add -f` explicit paths, commit, push.
  - Codex worktrees are under `C:\Users\Administrator\.codex\worktrees\<id>\PussStage`. Codex cannot commit from them.
- **Job numbers:** next free is **103**. Grep tools, records and commits before briefing anything; work is often already done.
- **Editor transport**: `Saved/CodexConductor/conductor_helpers/mcprun.sh <request.json> "<regex>" "<prefix>" 1`. This calls `ExecuteProjectPythonFile` on the guarded MCP at 127.0.0.1:8010, with scripts under `Saved/`.
- **Editor restart:**
  - Kill UnrealEditor.
  - If the restart follows a failed mutation, choose Don't-Save: rename `Saved/Autosaves/PackageRestoreData.json`.
  - Relaunch with `Start-Process explorer.exe -ArgumentList '"E:\PussStage\PussStage.uproject"'`. Going through explorer detaches it from the agent process.
  - **Always** run `editor_sky_toggle_request.json` afterwards to hide the sky. This is Gary's standing rule: the editor stays without sky or sun.
- **One editor writer at a time.**
  - Never end Gary's PIE.
  - Never save Klara's streamed levels.
  - Look and creative changes need Gary's own word.

## 5. State at handover (9 Oct ~22:45)

**Live in the Show today** (measured, read back):
- music-length Passages (P05 held at 186.4 s)
- P06 retime and dominoes (chains A and B)
- I2 fixes
- Nap interlude
- chandelier assets imported
- ragged curtains
- S1/S3 fixes
- Cue Book stills

**Built tonight** (measured):
- **P86 rehearsal bar**: scrub on script step, draggable strip, big Play, Right-hold 4×/8×. Commit bb6e431e; `InfinityStage.Rehearsal` 5/5.
- **Job 95 C++ patch** (`Scripts/patches/2026-10-09_job95_bob_bias_and_free_look_settle.patch`): built only after adding `#include "CineCameraComponent.h"` to `Go1LookResetAtCutTests.cpp`. Its own new test `InfinityStage.Go1.FreeLookReturnsDuringPassageSettle` FAILED; the other six Go1 tests passed. **Reverted and rebuilt clean.** It needs a Codex fix (the patch should carry the include) before a retry.

**Running now:** Codex job 102, the live queue in Gary's priority order:
1. S3 read-only diagnosis
2. P02 Top-wing facing DRY
3. P02 lighting = P01, plus P02 practicals
4. chandelier staging → candles → swing
5. jobs 87–98 and the pearl fade
6. then 99–101

Check `Saved/CodexRuns/ledger.tsv`, the codex_p102 log, and the report file above.

**Offline jobs:**
- **Imported and harness-green (commit 980fb43d):** 87, 88, 89, 90, 90b, 92, 93, 94, 95 (Python), 96, 97, 98.
- **Possibly still finishing offline:** 99 (S6 parcan + sun disc), 100 (S6 swarm driven by the old lady's hand analysis), 101 (ending). Their worktrees are 29b6, 7aaf and 2e2a.
- **Deprioritised by Gary**: swarm and ending.

**Waiting on Gary:**
- P05 length: 186.4 → 42.0 s? Two camera keys fall past the new end.
- S3 dune set D (594 cm, over the landed box).
- Gobo content.
- Cue Book dark stills retake.
- Saturday-night filming (`Tools/Fallbacks/saturday_night_film.ps1`).
- Darker S6 old-lady cuts? (asked, unanswered)
- His own tasks: cloud-wing widening, the P05 deer curtain image (deer looking at camera, smaller), Code.gs redeploys.

**Known open issues:**
- S3 figure materials: shrouds black/shiny/untextured, T-shirts white, one figure with no shroud, one translucent, feet sunk in the dune. Diagnosis is item 1 of job 102.
- I5 curtain hidden behind a wall: wait for Rob's S5 material, since the S5 hangar will change.
- `UMovieScene::GetBindings` non-const deprecation warnings in `InfinityStageArrival.cpp:236,358`: compiles today, will break in the next engine.

## 6. Traps that cost hours (keep these)
- **UE 5.8 Python** — return values lie (setters return False, `remove_track` returns None): always read back.
  - `str(FGuid)` is a changing address; use `GuidLibrary.conv_guid_to_string`.
  - `str(enum)` gives `'<E.V: n>'`.
  - Channel names are suffixed (`Location.X_183`).
  - Editor Python caches imports across MCP runs: purge before rerunning edited helpers.
- **Editor crashes**:
  - deleting nodes on pre-existing materials
  - reloading the open level/world
  - a cloth asset on a Poseable mesh
  - UE wrappers in module globals
  - bulk imports (3× 4096² + hundreds of MIs in one call: batch it and GC)
- **Sequencer**:
  - Visibility tracks must bind `bHidden` (bound to `bHiddenInGame` they are inert).
  - Opening or scrubbing the Master dirties the map.
  - Passage keys are absolute.
  - Scene cut bindings must resolve in the show level.
- **Builds**: any running UE editor blocks every build. C4458 shadowing is an error. Use a `.cmd` wrapper for Build.bat.
- **Read-backs are not visual proof**. Gary found applied-and-read-back changes (underwear colour, feet height) that looked unchanged on screen. Take stills and compare against what he asked for.

## 7. People and sessions
- **Gary**: director, the only approver of look and creative decisions.
- **Klara**: Scenes and sequences; her lengths set S1/S2/S4.
- **Rob**: S5 material, coming.
- **Cameron**: timings.
- Other Claude streams (Wings & Textures, Finishing Touches, Hyper3D, Museum, Cueing, Gobo) are mostly offline now. Their files are their own; never commit them.
- Cue Book: GitHub Pages `rokeby/puss-cue-book` plus a private Sheet/Apps Script. Gary owns the passcode.
