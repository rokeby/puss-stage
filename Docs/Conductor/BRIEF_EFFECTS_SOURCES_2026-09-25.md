# Effects sources — brief

For the session **"Puss · Effects sources"**, from the conductor session, 2026-09-25.
Read `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md` first, then this.

**This stream starts late, and that is deliberate.** Your emitters plug into
bays that do not exist yet and feed volumetrics that are still being tuned. Do
not begin building until the conductor says the gridiron and ground are in.
Design and reading can start now.

## What the user wants

> "some sources of haze pumping out and some sources of fire, even"

Practical effects sources as part of the machine: smoke machines sitting in the
wings actually pumping haze, fire sources, steam. Visible apparatus, not
invisible ambience — the audience should see where the atmosphere comes from.
Baroque stagecraft register: this is a theatre that makes its own weather with
physical devices.

Crucially, these feed the lighting. The volumetric beams (136 shaft-casting
fixtures on every 4th bay) only read against a medium; **local emitters are what
make a shaft visible *here* rather than everywhere**, which is the difference
between atmosphere and uniform fog.

## What you own

- New **Haze / Fire / Smoke** attachment kinds and their Niagara systems.
- New plugin files only — never another stream's.

## The one shared change you must not make yourself

Adding an attachment kind means extending **`EInfinityAttachmentKind`** in
`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h`, which
is shared with Rig & atmosphere. **That enum change goes through the conductor
once.** Ask for it; do not edit the file. Everything downstream of it — your
Niagara systems, your spawn path, your parameters — is yours.

The existing kinds are `Prop`, `Light`, `AnimationTrigger`, `Sound`. Attachments
already carry an anchor (`Station`, `LeftPanel`, `RightPanel`, `TopPanel`,
`PairCentre`), a relative transform and per-kind settings — so once the enum
exists you inherit placement, replication across bays, and the actor-move
write-back for free. Study how `FInfinityStageLightSettings` hangs off
`FInfinityCueAttachment` and follow that shape.

## What the machinery already gives you

- **Placement by bay.** Attachments are placed from compiled wing stations, so a
  haze source every Nth bay is a match rule, not hand placement.
- **Replication.** The Cue Desk's *Replicate First Pair's Lighting* pattern —
  tune one pair, copy across Selection / Whole Passage / Entire Show, with or
  without seeded variation. The same approach should work for emitters; look at
  `ReplicateLightAttachmentsWithVariation`.
- **Write-back.** Moving a placed attachment in the level writes its offset back
  into the Show. Keep that property for emitters: it is how the user art-directs.

## Constraints

- **Performance is already tight.** The VSM one-pass shadow limit is overflowing
  with ~541 shadow casters plus 136 volumetric ones, across ~2,500 light actors
  and 261 wing pairs. Niagara haze interacting with volumetric fog is expensive.
  Budget before building, and prefer few good emitters to many.
- Fire is a light source as well as an effect. Coordinate its **light** with Rig
  & atmosphere rather than adding rogue lights — they own lighting.
- Volumetric fog settings are theirs too: density 0.022, falloff 0.12,
  extinction 0.9. Your emitters should work *with* that global medium, not fight
  it with their own dense local fog.
- Headless success is not rendered acceptance. The user judges by eye, at night,
  under raking beams.

## Working rules

- Source is in **git**; commit your own work only.
- Take a `Backups/Pre<Thing>-YYYYMMDD-HHMM` snapshot before mutating the Show or
  the level. Git does not cover them.
- Puss serves MCP on **port 8010** (MHFat holds 8000). Assert the expected world
  before mutating anything — a port mix-up otherwise edits the wrong project in
  silence.
- Builds need the editor closed and go through the conductor.
- Never Save All.
- Report status to the conductor session **"Puss · Conductor"** via `SendMessage` at milestones: one line, DONE / NEXT / NEEDS-YOU. Route **decisions** there too — anything touching a shared file, the build, the Show asset, the level, or another stream's ownership is the conductor's call, not yours.

## Relevant code

- `Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageTypes.h` —
  `FInfinityCueAttachment`, `EInfinityAttachmentKind`, `EInfinityAttachmentAnchor`,
  `FInfinityStageLightSettings` (the shape to imitate).
- `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStagePassageActor.cpp`
  — `MaterializeAttachments` spawns and owns attachment actors.
- `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageShowAsset.cpp`
  — `ReplicateLightAttachmentsWithVariation`.
