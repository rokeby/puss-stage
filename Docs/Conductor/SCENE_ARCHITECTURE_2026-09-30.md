# Scenes are placeholders, and what that unlocks

Gary, 30 September 2026, afternoon. **This is the most consequential thing said
today**, because several open decisions were expensive only on the assumption
that scene infrastructure was authored work worth preserving.

---

## What he said

> **"Other than some minor character placement on Scene 3, none of the scenes are
> placed, and all of the existing scene infrastructure — the hand-on/hand-off
> cameras, the sequences — are purely placeholders.**
>
> **We can in fact rethink whether hand-on or hand-off cameras are necessary in
> the first place, if the scenes essentially cut to a predefined sequence. The rig
> comes up, the lights strike, and then we cut into the scene's sequence.**
>
> **The only question then is how do we exit the rig moment and move into the next
> passage. That may require further development of how the hangar rig box works to
> lead us to the next passage opening — which was roughly the role of the hand-off
> camera, and the reason for nested sequences."**

## The architecture he is describing

**ENTRY IS A CUT.** Rig rises → lights strike → **cut** into the scene's own
sequence. No handover camera, no blend, no retained-camera machinery. The
transition's drama is the rise and the strike, which already exist.

**EXIT IS THE UNSOLVED PROBLEM**, and it is a **mechanism and staging** question
rather than a camera one: **how does the hangar box lead you back out to the next
passage opening?** The hand-off camera was standing in for an answer nobody had
designed. That is why nested sequences exist.

---

## What this makes cheap that was expensive

### 1. The stale Master — the blocker becomes a chore

The Master is **425.265 s** out of step with the Show from Scene 3 onward.
`Docs/SceneTransitionRepair-20260914.md` suggests Scene 3's 585.64 s was
**authored and deliberately preserved**, which made a rebuild dangerous: it could
destroy real work.

**If the scenes are placeholders, there is little or nothing to preserve.** A
rebuild stops being a risk to be managed and becomes a job to be done. **This is
the single biggest unblocking consequence** — over half the show sits downstream
of that 425 s.

*Caveat to confirm with him: Scene 3 does hold placed characters, the Shore cast
and the Celadon set. Those are level actors, not sequence data — but anything
**keyed** in `LS_DevScene_03` should be checked before it is rebuilt.*

### 2. Scenes 2, 5 and 6 being too short — trivial

They are 15 s against hangar rises of 31, 49 and 31 s, which blocked nesting.
The cost was that lengthening them moves every later segment's timing on an
already-stale timeline. **If they are placeholders, lengthening them destroys
nothing** — and it should be done in the same pass as the Master repair.

### 3. The one-frame flash — possibly DELETED rather than fixed

A Scene→Interaction crossing shows one frame of empty dev grid, and the mechanism
looks like Sequencer restoring its pre-animated view target when a camera cut
section ends. **If handover cameras go away, so may the cut sections that
restore.** Fix the mechanism only if it survives the architecture.

### 4. The handover machinery itself — a candidate for deletion

`SceneEntryBlend`, `PassageEntryBlend`, retained cameras, covered handoffs,
`bRevealNextPassageWhenCovered`, and the nested sub-sequence structure exist to
serve hand-on/hand-off. **Nothing should be deleted yet** — but nothing should be
*repaired* on the assumption that it stays, either.

---

## The real work this exposes

**How does the box let you out?**

The rise is solved: the box comes up, assembled and dark, and the lights strike.
Nothing has ever been designed for the other end. Candidate directions, none of
them his yet:

- **The box opens.** A wall, the roof, or the mouth it rose from gives way, and
  the next passage is beyond it.
- **The box falls away**, the reverse of its arrival, leaving you at the next
  passage mouth.
- **The passage arrives**, rather than the box leaving — the next passage's
  structure rises or slides into the box.
- **A curtain closes the scene** and the box is simply gone behind it, which
  rhymes with the transition drape already being built.

That last one is the cheapest and it reuses what exists.

---

## THE PROPOSAL ON THE TABLE: the hangar IS the house

Look & camera, 30 Sep. **Better than the four above, and the reason is their own
line: "it's a trick where the first option is a place."** The four are mechanisms
for getting the cat out of a box. This makes the box somewhere he already knows
how to be.

**The Opening is a house** — stalls seat, parquet, gilded ceiling — looking at
P01's proscenium with its drape. **Every hangar becomes that house again.** The
room rises around the cat, the lights strike, we cut into the Scene. At the
Scene's end **the hangar's FAR WALL opens, and behind it stands the next
Passage's proscenium with its drape.** The cat takes a stalls seat inside the
hangar; the Interaction's shadow play runs on the drape; the drape falls; he
walks out of the house onto the next stage.

