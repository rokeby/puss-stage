# Puss — creative production checklist

Content, lighting, aesthetics, scenes, sound. The making of the show, as opposed
to the machine that runs it.

Companion lists: [engineering](ShowBuildTodo.md) · [rehearsal](ShowRehearsalTodo.md)
Reasoning behind each line: https://claude.ai/code/artifact/7d8d8c4f-885c-436b-8b7c-9f7ef709d29a

**G** Gary · **K** Klara · **C** Cameron · **X** external animator

| Date | What |
| --- | --- |
| **18 Sept** | Organized script copy created; Mountains is isolated as the rewrite focus, but the rewrite is still open |
| **15 Sept** | Mountains/Cloud Wings/Animals package ready for Rob; external delivery is not confirmed |

---

## Sound production

- [ ] **D.3** (C) 9 missing stems — [list drafted](SoundDeliveryList.md), **not sent**. Needs your call on the 7 unspecified lengths first.
- [ ] **D.4** (C) Lock stem lengths before any passage aesthetic work. Wing count derives from music duration; a later length change re-fits the passage.
- [ ] **D.5** (G/C) Wing mechanism sound set per Passage. `Sound Effects/Theatre Winches Pulleys` already holds `Winch_1`–`Winch_4`.
- [ ] **D.6** (G) Approve all six music handoffs — Source In/Out and fades — on a proper device.
- [ ] **D.7** (K/C) Room test in the power station: recorded stems and live cello, before the mix is finished.
- [ ] **D.2** (G/K/C) Decide the cue feed for vocalist and cellist — countdown monitor, cue light, or click. Required now that UE owns the clock.

**Music analysis, 21 Aug:** all six rails at provider 0.3.0 with 7 feature curves and expressive sections. Note **P02 and P05 come back ambiguity `high`, and P06 has no stable tempo candidate** — on those three, pinning camera anchors is a musical judgement, not accepting a number.

## Scenes

- [ ] **I.5** (G/X) **S5 Mountains — package prepared, not confirmed sent.** [Brief_S5_Mountains.md](Brief_S5_Mountains.md). The 15 Sept Rob archive includes the brief, delivery contract, locked 152.341-second audio, analysis, 22 in-use cloud Wings, Klara's Deer/Pig/Raccoon content and manifests. Still to do: rewrite the Mountains script block, write the surtitle text, receive Cameron's current villagers, add a venue/framing reference if needed, then send/confirm receipt. [Organized script copy](https://docs.google.com/document/d/1sr0SHFizLQ6tOThyEJSlL_F76loGJcV3AqHig6R5OBY/edit).
- [x] **I.8** ✅ [Scene delivery contract](SceneDeliveryContract.md) — send it with every scene brief.
- [ ] **I.1** (G) S1 Animals — finish. Audio, lighting, replace the placeholder cue.
- [ ] **I.2** (G) S2 Shrine — build. `KK_S2_Shrine`, `Scenes/Wings/Shrine`, `Cauldron` and `Shrine_Scene` audio all exist.
- [ ] **I.3** (G) S3 Shore of Forgetting / Clam — build in full. Curate the interrupted Shore Mourning concepts before generating more.
- **I.3 progress, 12 Sept:** six pale, gaunt, pot-bellied MetaHumans are assembled, fitted to the six shore recordings, and placed by the clam with secured Chaos head drapes. `LS_Clams` has their individual slow motion sections; full takes and hidden mannequin originals are retained. Full-sequence play-mode motion/attachment checks passed. See [Shore cast delivery](ShoreCast-20260910.md) for assets and rendered review. Overall scene composition/lighting remains open.
- **Motion handoff, 17 Sept:** all six Shore takes plus `child1` and `child2` are packaged as body-only Animation Sequences with their matching source Skeletal Meshes in `Transfers/Klara_MetaHuman_Mocap_20260917.zip`. Checksums and byte-for-byte source comparison passed; Klara's receipt and retargeting remain unverified.
- [ ] **I.4** (G) S4 Children — finish, lighting pass.
- [ ] **I.6** (G) S6 The Void — finish the mocap, Niagara bee swarm, built for a dog loose on the stage.

## Curtain, opening, interactions, closing

**Asset baseline, 27 Aug:** the 17.77 × 10 × 0.10 m V2 fire-safety curtain is
imported with relief maps, its own opacity mask and a 4K TextileV5 Base Color.
That completes the technical asset baseline, not the final curtain look or any
real-world fire-rating claim.

- [ ] **B.4** (G) Design the opening — the sequence scaffold and curtain track exist; the proscenium reveal, opening-music cueing and final visual composition remain.
- [ ] **B.5** (G/X) Boy tantrum figures × 5, plus Puss's response to each. The five 20-second interaction sequences now provide a 12-second BoyCat window (frames 75–375 at 25 fps) and dedicated folders, but the actual figures/performance are not authored. Decide shadow-cast vs blurred-behind-fabric per interaction.
- [ ] **B.7** (G) Design the closing — the sequence scaffold and curtain close track exist; figures sweeping up the stage remain to author.
- [ ] **C.6** (G) Write the surtitle text. S5's rumbles are the clearest case; decide per scene whether surtitles carry narrative, translate non-verbal sound, or stay absent.
- [ ] **C.7** (G) Surtitle legibility — type size, bar opacity, contrast, at real throw distance in real ambient light.

- [ ] **C.P06-end** (G, 5 Oct) P06 has NO painted end curtain: "only darkness but the curtain's already on the ground on fire". Stage a fallen drop burning on the floor in the dark before S6. Owners: Soft goods (drop) and Effects sources (fire). Passage-end curtains P01–P05 are Fuser job 48.

## Passages — aesthetics and timing

- [ ] **H.2** (G) One stated idea per passage, written down. P1, P4 and P6 have none; P2, P3 and P5 already carry theirs in their wing families.
- [ ] **H.3** (G) Timing pass — what the dog sees and when. Ground events, a figure passing, something noticed late.
- [ ] **H.4** (G) Camera speed and framing per passage. Pin confirmed music markers as anchors first.
- [ ] **H.5** (G) Camera-led reveal per passage — `Reveal Ahead` and `Opening Ramp`.
- [ ] **H.6** (G) Music-driven wing movement — travel, cycle rate, phase bias against the musical sections.
- [ ] **H.7** (G) Ground plane per passage. Separate bays can carry different floors.
- [ ] **A.5** (G) Camera owner across all 19 cues. Interactions → Timeline, locked, so Gary can walk the dog without the projection swinging.

## Lighting design

- [ ] **E.4** (G) A stated lighting idea per section — all 19. Record the intent per cue as you go.
- [ ] **E.8** (G) Follow light behind the camera: on or off, decided per passage. Strong device; should not be uniform.
- [ ] **E.6** (G) Judge the Stage Opening relief and silhouette under grazing stage light.
- [ ] **E.5** (G) Wing texture and material pass — deliberately after the lighting exists, or you judge them twice. Passage 2's technical opacity-mask assignment is now correct 60/60; the aesthetic pass remains.
- [ ] **E.7d** (G/K) Design the house-light states against the UE lighting modes. A manual desk makes this more important, not less — nothing will auto-correct a mismatch.
