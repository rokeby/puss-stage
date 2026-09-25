# Container world — conductor plan

Written by the conductor session, 2026-09-25. Companion to the three working
lists; this plan is what the parallel streams work from until the container
exists.

## The goal, in one paragraph

We are not travelling past stage wings on a travellator. We are moving **inside
a Baroque stage machine** — timber gridiron overhead, chariot grooves in the
floor, hemp lines, sandbags, walls beyond the wings, par cans hazing in the
distance, cloth hanging and peeling. The wings are the machine's painted
surfaces; Puss is the one thing in it that is not on rails. Scenes are not
elsewhere: they are the same stage suddenly opening into a large volume, still
containing wings, placed irregularly.

**Register: Baroque stagecraft, not industrial perfection.** Wood, rope, canvas,
paint, wear. Industrial precision is a deliberate wrongness to introduce later,
not the default.

## The structural idea: the bay is the unit

The Show already compiles every wing pair to a station distance along its route.
Only the wings and their lights use that today. Everything else in the world —
ground slots, gridiron bays, wall panels, practicals, haze and fire emitters —
must derive from **the same compiled stations**, so the container shares the
wings' rhythm and reads as one machine. Change the wing spacing and the building
re-fits itself.

**Generate the spine, hand-place the accidents.** Any generator owns only what it
created and never touches anything else, so hand-dropped rope, ladders, sandbags
and debris survive every regeneration. The generator gives rhythm; the hand gives
evidence of use. That division is also what stops it looking generated.

## Streams and ownership

Each stream is a separate session. **Own your files; never edit another stream's.
Message the conductor at milestones with one line: DONE / NEXT / NEEDS-YOU.**

| Stream | Owns | First job |
| --- | --- | --- |
| **Rig & atmosphere** | New plugin files for a `MaterializeStructure` pass beside `MaterializePassage`; fog/volumetrics; light fixture bodies | Volumetric fog pass, then ground slots + timber gridiron derived from compiled stations, with the fixtures hung on them |
| **Wing materiality** | `/Game/Scenes/Wings` materials only | Parallax depth, oily paint and billboard finishes, per-instance variation |
| **Soft goods** | `Scripts/build_curtain_cloth_bake.py`, `DerivedAssets/CurtainCloth` | Velvet / sack / hanging cloth / peeling variants off the existing pipeline |
| **Effects sources** *(lower priority)* | New Haze/Fire/Smoke attachment kinds and their Niagara systems | Practical haze and fire emitters placed on bays, feeding the volumetrics |
| **Look & camera** | `Go1Input`, camera rig | Mouse stand-in (**done, built**); framing passes once there is a container |
| **Conductor** | This plan, briefs, the build gate, `README.md` and the handover | Sequencing, merges, keeping the docs true |

**Rig and atmosphere are one stream** because they are one problem: the gridiron
holds the fixtures, the fixtures make the beams, the beams only read against haze,
and the haze is shaped by the structure it hangs in. Splitting them would mean two
sessions contending for the same bays and each tuning half a look.

**Effects sources is deliberately separate and second.** Smoke machines, fire and
their Niagara systems are self-contained emitters that plug into bays once the
bays and the volumetrics exist. It is the one stream that can start late without
blocking anything.

## Briefs

One per stream, written the way the MHFat conductor writes them. Read the plan,
then your brief.

- `BRIEF_RIG_AND_ATMOSPHERE_2026-09-25.md`
- `BRIEF_WING_MATERIALITY_2026-09-25.md`
- `BRIEF_SOFT_GOODS_2026-09-25.md`
- `BRIEF_EFFECTS_SOURCES_2026-09-25.md` — starts late, by design

**Look & camera** has no brief yet: its immediate job (the mouse stand-in for the
dog) is built and verified, and its next job — framing passes — is not worth
starting until there is a container to frame.

**One shared file, one owner.** `EInfinityAttachmentKind` in
`InfinityStageTypes.h` is wanted by both Rig & atmosphere and Effects sources.
That change is made **once, through the conductor**, never twice.

## Exclusive resources — these do not parallelise

1. **The build.** One at a time, and the Unreal editor must be **closed**. Any
   open UE editor blocks it via Live Coding — including the MHFat editor, which
   blocked a Puss build today. All builds go through the conductor and the user.
