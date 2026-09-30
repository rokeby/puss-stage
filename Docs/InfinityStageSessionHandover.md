# Infinity Stage — session handover

**Current as of 30 September 2026, 02:00.** Supersedes the 25 September version.
Written by the conductor across an overnight run with three streams (Rig &
atmosphere, Soft goods, Look & camera) plus Wing materiality.

---

## 1. THE HEADLINE

**The show walks end to end for the first time.** Gary played it through on 29 Sep
and confirmed: *"works end to end in terms of operator"*. Every segment is
reachable. That was the day's blocker and it is gone.

**Show length is now 16:49** (1009.4 s), up from 13:17.6, because Scene 1 was
restored to its full 210.8 s and Scene 4 grew to hold the hangar rise.

---

## 2. WHAT IS NEW AND WORKING

### The Opening

- The **baked drape is placed** at the front of the stage with a stalls camera cut,
  replacing the old fire-safety curtain. Gary: *"the animation, the feel, looks good"*.
- **It falls.** The fault was a `running = False` flag on the GeometryCache
  component, which meant Sequencer never advanced it — it spawned, hung, and froze
  on frame 0. Proven by reading bounds back at frames 10/150/350 from disk.
- **The velvet still reads flat and orange.** Diagnosed as the LIGHT, not the
  material: the fold crests facing the house lights are bright and the troughs
  dark, which is the correct way round, and the same material read the same on
  28 Sep. Today's lighting is frontal and floods it. Rig's drape lighting is
  queued; the 28 Sep look is the reference.

### Transitions

- **Five transition drapes are placed**, one at each of Passages 2–6's mouths,
  each bound to its own stalls camera by tag. The fire-safety curtain is keyed off.
- **Five stalls cameras are placed**, carrying the Opening's exact seat (1400 cm
  back, +150 up, pitch +14°, 15 mm) to every mouth, derived live rather than typed —
  so P02 gets its 22.908° yaw from its bent route.
- **Portals are enabled at all six mouths**, with stage front, which is what makes
  one curtain bake serve them all. **S03 is FRAME ONLY** — Structure 03 has no
  ground, so there is nothing to build a stage front from.
- **The design settled**: the interaction happens ON the curtain (60 s+ of
  boy-and-cat shadow play), and it falls at the END, revealing the passage.

### Scene 4 — the hangar

- **A hangar exists and you can stand inside it**: 60 × 20 × 30 m, walnut
  herringbone floor, black-metal walls and roof, a 12 m lattice, ghost light and
  14 practicals.
- **v2 implements Gary's sketch**: the WHOLE BOX hangs below the passage floor,
  hinged 5 m ahead of the camera, and **rotates up as one thing**. It rises
  assembled and dark over about 15 s with only the ghost light glowing inside, so
  its glow breaks over the lip before the room arrives. Then lights strike, the
  roof swings over, the lattice flies in.
- **The walls' inward swing is dropped** — that was the thing that read as a box
  closing around you rather than a world unfolding.
- **The speed dial is the Hangar Fold section's Time Scale** in `LS_DevScene_04`.
  1.0 or faster is safe; slower needs `scene4_fold_nest.py` re-run.
- **Scene 4 is Dog Gaze** (applied 30 Sep 01:55): Puss keeps camera ownership, so
  peering over the lip and looking up at the stars are the dog's movement, live,
  in sync with the robot.
- **v1 is kept unreferenced** with a one-command revert.

### Lighting

- **P04/P05/P06 have baseline lighting**: 1521 lamps rewritten in place, GUIDs and
  positions kept, **shadow casters 1643 to 612**. P01–P03 fingerprint-proven untouched.
- **Six blinking gobo spots placed** across P02–P06, reproducing the one Gary
  praised in P01 — with **deliberately varied lens-to-gobo distance** (0.9 m to
  5.5 m) so each shadow has a different character, from vast and soft to small and
  hard-cored.
- **The hangar's upper volume is lit**: three shadowless uplights raking the far
  wall, and 24 emissive lattice bulbs. **At 30° of look-up it reads; at 48° it is
  still black** (grazing light on 4%-reflectance black metal).

### Floors and structure

- **Walnut on the boards** across all five passages with ground.
- **Steel grooves are real geometry** — recessed U-channels in each slot.
- **Floor material is unresolved.** Gary rejected the plank articulation
  (*"the floorboard like slats don't work great, we only needed the metal grooves"*).
  Options A (continuous herringbone) and C (dark waxed lacquer) are rendered and
  with him.

  **AND A MEASUREMENT THAT CHANGES WHAT THAT DECISION IS: THE GROOVES ARE NOT
  VISIBLE FROM EYE HEIGHT.** He approved widening them 8 cm to 16 cm; done across
  all six floors, it changed **0.05% of pixels** from the standing and rhythm
  views — and a difference image shows even that was temporal noise on the wing
  cards, not the floor. Only the close view down a slot changed (13.9%).
  **Because the slots start 150 cm inboard of each wing, under the wing bases.**
  So **width was never the legibility lever — `SlotInboardCm` is** (about 380
  would bring them toward the cat line). **As things stand his A-vs-C choice is a
  judgement about BOARDS, not about grooves.** The widening is harmless and stays;
  it simply achieved nothing visible.

