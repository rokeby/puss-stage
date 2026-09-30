# Spec: HELD PATCH Q v2: REPLACE `Scripts/patches/2026-09-30_Q_mechanism_renderstate_cvar.patch`

Q v1 (in the repo now) adds cvar `InfinityStage.Mechanism.MarkRenderStateDirty` (default 1) gating the per-frame
`Component->MarkRenderStateDirty()` at `InfinityStagePassageActor.cpp:~1461`.
- Its flaw: the batch update is called with `bMarkRenderStateDirty=false`, and the engine header
  (`D:/Unreal Engine/UE_5.8/Engine/Source/Runtime/Engine/Classes/Components/InstancedStaticMeshComponent.h:383`) says
  that flag is what makes the change visible.
- So cvar 0 may FREEZE the wings on screen, and the smudge A/B can't be judged.
- Gary measured that FXAA removes the in-motion smudge (TSR history). The suspect is the per-frame render-state recreate
  discarding the per-instance previous transforms.

## Change: one cvar with three values
- **1 (default, EXACTLY today):** batch with `bMarkRenderStateDirty=false`, then `Component->MarkRenderStateDirty()`.
- **0:** batch with false, and NO recreate. A diagnostic: it tells whether anything else pushes transforms.
- **2:** batch with `bMarkRenderStateDirty=true` on the component's LAST contiguous span only (false on earlier spans),
  and NO separate `MarkRenderStateDirty()`. This is the engine's own visible-update path.
- Read the cvar ONCE per component per frame, before its spans, via `GetValueOnGameThread()`. Treat any value outside
  0..2 as 1.
- Update the help text to describe all three values and the A/B:
  - 1 vs 2 for the smudge;
  - 0 = freeze diagnostic.

## TRAP
`FlushContiguousSpan()` can run SEVERAL times per component per frame, once per contiguous run of instance indices,
plus the final flush.
- Passing true on every span would mark the component dirty repeatedly (the header: "only set this to true for the last
  instance").
- Restructure minimally: collect the spans, or pass a flag into the final `FlushContiguousSpan()` call, so that only the
  last `BatchUpdateInstancesTransforms` call of that component gets true when cvar == 2.
- Mode 1 must stay byte-for-byte today's behaviour.

## Tests (replace Q v1's tests in the patch)
- The cvar exists, defaults to 1, and accepts 0, 1 and 2 (set and read back); a misspelled name isn't found.
- In the existing undulation fixture (`InfinityStageCompilerTests.cpp`, where v1 added the cvar-0 transform check),
  evaluate the crest with the cvar at 0 and at 2. The instance transforms must equal the cvar-1 result within 0.001.
  Restore 1 at the end.

## Output
- REPLACE the same file `Scripts/patches/2026-09-30_Q_mechanism_renderstate_cvar.patch`, a `git diff` against HEAD
  (CRLF like the other patches).
- Leave the source files unchanged, so only the patch file differs.
- Don't build and don't run Unreal.
- Final message:
  - `git apply --check --ignore-whitespace` result;
  - how you made "last span only" true;
  - what you couldn't verify.
