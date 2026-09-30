# Spec: HELD PATCH Q: a console variable gating the per-frame `MarkRenderStateDirty` on moving wing ISMs

Output: ONE file, `Scripts/patches/2026-09-30_Q_mechanism_renderstate_cvar.patch`, a `git diff` against HEAD. It must
apply with `git apply` (CRLF on checkout; match the format of the other patches in `Scripts/patches/`). The working
tree must be left UNCHANGED at HEAD.

## Why
A suspect for Gary's "smudged in motion" (unmeasured).
`Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp:~1461`: after the batch at
~1415–1460 writes each moving wing ISM's new instance transforms WITH explicit previous-frame transforms (the velocity
history), it calls `Component->MarkRenderStateDirty()`, every frame. A render-state recreate per frame may discard the
history the batch just supplied, so TSR and motion blur would see no motion vectors.

We need a LIVE A/B with no rebuild: a cvar.

## What to change
- **Add a cvar** in `InfinityStagePassageActor.cpp` (file-static `TAutoConsoleVariable<int32>`):
  - name `InfinityStage.Mechanism.MarkRenderStateDirty`;
  - default `1`, meaning EXACTLY today's behaviour;
  - `0` skips the `MarkRenderStateDirty()` call at that one site;
  - help text naming the site and the purpose (motion-vector A/B).
- **Nothing else changes.** The batch update and the history transforms stay identical in both states.
- If the batch-update function already marks the render state dirty or sends the transforms to the render thread
  itself, SAY SO in your final message, with the engine header line you read. That is exactly the evidence the A/B
  needs.

## Traps
1. The default must be byte-for-byte today's behaviour: the cvar read defaults to 1, and the call is unchanged when 1.
2. Only the ONE call site. There may be other `MarkRenderStateDirty` calls in the file; don't touch them, and list them
   in your final message with line numbers.
3. Read the cvar per call (`GetValueOnGameThread()`), not cached at startup, so it toggles live.

## Test
In `Plugins/InfinityStage/Source/InfinityStageTests/Private/` (an existing tests file in the same style, or a new small
one):
- **POSITIVE:** the cvar exists, defaults to 1, and can be set to 0 and back.
- **NEGATIVE:** a misspelled name is not found.
- If a mechanism update can be driven in a test world, also assert the instance transforms are identical with the cvar
  at 0 and at 1. If it can't, say so.

## Constraints
- Don't build and don't run Unreal.
- Tree at HEAD when done; the patch file is the only new file.
- Report: the patch path; the other `MarkRenderStateDirty` sites; what you could not verify.