### Build

- **88 passing / 1 failing / 89 total**, up from 84/1/85. Six patches applied,
  every one verified linked by UTF-16 string literal in the DLLs rather than by
  exit code. Zero hot-reload leftovers.
- **The failing set collapsed from five assertions to one.** The remaining red is
  `SavedFixturePIE` — **"Reverse navigation restores the retained Scene 1 exit
  camera"**, newly exposed once the five ahead of it were fixed. Soft goods'.

---

## 3. DECISIONS GARY MADE (his, not inferred)

| Topic | Decision |
| --- | --- |
| Transition curtain | A thing in the world, not a lens wipe. The interaction happens ON it; it falls at the end. |
| Hangar arrival | The whole box rises from below the horizon, hinged at the mouth. Assembled and dark, about 15 s. |
| Camera at the rise | Option C's image, but the look-down is **the dog's**, performed live — not a keyed track. |
| Horizon illusion | Dropped — irrelevant once the curtain is at the passage end. |
| The stars | **A glimpse of open sky between the curtain falling and the box enclosing is a BEAT, not a fault.** |
| Scene 4 ownership | Dog Gaze. Puss keeps the camera. |
| Fold lighting | Light it — practicals strike before the walls rise, so the lamps ride them up. |
| Mechanical-rig lighting | *"The passage rig again"* — the lattice carries the passage gridiron's own fixture housings. |
| Grooves | Widen to 16 cm on all six floors. |
| P01 casters | Apply P03's recipe — fill lights shadowless, key lamps keep shadows. |
| Portals | Enable at all mouths, full stage front. |
| Scene content | **Nothing in any scene is precious.** S01/S02 come from Klara later; S04–S06 are open. |
| Hangars | Build all six; **make them RESIZABLE**, since scaling to fit later content is the whole job. |
| Cloths | Bake freely. Structured hanging profile, the good fall already achieved, a couple of versions. |

---

## 4. OPEN — NEEDS GARY

1. **Floor: A or C**, once he has seen real grooves.
2. **The robot's own body pitch range.** Nobody here may command the GO1. Only the
   operator with the remote can measure it. `PitchRangeDeg` is the knob that
   matches the projection's look to the robot's once known.
3. **Scene 3's true length.** He said *"isn't done yet, will eventually be about
   3–4 min"*. It currently plays 65.5 s.
4. **The transition seat**, once the mouth lanterns light the curtains.
5. **P03's mouth** — frame-only, no stage front. Accept, re-bake against its
   landscape, or give Structure 03 ground.
6. **The pleat/pile trade**, if the hem-guide sweep cannot resolve it (see §6).

---

## 5. THE FRAME-RATE STUTTER — STILL UNSOLVED

**Ruled out by measurement:** cloth simulation, the celestial world-walk, wing
motion, all 432 flicker light functions, the shadow cache, every dynamic shadow,
lights-per-pixel, GPU contention with MHFat, the AI logging recorder, all eight
timers, scene captures and reflections, the Go1 socket, fog, the entire structure
kit and every wing, and PIE itself.

**What is established:**

- **The GPU is flat** — 14.8 to 15.5 ms, max 17.2, while CPU frames reach 113 ms.
- **Every thread inflates together** on a spike, GPU unmoved. *"The CPU as a whole
  running slow for a moment."*
- **No other process bursts** (every process sampled at 250 ms for 15 s).
- **A restart helped materially**: p95 49.6 to 34.2 ms, slow frames 33 to 13.
- **The rhythm survives on a virgin editor**, so it is not our scripts leaking.

**The power plan was switched to Ultimate Performance** (30 Sep 01:50) — processor
min and max both pinned at 100%, no frequency scaling, no core parking. Previously
Balanced, `381b4222-f694-41f0-9685-ff5bb260df2e`. The re-record was deliberately
NOT run overnight because three Blender bakes were using the machine and it would
not have been a like-for-like.

**Gary's objection stands and is the stronger argument:** a power plan does not
drift on its own, and he is certain this was not always happening. It is a
regression with a cause and a date.

**Separately: suspending Scene 3's head cloths is worth about 6 ms a frame and
three-quarters of the slow frames.** Baking them rather than simulating them is
the real win and is not yet done.

---

## 6. RUNNING OVERNIGHT

