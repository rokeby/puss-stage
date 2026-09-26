# Transitions and scale — creative brief

From Gary, dictated 2026-09-26, ~02:15. Captured by the conductor.
**This is his description reflected back, not an implementation plan.** Where I
have interpreted or filled a gap, it says so. The dictation ended mid-sentence,
so the last section is incomplete.

## The shape of a transition

### The opening

A **light on a curtain that is already down**. The curtain is **heavy, thick,
plain Chaos cloth** — "nothing too fancy", a core fabric rather than drapery.

Then the reversal: **it falls to the ground.** Not a grand theatrical fly-out.
It drops, and through the gap it leaves we see the opening of the theatre
machine. The fallen cloth **stacks on the floor** and stays there as a low pile.

We then **travel in slowly**, take up the perspective, and **look around — like a
video game**, before starting down the passage.

### Travelling a passage

Movement is **choreographed and balletic**, not constant travel. It **coordinates
with the music**: faster and slower, with **pauses**.

### Arriving at the end of a passage

**Not** a light at the end of the tunnel. We **arrive at another curtain**. It
falls, as the first one did, and again leaves a **stack of cloth near the ground**.
Each curtain may **look a little different**.

Behind it: the scene, revealed — "dazzling".

### Inside a scene

Scenes are **scripted, cinematographed scenography**, and we **cut** between
shots. The cuts let us be somewhere spatially different.

But we are **still inside the machine**. A larger one — a sound stage, a grander
theatre — and we must still feel **walls and rigging** around us. The change
between passage and scene is a **change of scale**, not an escape.

## Tunnel and hangar (Gary, 02:40)

The architecture, in his words: the wing passage rigging is **like a tunnel**
that **reveals a huge "hangar" space**, which **we occupy for the scene**, before
finding **a subtle way to return to the passage** for the next part.

That settles several open questions at once:

- **Passage = tunnel.** Narrow, rigged, travelled through.
- **Scene = hangar.** Huge, volumetric, still unmistakably a built structure.
  A scene dock and an aircraft hangar are the same building type — the place
  where big things are assembled and flown. The machine does not stop at the
  tunnel mouth; it gets bigger.
- **We OCCUPY the hangar.** We do not pass through it. The scene happens while
  we are inside a volume, which is why cuts are available there and not in the
  passage.
- **Entry is a reveal; the return is subtle.** The asymmetry is deliberate and
  it is the interesting part. Arriving is theatrical — a curtain falls and the
  space opens out. Leaving is quiet enough that the audience does not experience
  it as a second event.

### What this resolves

- Rig & atmosphere's question about how Scene structure relates to Passage
  structure: the hangar is the **Scene Volume**, and the "one generator, two
  station sources" design fits it directly.
- Why scale contrast matters: tunnel → hangar → tunnel is a **rhythm**, not a
  single expansion. The narrow is what makes the vast read.
- Why cuts belong in Scenes and not Passages.

### Still open

- **How the subtle return works.** A reverse reveal would be a second event,
  which he has ruled out by implication. Candidates, none chosen: the tunnel
  mouth stays visible behind us the whole time; the hangar has more than one
  mouth and we leave by a different one than we entered; the return is covered
  by a cut, so we are simply back.
- Whether every Scene is a hangar, or whether the type varies (the void, Scene 6,
  he has already set aside as "may be quite different").

## The scale progression

Mapped to the real spine (6 Passages, 6 Scenes, 7 Sequence blocks).

| Scene | Subject | Scale |
| --- | --- | --- |
| **Scene 1** | animals, "campfire train wreck" | **relatively small** |
| **Scene 2** | the shrine | bigger |
| **Scene 3** | the shore | bigger, and the first time we open out |
| **Scene 4** | the school | **Baroque interior** — cathedral or school hall |
| **Scene 5** | the mountains | **grandest and most dramatic** |
| **Scene 6** | the old lady in the void | *"think about differently — may be quite different"* |

The point is not that each is bigger than the last. It is that the audience
**builds scalar expectations and has them played with**, while never leaving the
rigged machine.

## The idea the dictation ended on

> "one way we might do that is by having a different style of movement for the
> larger stage widths in the larger setting… we still have some kind of sense of
> mechanical movements of parts of the stage."

**Different movement vocabulary at different scales**, with stage machinery
visibly moving. The sentence was unfinished; the rest is Gary's to add.

## What this changes in work already built

Flagged by the conductor, not decided.

1. **The curtain falls; it does not fly.** Soft goods' Chaos curtain is currently
   hung from a pinned top row to be **flown up**, and the earlier Blender work was
   a *fly* bake. A falling, collapsing, self-stacking curtain is a different
   simulation: release the pins, let it collapse under gravity, and let it pile
   against the floor. The floor now exists (26,090 boards), so it has something to
   land on. The ragged pattern, the velvet, the weave and the physics all carry
   over.
2. **Curtains are plural and varied.** At least one per passage end, each a little
   different. That argues for one cloth asset with per-instance variation rather
   than seven authored curtains.
3. **This answers the transition question.** It is "the machine produces the
   scene" — the route already agreed — and it says how: a curtain drops, the
   machine opens, the scale changes.
4. **Scene environments need walls and rigging.** Currently a Scene is a Level
   Instance with its own content. If the audience must feel a surrounding sound
   stage at every scene, that is structure work at Scene scale, not just Passage
   scale — and it is not in any current brief.
5. **Passage movement must become musical.** The route evaluation is presently
   continuous. Choreographed movement with pauses is a timing and authoring
   problem, and it interacts with the Director's handover work.
6. **"Look around like a video game" at the opening** is the dog's free look —
   already the mechanism used for Scene 6.

## Not yet decided

- Whether every passage end gets a curtain, or only some.
- How the fallen cloth persists — does the pile stay for the return journey?
- What "different" means per curtain: colour, wear, weave, silhouette.
- Scene 6's treatment, which Gary has explicitly left open.
- The movement vocabulary per scale — the unfinished sentence.
