# PussStage — Infinity Stage

A theatre piece for projection, live cello and voice, and a live robot dog.
The audience travels an endless Baroque stage machine: painted wings pass on
either side while a cat — played by the dog — moves through it.

This README is written for a person with no AI session open. It says what the
project is, where the authority lives, how to run it, and what state it is in.

## What the show is

Nineteen segments: **six Passages** (travelling through wings), **six Scenes**
(cinematic, opening into large volumes) and **seven SEQ blocks** (an opening,
five boy/cat interactions behind a curtain, a closing). Unreal owns the clock;
the musicians play to it.

The world being built now is the **container**: timber gridiron overhead,
chariot grooves in the floor, walls beyond the wings, haze, practicals, cloth.
The register is Baroque stagecraft — wood, rope, canvas, paint, wear — not
industrial precision. See `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md`.

## Where the authority lives

| Thing | Authority |
| --- | --- |
| Cue order, wings, lights, timing | `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show` |
| The world | `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice` |
| Engine | UE **5.8** at `D:\Unreal Engine\UE_5.8` |
| Plugin | `Plugins/InfinityStage` (version in its `.uplugin`) |

**The Show Asset is the source of truth.** Moving a placed light or attachment
in the level writes its offset and settings back into the Show. Never derive
authoring data from actor world transforms.

## Running it

Open `PussStage.uproject`, load the vertical-slice map, press Play.

- Click the game viewport for keyboard focus. **Space** plays/holds the current
  segment, **Right/Left Arrow** move a segment.
- **F8** ejects to a free camera while the show keeps running.
- With no robot connected, set the Cue Desk's *Live Camera Owner* to **Force
  Dog** and the **mouse** stands in for the dog's head.
- The **Cue Desk** (Window menu) is the authoring surface: cue list, music,
  Actions.

## Building

The editor must be **closed** — and so must any other Unreal editor, because
Live Coding blocks builds across projects.

```bat
"D:\Unreal Engine\UE_5.8\Engine\Build\BatchFiles\Build.bat" PussStageEditor Win64 Development -Project="E:\PussStage\PussStage.uproject" -waitmutex -NoUBA
```

Then prove the new code is really in the binary before trusting any test — a
symbol check is not enough, because an inlined function exports nothing. Search
for a **UTF-16 string literal** from the new code. Full procedure and the test
command: `Docs/WindowsBuildProcedure.md`.

## Version control

- **git** covers source, tooling, docs and config only. Content is excluded by
  `.gitignore`.
- **`D:\PussStageBackups`** holds full snapshots including the 46 GB of Content.
- **`Backups/Pre<Thing>-YYYYMMDD-HHMM`** are taken before editing C++ or
  mutating the Show. Git does not cover the Show asset or the level.

## Automation

Two Unreal editors run on this machine. **PussStage serves MCP on port 8010**;
MHFat holds 8000. Drive Puss from Bash:

```bash
python Saved/CodexMocap/mcp_request.py tools/call --params-file <request>.json
```

Scripts live under `Saved/Codex*/` (the executor refuses paths outside `Saved/`)
and **must assert the expected world before mutating anything**, or a port
mix-up edits the wrong project in silence. See `Docs/CodexUnrealMCPRunbook.md`.

## Three tiers of proof

None substitutes for another, and this project has been bitten by confusing them:

1. A clean build with the new code proven present in the DLL.
2. A saved Unreal read-back with zero dirty packages.
3. Rendered visual acceptance, by eye.

Automation reaching green is not the look being right.

## Current state

- Plugin **0.15.0-container-look**. Suite **45/46** — the long-standing
  `SavedFixturePIE` curtain-marker failure is the only one, unchanged since
  14 September. **Do not describe the suite as green.**
- Night lighting is frozen at 00:00 for editor and PIE; foreign skies from
  Level Instances are suppressed; exposure is pinned.
- ~2,500 stage-light attachments across 261 wing pairs, with six flicker
  profiles. 136 of them cast volumetric shafts on every fourth bay.
- A generated timber **gridiron** (771 beams) over all six Passages, derived
  from the wing stations. Currently grey engine cubes — a look test, not the
  final pass.
- A Blender **cloth pipeline** for curtains and soft goods bakes to Alembic and
  imports as a Geometry Cache.
- Not yet done: ground grooves and wooden floor, wall bays, fixture bodies,
  wing materiality, effects sources, the Scene transitions.

## Reading order for a new session

1. `AGENTS.md` — the rules.
2. `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` — what is being built and
   who owns which files.
3. `Docs/InfinityStageSessionHandover.md` — the dated checkpoint.
4. `Docs/ShowBuildTodo.md`, `ShowCreativeTodo.md`, `ShowRehearsalTodo.md`.

Verify against the code before trusting any list. Both the handover and the
build list have fallen behind the work twice, and each time the next session
started from a false map.