- **Cloth bakes** with a new acceptance test: stillness under 2 mm/frame, **flare
  ratio at most 1.15**, fold count and depth at 25/50/75% of the drop, and the pile
  measured against `final2` (the fall Gary approved). **Nothing gets placed that
  fails.**
- **A finding that cost two bakes and saved four hours:** a flat cloth on a pinned
  ripplefold heading **does not hold columns** — the fine pleats die within 1.5 m
  and it merges into soft swags below. So `final3`/`final4` will be still-ish but
  flared. They finish as controls; they do not get imported.
- **A hem-guide sweep** (the lead-tape stand-in) crossed with bending 5 vs 2 is
  testing whether low bending — needed for the good fall — can still hold columns.
- **Rig**: mouth lanterns, the Arrival C++ (held patch G), the backcloth, six
  parametric hangars, Scene 3.
- **Look & camera**: Scene 4's post-landing re-key once v2 settles.

---

## 7. THINGS THAT WOULD HAVE COST DAYS

Recorded because each is a class of fault, not a one-off.

- **A test can silently measure the wrong thing.** `SavedFixturePIE` depended on
  the saved level's performance mode; when that changed, four assertions kept
  passing while testing a state nobody intended. **The count hid it: 84/1 looked
  identical to 84/1 while the failing SET changed underneath.** Report assertion
  names, never tallies.
- **Procedural layout can change between BUILDS.** `FRandRange(a,b) * FRandRange(c,d)`
  — C++ leaves the operand order unspecified, the compiler picks per call site, and
  editing the function flipped it. **288 of 337 floor lanes silently re-rolled, and
  every staleness guard reported clean.** The same bug existed in light replication,
  where **126 real lights** in P02's corridor depend on it.
- **A Sequencer spawnable's identity lives in its template.** `set_actor_location`
  on one does not persist — five drapes would have spawned stacked at the Opening
  with every check reporting success. And editing a *spawned* actor writes back
  into the template.
- **"Read-only" does not mean safe.** Four of five editor crashes were inspection
  scripts. A bad argument crashes as hard as a bad write.
- **Every MCP call costs a 40–80 ms hitch.** A session polling the editor
  manufactures the stutter it is measuring.
- **Measure before judging.** Four cloth bakes were rejected on look this week
  before anyone measured anything. Every bake now carries a number.
- **THE CAPTURE CONVENTION EVERY STREAM USED WAS SEVERAL STOPS DARK.** Setting
  `auto_exposure_method` to MANUAL plus an `auto_exposure_bias` — what we all
  called "EV 1.0" — is **not** EV100. On one frame: our convention gave a curtain
  p99 of **16** and looked black; the show's real setting gave **194**; and a
  capture with **no exposure override at all** was **byte-identical to the show**,
  because a SceneCapture2D picks up the unbound global PostProcessVolume by itself.
  **RE-MEASURED AND RESOLVED (30 Sep 02:30):** every Scene 4 reading was re-taken
  with no override and **stands, to 0.05 of 255** — because the override had never
  taken effect there at all (min/max brightness only act in an AUTO exposure
  method, and the hangar has its own bound volume). Only the Opening seat moved,
  by about half a stop. **So the 30° tilt cap rests on photometry as well as
  composition: 48° is black in v2 (p99 0.0), and at 17.8 s even 30° is black
  because the upright roof is unlit BEFORE the swing — while at 21.5 s, 30° reads
  strongly (p99 213). The look-up should therefore start WITH the swing at 18.5 s,
  not before it.** Also:
  a capture's `HiddenComponents` hides **primitives only, not lights**, so a true
  "before" frame must be taken before the light exists.

---

## 8. CODEX AGENTS

Set up 30 Sep. See **`Docs/CodexAgents.md`**. `Scripts/codex.sh` runs a Codex agent
in this folder, **read-only by default**. A real bug was fixed: `.codex/config.toml`
pointed Codex's Unreal MCP at port 8000 — **MHFat's editor, not this project's.**

---

## 9. STANDING RULES (unchanged)

- **Two authorities**: the Show owns cues and attachments; the Master sequence owns
  time and the camera.
- **Never Save All.** Snapshot to `Backups/Pre<Thing>-YYYYMMDD-HHMM` before
  mutating Show data, the level, or C++.
- **Never broaden the suite filter to `PussStage`** — it matches a bootstrap test
  that rebuilds AND SAVES the Master.
- **The build gate is machine-wide**: any open UE editor blocks any build.
- **The GO1 is read-only infrastructure**: no sudo, no installs, nothing outside
  `~/go1_bridge/`, and no command that could move the robot.
- **Permission boundaries are per-session.** A relayed approval is not a stream's
  own approval, and a conductor who can route around any session's guard makes
  every guard decorative.