**No teleport, no hand-off camera, no retained-camera machinery.** The box leads
you to the next opening, which is exactly what Gary asked for.

**The geometry already fits**, checked not assumed: the far wall is 21 × 30 m
against a 19 × 10.5 m portal, so the proscenium sits inside it with room to
spare; the stalls seat 14 m back from the portal is 46 m from the Scene's stop,
inside the 60 m nave.

**Most of it follows a docked Passage by construction** — the drape lives at the
mouth, the portal is built at the route start, and the **camera RIGS** derive
their transform from the route spline every evaluation, so a moved Passage
carries them.

**CORRECTED 30 Sep, by its own author: the five TRANSITION STALLS cameras are NOT
derived.** They are placed once by a script that refuses if they already exist.
After a docking move they must be **re-seated in place** — not replaced, because
the Interaction cuts bind them **as actors**, so new ones would break the
bindings. A small script, for moved mouths only. **The Scene handoff cameras are
also static copies** taken at match time, so adjacent Scenes need a gated
rematch after any move.

**Cost sits almost entirely with Rig:** dock each Passage N+1's mouth at Hangar
N's far wall, and give the far wall an opening mechanism (the fold vocabulary in
reverse — hinging down and outward, drawbridge-style). Soft goods: nothing new.
Look & camera: the move to the seat and the cut timing. Director: nothing, the
segment order is unchanged.

**Unknowns, stated by them:** the Passages sit in 800 m lanes, so docking carries
wings, lights and the celestial frame; P03's landscape may not want to move; and
whether the move to the seat is dog-driven or authored.

### THE FALLBACK, if docking is too dear: a match cut on the cloth

At the Scene's end the drape **flies in inside the hangar**, in front of a
stalls-seat camera there. Once it fills the frame, **cut to the real stalls
camera at the next mouth**, where the identical drape hangs in identical framing.
**The cut is invisible because the same cloth fills the frame at the same seat
geometry.** The world changes behind the curtain, which is how a theatre changes
scenes. One extra drape spawn and one camera; no docking.

### ONE THING TO PUT TO GARY IN HIS OWN WORDS

He said of the hangar: *"It's essentially a little viewing cinema… **the cat does
not walk through the box.** It's more like a cutscene."* The proposal has him
walking about 46 m to the seat and then out. **Taking a seat is not traversing,
and the exit is what he asked to design** — but it is close enough that it must
be asked, not assumed: **does the cat move inside the box, or does the box move
around a cat who stays still?** There may be a version where the seat is already
where he stands.

---

## AN INVARIANT THAT SURVIVES WHICHEVER ARCHITECTURE WINS

**Every Scene and Interaction sequence's camera-cut track must cover its ENTIRE
playback range.** An uncovered stretch is a segment with no camera rule, and
anyone who **jumps** into it sees the dev grid at the world origin.

**Found 30 Sep**, after three wrong hypotheses about a one-frame flash. A probe
into Scene 1's tail logged `INFINITY_HANDOVER_UNRESOLVED … 'Scene 1 — External
Sound' … NoRuleForSegment — no camera was claimed`, with the view target left as
the **player controller at (0,0,0)**. Scene 1's cut track covers **frames 0–375**
— 15 s at 25 fps — while **Scene 1 was restored to its full 210.8 s.** So the
tail has no cut section at all.

**Continuous playback hides it** by leaving the previous camera live. **A scrub
exposes it**, and the operator scrubs in rehearsal, which is when the show gets
judged.

**This gets MORE important under the new architecture, not less.** "Cut into the
scene's sequence" means each sequence owns its cameras outright, and there is no
handover machinery left to paper over a gap. **A fix to the handover would have
been thrown away with it; an invariant on the data survives.**

**AND THE REPAIR ALREADY SCHEDULED WILL CREATE THIS FAULT THREE MORE TIMES.**
Scenes 2, 5 and 6 are to be lengthened to 31 / 49 / 31 s so their hangar rises
fit. **Lengthening a sequence without extending its cut track is exactly what
created this.** So the invariant and its test are a **precondition** for that
work, not cleanup after it.

---

## What is NOT changed by this

- The hangar rises themselves, the Arrivals, and the one-curve-two-evaluators
  handover at the Scene boundary. Those drive **geometry**, not cameras.
- The cloth work, the coverage fix, the at-rest gate.
- Scene 3's cast staging decision, which is about where people stand.
