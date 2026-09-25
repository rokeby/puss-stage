# Soft goods — brief

For the session **"Puss · Soft goods"**, from the conductor session, 2026-09-25.
Read `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` first, then this.

## What the user wants

> "lots of this requires getting naturalistic cloth, sack, velvet with some
> physics really right"

Cloth is structural to this world, not decoration: the show curtain that flies,
loose fabric hanging in the rig, peeling wing edges, dust sheets, sacking. It
has to read as **heavy fabric under gravity** — crumpling, creasing, lagging —
in a Baroque theatre, not as rubber or as a stiff sheet on a motor.

## What you own

- `Scripts/build_curtain_cloth_bake.py`
- `DerivedAssets/CurtainCloth/`
- The **Blender GUI** (exclusive — no other stream may drive it)
- Cloth-related content you generate under `/Game/Scenes/Curtain`

## Where it got to

A working Blender → Alembic → Unreal Geometry Cache pipeline, with two modes:

- **`fly`** (default): one batten lifts the whole drop straight up, fabric
  trails and sways. This is what the user asked for.
- **`festoon`**: hem lift lines gather it into swags. Built first, then rejected —
  "there's actually no need for drapery".

Current bake: 44,352 vertices, 405 frames at 30 fps, timeline
settle → rise (4 s) → hold → lower (3 s) → settle. Imported as
`/Game/Scenes/Curtain/Cloth/GC_CurtainCloth_Festoon_V1` (name predates the mode
switch). A preview actor sits near Passage 1.

**The physics that finally worked**, after three wrong turns:

| | value | why |
| --- | --- | --- |
| mass | 0.05/vertex | ≈7 kg/m². At 1.2 it was ~200 kg/m² and wobbled like jelly |
| tension / compression | 200 / **3** | fabric will not stretch but folds for free. Equal values made it a plate that bulged in smooth rolls — the "waxy" look |
| bending | 0.1 | cheap creases |
| self friction | 30 | folds hold structure through the lift instead of sliding flat |
| quad | 9 cm, substeps 12 | fine enough to represent a crease |

**The lesson to carry:** the user spotted that early wrinkles "seem to be drawn
on in repeated patterns" — and he was right, they were per-vertex noise I had
seeded into the start pose. A flat rest shape means the solver never removes it,
so it reads as a stamp. **Any wrinkle finer than the pleats must be earned by the
solver.** Do not fake surface detail in geometry.

## Your first jobs

1. **Material for the curtain.** It currently has none. The fire-safety curtain's
   4K TextileV5 weave and relief maps transfer directly — same UV convention.
2. **Velvet, sack and hanging-cloth variants** off the same pipeline: different
   sizes, corner-pinned, left to hang; peeling wing-edge strips; dust sheets.
   Brief from **Rig & atmosphere** on where they hang once the gridiron is timber.
3. **Sequencer integration.** Replace the transform-driven
   `BP_InfinityStageSequenceCurtain` in the opening and the five interactions
   with a Geometry Cache track, mapping the existing beats onto cache sub-ranges:
   **lower** ≈ frames 270–360 (3 s fall), **rise** ≈ 90–210 (4 s reveal), held
   frames for the covered changeover. The authored markers
   (`InfinityStage.CurtainFullyDown`, `HiddenChangeover`, `CurtainRiseStart`,
   `CurtainFullyOpen`) stay as they are. **Coordinate this one with the
   conductor** — it touches show sequences, which are shared.

## Honest limits

- No cloth solver models **crease memory** — plastic deformation. Fabric that
  stays crumpled is a *material* problem (crease normal detail on the shader),
  not more simulation. Say so rather than burning bakes on it.
- Bakes are minutes, not seconds: 44k verts × 405 frames with self-collision runs
  ~10–15 minutes. Run them in the background and keep working.
- Scale matters: simulate at true stage size (17.77 × 10 m) and place the cache
  at whatever scale the framing wants. A scaled-down sim falls like a handkerchief.

## Tooling

Blender **4.4** at `C:\Program Files\Blender Foundation\Blender 4.4`. Stay on
4.4 — 5.x removes the action API the older `Scripts/build_curtain_anim.py` uses,
and the cloth solver is unchanged.

Blender MCP is installed: add-on at
`%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons\blender_mcp_addon.py`,
socket on **9876**. Launch ready-to-drive with:

```bash
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" --python /e/PussStage/Scripts/blender_mcp_launch.py <file.blend>
```

Note 9876 is also the GO1 dog's UDP telemetry port — different protocols, they
coexist, but that is why you may see the number twice.

The BlenderGPT add-on throws an `unegister_class` error on every shutdown. Noise,
not a failure; ignore it in logs.

## Working rules

- Source is in **git** — commit your own scripts. `DerivedAssets/` is not in git;
  it is covered by snapshots to `D:\PussStageBackups`.
- Puss serves MCP on **port 8010**; assert the expected world before mutating.
- Never Save All.
- Report status to the conductor session **"Puss · Conductor"** via `SendMessage` at milestones: one line, DONE / NEXT / NEEDS-YOU. Route **decisions** there too — anything touching a shared file, the build, the Show asset, the level, or another stream's ownership is the conductor's call, not yours.