2. **The Puss editor / MCP on port 8010.** One script at a time. Both projects
   were configured for 8000 and MHFat won the race, so a Puss script was being
   addressed to the MHFat editor. PussStage now owns **8010** (set in
   `Config/DefaultEditorPerProjectUserSettings.ini`); MHFat keeps 8000, and its
   config was not touched. `Saved/CodexMocap/mcp_request.py` defaults to 8010 and
   takes `--url` / `PUSS_MCP_URL`.
   **Every Puss script must assert the expected world before mutating anything** —
   a port mix-up otherwise edits the wrong project in silence.
3. **The Show asset and the level.** One writer at a time. Materialize is global
   and a targeted save persists whatever else is dirty.
4. **Blender GUI.** Held by Soft goods.

Everything else — writing C++, generating in Blender, authoring materials,
read-only audits — runs in parallel.

## The build gate and the editor

The conductor can open and close the Puss editor itself, so a stream never has to
wait on a person to run a build. The discipline around it:

1. Before closing, read back through MCP and require **zero dirty packages**. The
   editor is only ever closed from a clean state, never with unsaved work.
2. Close, build, prove the new code is in the DLL by its UTF-16 string, check for
   hot-reload leftovers, run the suite, reopen.
3. Builds are blocked by **any** open UE editor, MHFat's included. If a build
   refuses with a Live Coding message, that is the gate working — nothing was
   compiled and there are no stale binaries.
4. The user still owns rendered acceptance. Automation getting to green is not the
   same as the look being right.

## Keeping the docs true — a conductor duty, not an afterthought

The working lists fell a week behind the code twice now, and both times the next
session started from a false map. So, at every milestone and at the end of every
run:

- `README.md` — what this project is, where the authority lives, how to run it,
  what state it is in. Written for a person with no AI session open.
- `Docs/InfinityStageSessionHandover.md` — current checkpoint, what is verified
  and at which tier, what is unproven.
- The three working lists — tick what is actually done, against the code.

If a stream finishes work that changes any of these, it reports it and the
conductor writes it down. Undocumented work is treated as unfinished.

## Rules every stream inherits

- **The Show Asset is the authority.** Moving a placed light or attachment in the
  level writes its offset and settings back to the Show; replicate from the Show,
  never from actor world transforms.
- **No git.** `Backups/Pre<Thing>-YYYYMMDD-HHMM` before touching C++, the Show or
  the level. Say which backup covers your change.
- **Three tiers of proof, none substituting for another**: a clean build with the
  new code proven in the DLL; a saved Unreal read-back with zero dirty packages;
  rendered visual acceptance by the user. Report which tier you reached.
- **Never Save All.** Save only the asset and level you touched.
- Verify against the code before trusting any task list. Both the handover and
  `ShowBuildTodo.md` are currently behind the work (see below).

## Status at the time of writing

- Built and verified today (plugin **0.15.0-container-look**): mouse stand-in for
  the dog on the same path the robot drives; Passage details panel no longer
  builds thousands of rows (the cause of the 10–20 s selection stall).
- Suite **45/46** — the lone `SavedFixturePIE` curtain-marker failure, unchanged.
- **Volumetric fog is still off**, and every one of the 2,340 fixtures has
  `cast_volumetric_shadow` disabled. Nothing hazes yet. This is the cheapest
  large visual gain available and it is Atmospherics' first job.
- The docs are stale: the handover and `ShowBuildTodo.md` still read "43/44" and
  an 18 September checkpoint, and describe none of the lighting rig, spot-spawn
  fix, cat work, cloth pipeline or the 21 September sessions. Tier 0 of any
  overnight run is reconciling them.
- `Docs/GroundPlaneDesign.md` specifies a naturalistic forest floor. The new
  direction supersedes its *implementation*, not its three-layer logic: cloth is
  **laid over** the machine and worn through at frays and holes to show boards
  and grooves beneath. That doc needs rewriting, not ignoring.
- The cat's centre line stays clear of grooves and slots. Puss is not on rails.

## Open questions for the user

- Scene volumes: how far does the container carry into them before it lifts away?
- How much industrial precision, and where, once the Baroque register is established?
