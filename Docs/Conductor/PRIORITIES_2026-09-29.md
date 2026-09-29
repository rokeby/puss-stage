# Priorities after the 29 Sep run-through

From Gary's full play-through, top to bottom. Ordered by **what most unblocks a
whole-show run**, which is the emphasis he set: "structural functionality,
continuity, operator functionality for the whole thing".

Each item says whether it is a **DECISION** (only he can answer), a **SETTING**
(minutes, no build), a **BUILD** (C++ / new capability), or **AUTHORING**
(content work in the editor).

---

## TIER 0 — blocking. Nothing downstream is judgeable until these clear.

### 0.1 Scene 3's true length — DECISION (him), then ~15 min

**He cannot get past Scene 3.** The readout says Passage 4; the playhead stays
with the metahumans. The transport computes segment positions from the **Show**
and plays the **Master**. Scene 3 is 160.375 s in the Show and 585.640 s in the
Master, so everything after it is **425.265 s** out of place. Confirmed live by
him, and confirmed read-only overnight.

This also explains "I can go there outside PIE but not inside it".

`Docs/SceneTransitionRepair-20260914.md` says the 585.64 s was his **authored**
Scene 3, deliberately preserved — which suggests the *sequence* lost its length
(it is also the only 24 fps sequence in the show, consistent with migration
damage) and the Master is the surviving record.

**Unlocks:** Passages 4, 5, 6; Scenes 4, 5, 6; Interactions 3, 4, 5; the Closing.
Over half the show.

### 0.2 The ~1 Hz frame drop — MEASURE, then fix. He calls it "very core".

40 fps dropping to ~12, rhythmically, about once a second, throughout.
Ruled out already: no timers or tick intervals anywhere in the InfinityStage
plugin; no SceneCapture actors in the level; not MHFat contention (a periodic
beat is a timer, not load — and MHFat is now idle under a yield flag).
**Next step is `stat unit` / `stat unitgraph` during a spike** — Game vs Draw vs
GPU names the owner. Must be caught in the act.

### 0.3 The floor is 49.5 cm too high — DECISION (him), then SETTING

"Passage 01 — Opening Floor": an engine Cube at scale Z 1 where it wants 0.01,
so its top sits at **+49.5** instead of 0. Everything else — boards, slots,
understage, forestage, the whole stage front, and the curtain bake — is built to
**z 0** and is buried underneath it. There are two of these slabs.

**He likes the floor** ("a great shiny, waxy kind of wooden floor texture"), so
this is not a removal. It is a height fix. But it is an actor nobody in the
project authored, so the call is his.

**Unlocks:** enabling the portal, placing the curtain, and part of why there is
no sense of ground structure.

---

## TIER 1 — operator continuity. His stated emphasis.

### 1.1 The camera does not follow the route — BUILD

On a curved passage the camera "just points directionally forward as the path
curves". It should look **down** the path. This is the single most damaging
thing to the sense of travelling through a tunnel.

### 1.2 Mouse look fights the fixed camera — BUILD / DECISION

Mouse look works, and so does the dog equivalent, but it is "completely
fighting" the sequence camera. Needs a defined rule: who owns the camera when,
and how a look-around is layered on a driven shot rather than competing with it.

### 1.3 Transitions must be hidden behind the curtain — AUTHORING + BUILD

Currently the passage "suddenly jumped into view" and then the curtain opens.
The sleight of hand requires the **teleport to happen while the curtain covers
the view**. He identified the asset in use: `BP_InfinityStageSequenceCurtain_C`.
The Scene 2 to Scene 3 seam is worse: it snaps into the next sequence's lighting
and position already past the first or second wing, then plays a close, low-res
fire curtain, then snaps again into cat view.

### 1.4 A curtain at the end of every passage — AUTHORING

He stares down the tunnel at the dusky end and then simply arrives. A curtain at
each passage end stops the scene being visible before it is revealed. All seven
Sequence blocks reportedly already carry a keyed curtain spawnable — **verify**.

### 1.5 The drape as the opening curtain — AUTHORING

The Opening currently plays the **old fire-safety curtain**, close to camera and
soft. He wants the baked drape. The bake exists (`final3_stage_v2_q30.abc`) and
is blocked behind 0.3.

### 1.6 Remove the `CurtainChaos Preview` actor — SETTING, minutes

**The curtain he walked through never falls because nothing is wired to it.**
It is Soft goods' development preview, left in the persistent level at x=5400,
a few wings into P01. No sequence drives it and no cue references it. That single
actor accounts for three separate observations: a curtain sitting behind the
third or fourth wing instead of covering the front of the stage, a curtain he
walks straight through, and **15,025 simulating cloth vertices** running every
frame for nothing — against his "least lag" requirement.

The real Opening curtain is the baked drape and is a separate object, not yet
placed.

### 1.7 Interaction 3 does nothing — INVESTIGATE

