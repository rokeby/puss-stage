# Spec B1: Cue List panel (operator view). Cueing stream, 5 Oct

**Status.** Spec only. There is no patch yet; it waits for a build window.

**Data it needs (all built and green, suite 132/0):**
- `UInfinityStageTransportController::GoCues` [decl, build A]: number, label, HOLD/PASS, absolute frame, segment.
- `IsHoldActive()` and `GetActiveHoldIndex()`.
- `ReleaseActiveHold()`.
- `JumpToSegment`, and the existing navigation that calls `OnNavigation` on the hold and vamp states.

## Where it goes

It is a new tab in the Cue Desk: a new Slate file `SInfinityStageCueList.cpp` (mine) plus a small registration patch to `SInfinityStageCueDesk.cpp` (editor UI owner, reviewed by the conductor).

In PIE it reads the PIE world's transport. In the editor it lists cues from a transient transport built with `BuildSegments(Show)`. It never writes to the Show.

## Layout (one screen, large type)

**Top band:**
- **CURRENT**: the number and label of the last GO crossed or held, plus the time elapsed since it.
- **NEXT**: the number and label, plus the **notes** (see below).
- A HOLD indicator, shown in red while the show is held.
- Buttons: **GO** (the same call as →/Space at a hold: `ReleaseActiveHold`), **Back**, and **Pause/Play** (the Cue Desk is the only pause when `bSpaceNeverPauses` is set).

**List:** the columns are #, mode (HOLD/PASS), time (mm:ss.f in the Master), segment, label and notes.
- Double-click a row to **jump** to the cue's settle frame. This is navigation, so it does not arm the hold.
- **Re-run** jumps one second before the cue and plays.
- **A–B loop**: play from GO n to GO n+1, repeating. It reuses the vamp machinery as a transient range and is released by GO.

## Notes per cue (operator text)

A new Show array, `TArray<FInfinityCueNote> CueNotes` with `{Number, Notes, Standby}`, keyed by cue number. Marker position stays the truth for *when*; the notes are the truth for *what the stage manager reads*.
- This is a Show field, so it is held patch CL-A2 to `ShowAsset.h`.
- A **standby** line appears 5 s before NEXT (configurable).

## "What this cue does" (automatic)

For GO n to GO n+1, the panel lists the tracks that have keys in that span: lamps, sound, FX and events. It reads data only, like `SequenceBindsTag`; it never evaluates anything.

## Tests (`InfinityStage.Cueing.CueList.*`)

- **Ordering:** show order across nested sequences equals `GoCues` order.
- **Jump does not arm:** after a jump to a HOLD cue, the next Tick returns no hold. The control is a cue crossed by play, which does hold.
- **A–B loop:** it releases on GO and does not leave a vamp range behind.
- **Notes round-trip by number:** with no CueNotes, the panel shows labels only, unchanged.

## Out of scope for B1

OSC/MIDI out to a real lighting or sound desk. The design leaves room for an "External" column on CueNotes.
