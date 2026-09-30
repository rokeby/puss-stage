# Today as a Codex experiment

Gary, 30 September 2026: shift large amounts of actual coding work, and any
expensive work that does not need judgement, onto Codex — and treat today as an
experiment in doing so.

This document is the experiment's design, its live state, and the place its
result gets written. It is meant to be read at the end of the day and answer one
question: **what can this project safely stop paying Claude to do?**

---

## 1. The selection rule

The wrong question is "is this task hard?" Codex is capable. The right question
is **"if it is confidently wrong, how long before we find out, and what does it
cost?"**

So tasks are chosen by their **verification cost**, not their difficulty:

| Output shape | Verification | Delegate? |
| --- | --- | --- |
| A patch that must compile and pass the suite | The build and the suite say so | **Yes** |
| A finding citing `file:line` | Spot-check three citations | **Yes** |
| A script producing a number we can cross-check | Run it against a known case | **Yes** |
| A list of untested hypotheses | Each carries its own test | **Yes** |
| A judgement about how something looks | Nothing checks it | **No** |
| A Show asset or level mutation | Backup, dry run, read-back, revert | **No** |
| Anything on today's critical path | A capacity failure costs the day | **No** |

The failure mode to design against is not "Codex cannot do it". It is **Codex
producing something plausible that nobody can cheaply check** — which moves the
cost from doing to verifying and saves nothing.

## 2. What is running today

Launched about 10:20, all read-only, all printing to stdout, logs under
`Saved/CodexRuns/`.

| # | Task | Why it qualifies | How it gets judged |
| --- | --- | --- | --- |
| **A** | Audit `PussProjectTaskTracker.md` against source | Pure grep over a document already known to be stale. Nobody is blocked on it. A wrong answer costs a spot-check. | Every EXISTS must cite `file:line`. Spot-check three. Any UNCLEAR must say what was searched. |
| **B** | Landscape-hole investigation for S2/S3 | Currently blocked on nobody owning those environments. A written investigation makes the ownership decision cheap. Read-only. | Must distinguish what it read from what it inferred, and flag where UE 5.8's missing private `.cpp` makes behaviour unverifiable. |
| **D** | Adversarial review of today's commits | Machine-adjacent, and the repo took about twenty commits today from four streams. | Each finding cites `file:line` and is checkable in a minute. Praise is explicitly not the output. |
| **E** | Stutter: tested vs untested hypotheses, plus the cheapest decisive test for each | The most Claude-expensive open problem in the project, and still unsolved. Its output is a list of tests, each of which validates itself. | The report must separate "ruled out by measurement" from "not observed". If it blurs those, it is worthless and that itself is a result. |

**Deliberately NOT delegated today:** the backcloth integration (critical path,
and Rig is ready), the cloth acceptance decisions (judgement), anything that
writes to the Show asset or the level, and the lattice fade (Gary's call).

**Pending a stream's consent:** the 10 km gap in Rig's builder blocker test. It
is Rig's file, so Codex may draft it in a worktree only if Rig agrees — a stream's
files are not delegable by the conductor.

## 3. What Claude keeps doing today

Naming this matters as much as the delegation, because the saving comes from
Claude doing **less of the wrong thing**, not less work.

- **Deciding and sequencing** — who gets the editor, what reaches Gary, whether a
  result is trustworthy.
- **Judging** — every cloth verdict today turned on whether a number meant what it
  appeared to mean.
- **Talking to Gary.**
- **Anything on the critical path**, because a capacity failure there costs hours.

And the expensive Claude habits worth cutting regardless of Codex:

- Reading long logs in full when a `grep` answers the question.
- Re-verifying something a stream already verified and reported with evidence.
- Writing a long message where a short one does the same work. Several of today's
  peer messages were longer than the findings they acknowledged.

## 4. How today's result gets scored

At end of day, for each task: **did it produce something usable, and what did
verification cost?** Three outcomes, written down honestly:

- **USABLE** — the output was correct and checking it was cheap. Delegate this
  class permanently.
- **USABLE BUT EXPENSIVE** — correct, but verification cost as much as doing it.
  Delegate only when Claude is otherwise busy.
- **NOT USABLE** — wrong, or unverifiable. Record *why*, because the reason
  generalises further than the task.

Also recorded: **capacity failures**. Codex hit "selected model is at capacity"
twice on 30 Sep. Four concurrent runs is itself a test of whether that is a
throughput limit or bad luck.

## 5. Results

*To be filled in as each run lands. Nothing here yet.*

| # | Outcome | Verification cost | Note |
| --- | --- | --- | --- |
| A | — | — | — |
| B | — | — | — |
| D | — | — | — |
| E | — | — | — |
