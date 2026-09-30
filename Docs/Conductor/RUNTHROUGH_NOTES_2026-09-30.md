# Gary's PIE run-through — 30 September 2026, afternoon

His words, grouped by what they are rather than by the order he saw them. He
pushed through with the Right key, so most of this is the **transport and the
show's spine**, which is the largest cluster and the one with no owner.

---

## 1. THE PRINCIPLE HE STATED, which several faults violate

> **"The cat spawning in front of the curtain. This should never actually
> happen — since we are already the cat's POV. We are always the cat when in
> passage or curtain view, effectively."**

And what should happen instead:

> "So after looking at the curtain we should then let it fall and start walking
> through the proscenium."

**A visible cat actor in front of the camera is a category error, not a
placement bug.** It appeared at P04 and again at P06. Anywhere the camera is in
a passage or looking at a curtain, the camera **is** the cat.

## 2. TRANSPORT AND SEQUENCE — the largest cluster, currently unowned

Owner would be Director & transitions (`InfinityStageTransportController`,
`MovieSceneInfinityPassageTrack`). **No session owns it.**

- **"Pushing through the sequence with Right key meant that lots of sections
  didn't seem to play right."**
- **Space does nothing at P01's lattice moment.** *"Hitting space on P01
  lattice-light-dark-bg moment does not play the movement — hitting right key
  goes straight to next section P02 start."*
- **Order is wrong on arrival at a passage.** *"We first see misloaded wings
  followed by cloth, and then the next step if I hit right is the cat spawning in
  front of the curtain."*
- **P05's hangar movement does not play, where P04's does.** It skips to P06's
  curtain moment.
- **P06 spawns the cat animation in front of the curtain, and both at once.**
- **Right from there does not fall the curtain and walk the passage** — it goes
  straight to the next hangar, **which also does not play.**

**P04 is the only hangar whose movement plays.** It is also the only one authored
by hand; the other five are the transplanted rises placed inert this morning.
That is the first thing to check.

## 2b. RESOLVED — THE TRANSPORT IS A CUE DESK, NOT A FAST-FORWARD

**RIGHT means "stand by the next cue", not "play what is on screen".** Verified
in source, and the contract is written in the header:

> *"Operator advance: play a sequence/interstitial, or a Scene when automatic
> Scene playback is enabled. **A new Passage remains held at its first frame.**"*
> — `InfinityStageTransportController.h:324`

After RIGHT lands: a **Sequence** plays to its boundary; a **Scene** plays only
if automatic Scene playback is on; **a Passage is HELD.** The project's own
automation test presses RIGHT **twice** to get Opening → Passage 1 → playing
Scene 1 **without ever walking Passage 1**
(`InfinityStageEditorAutomationTests.cpp:941-945`).

**SPACE is the go button** — `PlayForwardToBoundary`.

**So "pushing through the sequence with Right meant lots of sections didn't seem
to play right" is RIGHT doing precisely what it is specified to do.** Gary was
using it as a fast-forward; it is a stand-by. The same explains *"Right from
P06's curtain doesn't fall the curtain and walk the passage — it goes straight to
the next hangar."*

**This is theatrically correct rather than accidental**: an operator stands by a
cue while the performer settles, then executes it. RIGHT stands by, SPACE goes.
**Whether that is the model Gary wants is his decision, and it is a design choice
rather than a bug to fix.**

**"Space does nothing at P01's lattice moment"** is not explained by this, but his
log shows every input returned `result=0` — SPACE succeeded. The candidate that
fits a success with no visible movement is **already at the terminal boundary**:
`PlayTo` succeeds with no remaining distance. The un-nested Scene 1 rise (since
nested) would also mean nothing moved even on a successful play.

**WHAT IS LEFT GENUINELY UNEXPLAINED** after this and the nesting collapse:
- the **one-frame flash** to an empty dev grid at a Scene→Interaction crossing
  (mechanism identified, test pending);
- the arrival ordering, *"misloaded wings followed by cloth"*.
The cat is fixed. Everything else was correct behaviour, an un-made decision, or
a change the conductor approved.

## 3. LIGHTING

- **P01's flicker is constant-rate, expensive, and not effective.** *"P01's
  lights all flicker at a constant rate which seems both expensive and not
  visually effective."* **He asked whether the stutter is the flicker sequence.**
  See §6 — the code supports him.
- **The lattice is too dark to describe a space.** *"Lights completely cut off
  showing lattice lights, it's too dark overall so lattice lights don't imply
  much spatial structure and seem very abstract. It just needs to be a bit
  brighter to show the lattice."* **20 cd was enough to register; it is not
  enough to read as structure.**
- **The lattice needs weight**, deferred by him: *"more scaffold/rig structure to
  make the lattice more heavy looking, but we can look at that later."*

## 4. STRUCTURE — now seen rather than argued

> **"Looking left and right during walk shows that we need external structure,
> not necessarily blocking out everything, but the empty dusky desert we see
> outside is not acceptable."**

The qualifier matters: **not an enclosure.** The passage should feel situated
inside a stage structure rather than under an open sky.

## 5. DECIDED, and it deletes a job

> **"Remove all landscapes and replace them with the floors."**

This retires the whole S2/S3 landscape-hole investigation — no visibility layer,
no hole material, no C++ helper, and no owner needed for a task that turned out
not to be scriptable at all. It also removes the S2 and S3 swept-volume blockers
rather than allowing them, and **he expects it to help load time.**

Also: **P03's water still needs moving.**

## 6. LOADING

> **"P02 open curtain is OK although everything loaded at once and the
> background loaded less than a second before the curtain ruining the effect."**

A reveal that depends on what is behind it cannot survive the background
arriving after the curtain. Related to §5 by his own reasoning.

## 7. ALREADY IN HAND

- **"Curtain at very start needs to hold still before falling."** This is exactly
  what the **hold-at-479** change does — freeze the last pre-release sample so
  nothing moves before the fall. It is applied at P04 and waiting on `final13`
  for the Opening and the five transitions. **He has independently asked for the
  thing that was built this morning.**
- **P03 lacks a hangar or a curtain** — correct, and he assumed so.
- **P01 arrives at no curtain** — correct until `final13` lands.

## 8. PRIORITY HE SET

> **"P03 will be the first place I test how the characters and scenes might work
> with the hangar."**

So P03 is the site that matters next, not P04.