No curtain came down; the sequence simply stopped. Likely downstream of 0.1.

---

## TIER 2 — the machine. The theme running through every note.

> "A wide, dusky, empty space rather than inside a big machine."

### 2.1 A hangar at every scene, including where no scene exists yet — BUILD

His instruction: where there are no scenes, **a giant empty hangar**. Not a void
with an infinite floor. This is the single biggest missing thing after Tier 0.

### 2.2 The Scene Volume does not exist — BUILD

**Verified:** a Scene in code is a sequence reference, a duration, a camera
owner, a music binding and handoff timings. No geometry, no space. The structure
actor knows only Passages — its only mentions of "Scene" are Unreal's own
`SceneComponent`. His own Director Specification defines a Scene Volume backed by
a Data Layer or Level Instance; it was never built.

**Interim:** a structure can be offset along its route, so a portal or gridiron
can be pushed to where a Scene camera sits — a Passage's rig standing in a
Scene's place. Crude, but it gives him mechanism to look at today.

### 2.3 Level Instances for scene content — ANSWERED: yes, with one hazard

His spec names Level Instance as a Scene Volume backing. **Hazard:** the existing
scene maps carry their own lighting — `Scenes/Main` has 4 directional lights, 4
sky lights, 4 height fogs; the Shrine map 3/4/3. Instanced as-is they override
the show's authored lighting, which happened in September. Strip sun, sky and fog
from a scene map before instancing.

### 2.4 Visible rigging — AUTHORING + BUILD

Nothing shows where the wings slide in and out or up and down from. He wants
**pistons, struts, rigging**. And an **outer supporting armature or scaffolding**
around the whole thing.

### 2.5 The pop-up book — DESIGN, then BUILD

Replaces the "mechanical coil" idea. Not one coherent machine but **things that
hinge up, unfold, fold away and fall down** — wings, and **the floor itself**,
"in that inception type of way". The scene should **hinge into view** as it is
revealed, rather than being approached and stared at. Alternatively the camera
descends. Either way: a sudden change of dimensionality, from a flat 2D journey
down a flat plane into a hinged world.

---

## TIER 3 — lighting. Half the show is dark.

### 3.1 Baseline lighting on P04, P05, P06 — AUTHORING

- **P04**: "completely underconsidered". Interim: arrange the existing wings in
  an orderly way and light them like P01, so there is something to see.
- **P05**: "barely lit", and long. Wants **gentle Baroque cloud painting,
  Raphael** feeling. Structure matters more here, not less — clouds have no
  architectural weight, so the rigging must be felt more strongly.
- **P06**: "a really nice set of wings" — billowing sacks, scaffolding, sand
  dunes, "structural undoing", poetic and dreamy. **Totally underlit.** Needs
  the P01/P02 treatment with a slight variation.

### 3.2 More blinking spots with shadows — AUTHORING. **The thing that works.**

The blinking spotlight with a shadow in it near the end of P01 is "really
effective". He wants many more. **Lights from the side into the centre of the
passage are good.**

### 3.3 Shadow puppets — DESIGN + AUTHORING. Cheap, and in the show's language.

Characterful shadows as a feature of every passage. Flat interior **shadow
puppets**, like the wings, so characters and ideas are *intimated* rather than
modelled as full assets. Also the home for the **boy-and-cat interactions**:
after each scene the curtain comes down, a spotlight plays their conversation as
shadow puppetry on it, the spotlight dims, the curtain collapses, and we arrive
in the next passage.

### 3.4 P03 — AUTHORING

Flat panels need lighting work; wants it "less completely flat", more **optical
illusion**. Needs more happening on the ground.

---

## TIER 4 — easy wins. Settings, minutes each.

- **Moving wings blur.** Sharp when paused, smeared when moving, making the scene
  read far lower resolution than the floor. Motion blur or temporal upscaling —
  both are settings.
- **Remove P03's water pools.** The reflections are struggling. Keep the
  consistent flat wooden floor and add other features instead of the landscape
  water texture.
- **The cat's ear shadows** — two of them, bottom left and right. The movement is
  nice; he does not want two.
- **The first sequence's audio** did not appear to play to completion.
- **The curtain blocks only ~80%** of the stage — light leaks past both sides.

---

## TIER 5 — content. After the structure holds.

- **Scene 3 (metahumans with cloths on their heads).** The cloths work well. They
  need a different colour and texture, **more weight**, and higher deformation
  resolution. He wants more takes of them collapsing into chaos — **or** to
  replicate them with offset timing so they sway together and build to a frenzy.
  The metahumans need dressing differently. The background needs thought.
  **Wind is worth playing with**, since the cloths are pinned to their heads.
- **Scene 4** — important, many metahumans and the boy. Needs the same hinge
  reveal into a different architectural interior.
- **The final void scene** — "a massive hangar", a cosmic void with **a swarm of
  bees and an old lady**.
