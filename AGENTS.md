# PussStage Agent Notes

**Start here (9 Oct handover):** [`Docs/Conductor/HANDOVER_2026-10-09_NEXT_AGENT.md`](Docs/Conductor/HANDOVER_2026-10-09_NEXT_AGENT.md), then [`README.md`](README.md), then
[`Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md`](Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md)
— the container-world build runs several sessions in parallel, each owning
different files; read your stream's brief before editing anything. Then
[`Docs/InfinityStageSessionHandover.md`](Docs/InfinityStageSessionHandover.md)
(current as of 2026-09-25) and the three working lists —
[`ShowBuildTodo.md`](Docs/ShowBuildTodo.md) (engineering),
[`ShowCreativeTodo.md`](Docs/ShowCreativeTodo.md) (creative production),
[`ShowRehearsalTodo.md`](Docs/ShowRehearsalTodo.md) (rehearsal). Those three are
authoritative for what to do next.

**The active Windows workspace is `E:\PussStage`; the Mac → PC move is
complete.** Read
[`Docs/PCMigration.md`](Docs/PCMigration.md) and
[`Docs/WindowsBuildProcedure.md`](Docs/WindowsBuildProcedure.md) before building.

**Verify before trusting a task list.** `Docs/PussProjectTaskTracker.md` is
history, not a work queue: four of its outstanding rows were found on 2026-08-22
to describe features that already exist in source. It carries a reconciliation
block at the top — read that first. Grep the code before implementing anything a
document says is missing.

**Version control is split by file type.** Source, tooling, docs and config are
in **git** at the project root (see `.gitignore` — Content is deliberately
excluded). Commit your own stream's work; never commit another stream's files.
Binary content is protected by **full snapshots** to `D:\PussStageBackups` and by
timestamped folders in `Backups/`, following the `Pre<Thing>-YYYYMMDD-HHMM`
convention. Take a `Backups/` snapshot before editing C++ or mutating Show data —
git does not cover the Show asset or the level.

Before automating the open Unreal Editor or changing Infinity Stage authoring data, read [`Docs/CodexUnrealMCPRunbook.md`](Docs/CodexUnrealMCPRunbook.md).

Before touching GO1 dog telemetry, the `Go1Input` plugin or `go1_pi_bridge/`, read [`Docs/Go1TelemetryProgress.md`](Docs/Go1TelemetryProgress.md) — it carries the verified network endpoints, the non-obvious tick-group requirement, every command, and the safety rules that keep the robot untouched.

Before generating, orienting, texturing or exporting stage wings, read [`Docs/WingGenerationConventions.md`](Docs/WingGenerationConventions.md). New Left/Right pairs must be authored in final image handedness before normal-map or FBX generation; do not rely on an Unreal image flip to repair new assets.

Key project rules:

- Treat the Infinity Stage Show Asset as the authoring authority. MCP, Unreal Python and editor UI actions are transports/editing mechanisms, not separate data stores.
- Inspect first, make deterministic and narrowly targeted edits, materialize each affected Passage Actor, then save only the affected asset and level. Do not use **Save All** when unrelated packages are dirty.
- Use the guarded loopback project-Python MCP route as the standard no-UI authoring transport for now: toolset `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`, tool `ExecuteProjectPythonFile`, with scripts restricted to project `Saved/`. Prefer a narrower semantic MCP tool when one directly supports the operation. Epic Remote Python discovery and the macOS desktop executor are fallbacks documented in the runbook; desktop-driven execution is last resort.
- Always verify saved state by reading it back from Unreal and checking an explicit success marker in the Unreal log.
- The GO1 is treated as read-only infrastructure: no `sudo`, no installs, nothing written outside `~/go1_bridge/`, and no command that could move the robot. Keep the dog prone and the handheld remote with the operator when testing.
- **Mark your own uncertainty, where a reader can check it.** Every report,
  audit or investigation must separate what it PROVED from what it INFERRED, and
  say which is which per claim, not once at the top. Use these tiers:
  **declaration-proven** (stated by a header, signature or config we can read),
  **binary-proven** (recovered from an installed DLL's symbols or strings, which
  carry more than the headers do), **measured** (an intervention was run and its
  result read back), **inferred** (a conclusion that could not be verified, and
  why). A verdict of UNCLEAR, naming exactly what was searched, is a **better**
  answer than a confident guess, and a report that names what it found nothing in
  is worth more than one that only lists hits. Cite `file:line` for anything
  claimed to exist. **Reject any agent output that does not do this, whatever it
  claims to have found** — an unmarked report costs more to verify than to redo.
  — adopted 30 Sep 2026, after six delegated runs in which this property alone
  separated the usable results from the unusable ones.
- **Exception, Flat V3 (Gary, 30 Sep):** new Flat V3 flats follow `Docs/FlatV3Spec_2026-09-30.md`, which supersedes the V2 profile below for them (four slots Front/Flap/Timber/Edge, LOD1 beyond ~15 m). V2 still governs non-V3 wings.
- All newly generated production Wing FBXs must use the V2 profile in `Docs/WingGenerationConventions.md`: final source handedness before derived maps, explicit 10 cm thickness, Base/alpha plus `_H` height and `_N` normal textures with a relief preview, Front/Back/Edge slots, and a clean FBX re-import validation. The pipeline's 5 cm default is legacy and must not be used implicitly for new production Wings.
