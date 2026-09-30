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

That last one is the cheapest and it reuses what exists. **It is also the one
that most resembles a theatre.**

---

## What is NOT changed by this

- The hangar rises themselves, the Arrivals, and the one-curve-two-evaluators
  handover at the Scene boundary. Those drive **geometry**, not cameras.
- The cloth work, the coverage fix, the at-rest gate.
- Scene 3's cast staging decision, which is about where people stand.
