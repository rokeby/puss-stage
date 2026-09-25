# PussStage Agent Notes

**Start here:** [`Docs/InfinityStageSessionHandover.md`](Docs/InfinityStageSessionHandover.md)
(current as of 2026-09-18) and the three working lists —
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

**This project has no git repository.** `Backups/` is the only version control
that exists. Take a timestamped snapshot there before editing C++ or mutating
Show data, following the existing `Pre<Thing>-YYYYMMDD-HHMM` convention.

Before automating the open Unreal Editor or changing Infinity Stage authoring data, read [`Docs/CodexUnrealMCPRunbook.md`](Docs/CodexUnrealMCPRunbook.md).

Before touching GO1 dog telemetry, the `Go1Input` plugin or `go1_pi_bridge/`, read [`Docs/Go1TelemetryProgress.md`](Docs/Go1TelemetryProgress.md) — it carries the verified network endpoints, the non-obvious tick-group requirement, every command, and the safety rules that keep the robot untouched.

Before generating, orienting, texturing or exporting stage wings, read [`Docs/WingGenerationConventions.md`](Docs/WingGenerationConventions.md). New Left/Right pairs must be authored in final image handedness before normal-map or FBX generation; do not rely on an Unreal image flip to repair new assets.

Key project rules:

- Treat the Infinity Stage Show Asset as the authoring authority. MCP, Unreal Python and editor UI actions are transports/editing mechanisms, not separate data stores.
- Inspect first, make deterministic and narrowly targeted edits, materialize each affected Passage Actor, then save only the affected asset and level. Do not use **Save All** when unrelated packages are dirty.
- Use the guarded loopback project-Python MCP route as the standard no-UI authoring transport for now: toolset `MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset`, tool `ExecuteProjectPythonFile`, with scripts restricted to project `Saved/`. Prefer a narrower semantic MCP tool when one directly supports the operation. Epic Remote Python discovery and the macOS desktop executor are fallbacks documented in the runbook; desktop-driven execution is last resort.
- Always verify saved state by reading it back from Unreal and checking an explicit success marker in the Unreal log.
- The GO1 is treated as read-only infrastructure: no `sudo`, no installs, nothing written outside `~/go1_bridge/`, and no command that could move the robot. Keep the dog prone and the handheld remote with the operator when testing.
- All newly generated production Wing FBXs must use the V2 profile in `Docs/WingGenerationConventions.md`: final source handedness before derived maps, explicit 10 cm thickness, Base/alpha plus `_H` height and `_N` normal textures with a relief preview, Front/Back/Edge slots, and a clean FBX re-import validation. The pipeline's 5 cm default is legacy and must not be used implicitly for new production Wings.
