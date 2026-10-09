# Codex job 56 — chandelier candle flames (offline build of an Unreal DRY/APPLY tool), 9 Oct 2026

Requested by Gary via "Blender MCP Hyper3D"; job number and reuse rules from Conductor 5. **Follow `Docs/Conductor/codex_briefs/_house_rules.md` in full.** Run with `--worktree`. **No live Unreal run in this job**: the --unreal run goes later in Conductor 5's editor queue. Any tool you write must NEVER end PIE or quit the editor.

## Goal
A DRY/APPLY/REVERT project-Python tool that, given a placed chandelier static mesh with sockets `Candle_01..NN` (from job 55, `chandelier_<Name>_sockets.json`), attaches one candle-flame effect per socket.

## REUSE, don't build new
- `/Game/Scenes/Effects/BP_Effect_Candle`:
  - an `InfinityStageEffectSource` BP; activation goes via UFXSystemComponent, `InfinityStageEffectSource.h:24-26`;
  - its `FlameFX` Niagara component is EMPTY (`Docs/Conductor/EFFECTS_PLAN_2026-10-07.md:51`).
- Flame look: `NS_Stylish_Fire_1`, as used by the P06 FX tools. Pattern: `Saved/CodexConductor/P06FX_20261008/p06_fx_blueprints.py` and `p06_fx_common.py`. That pattern is create-only children; never edit source StarterContent / marketplace assets.
- Flicker: the bulb-body FlickerModes in the plugin. Grep `Plugins/` + `Source/` and cite `file:line`.
- Swing: p52 (`Docs/Conductor/codex_briefs/p52_pendulum_swing_from_motion.md`) owns the pendulum. Flames attach to sockets so they ride the swing; do not implement the swing.

## Requirements
- A create-only child BP (e.g. `BP_Effect_ChandelierCandle`) or a child Niagara asset, with the flame scaled down to candle size (~3–5 cm flame).
- If a light is used: small radius, CastShadows OFF, low intensity, flicker on.
- Never auto-activate. Activation is cue-driven via the existing Effect path.
- The APPLY target is a chandelier actor named in an args JSON. The tool:
  - spawns or attaches N effect components or child actors, one per socket;
  - tags them for clean REVERT;
  - writes an originals JSON BEFORE any change (memory note `puss-bench-originals-to-file`);
  - saves only the affected packages, never Save All.
- DRY: list the sockets found, what would be created, and the asset paths. It writes nothing.
- Success marker only after asserted returns + save + read-back (memory note `puss-assert-dont-print`). Stamp log markers with a run id.

## Harness (offline; no editor)
- Pure-Python unit tests of the socket-JSON parsing, the plan builder and the REVERT tag selection.
- Negatives that must FAIL:
  - no sockets;
  - a missing BP_Effect_Candle path;
  - an args JSON naming a non-chandelier actor;
  - an APPLY without a confirm token.

## Deliverable
- Tool paths in your worktree; harness counts.
- The exact ordered commands for Conductor 5's --unreal queue: DRY → APPLY → read-back → REVERT check.
- Open questions.
- Evidence tiers on every claim, with `file:line`.
- Write `DONE_p56.txt` in the worktree root.
