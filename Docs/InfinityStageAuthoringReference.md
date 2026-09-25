# Infinity Stage authoring reference

Last updated: 14 September 2026 for Unreal Engine 5.8.2.

This is the practical reference for the finite, music-led `InfinityStage` plugin. The authoritative data is the selected `UInfinityStageShowAsset`; materialized level geometry, the Cue Desk, Sequencer and operator transport are views or evaluators of that same Show.

## Cue Desk layout

Open **Infinity Stage Cue Desk** from Unreal's Window menu. The dominant left column is the mixed Cue Score. A row is either a Wing Pair, Scene or Sequence; in nested mode, contiguous Wing Pair rows appear beneath a renameable Passage header.

- **View > Nested Passage View / Flat Cue View** changes presentation only.
- Passage headers can collapse, expand and be renamed inline.
- Drag one row or a multi-selection above/below another row, or onto a Passage header, to reorder it. Stable cue identities are preserved and the managed Master is rebuilt.
- The Cue List, Cue Details and right Passage / Music Inspector are a draggable three-column splitter.
- The Music Timeline is a horizontal workspace below them. Its divider is draggable and **View > Show Music Timeline Workspace** can collapse it completely.
- The splitter proportions, nested mode and timeline visibility persist per project.
- Multi-selection displays a UE multi-object details view. Shared values such as **Gap to Next**, **Rest Opening Width**, **Inward Travel** and mechanism settings can be committed once to every selected Wing Pair.

The bottom status rail reports Show duration, average camera speed, route length, Wing Pair count, Passage count and compile readiness. `SHOW MISMATCH` means the Cue Desk asset is not the Show used by the current level; choose **View > Use Current Level Show** before authoring or PIE testing.

## Music is the rail

Each Passage points to one Master-owned Music Rail. Its source In/Out, Passage offset and fades determine the usable music interval. Passage actors never auto-play audio from their world positions, so spatially separated bays cannot fight one another.

The Music Timeline provides waveform, playhead and ordinary transport controls. Dragging it evaluates the same absolute Master frame used by Sequencer and PIE. Optional audible scrub is a preview only; it does not become a second clock.

Music analysis remains non-destructive. Beat, onset and major-change markers are proposals until confirmed. **Curve Actions > Pin Confirmed Music Markers as Anchors** turns only confirmed markers into camera timing anchors. **View > Snap Scrub to Music Markers** snaps nearby scrub positions; hold Option while dragging to bypass snapping.

The Passage / Music Inspector keeps the four fit quantities with their authoritative Passage and Music Rail data:

- used music duration;
- preferred camera speed;
- preferred Wing spacing; and
- entry/exit clearance.

**Actions > Refit Selected Passage from Music** derives the appropriate number of Wing rows from those values. It preserves the Passage name, music, stable existing identities and the existing ordered Wing design pattern; the design repeats or trims as necessary.

## Camera route, speed and framing

The camera travels from distance zero toward increasing distance on the selected Passage Actor's `Route` spline. Its base orientation follows the spline tangent. Other systems—Wing station placement, camera distance and handoff endpoints—also depend on the spline, so edit the spline for the physical route and use camera channels for shot-specific framing.

New Passage actors normally have **Auto Fit Straight Route** enabled. It regenerates a two-point straight spline to the compiled route length whenever the Passage is materialized. To author a curve:

1. Select the relevant `Passage NN — Fixed Wings` actor.
2. Disable **Auto Fit Straight Route**.
3. Select its `Route` spline component and edit/add points in the Level viewport.
4. Keep the spline at least as long as the compiled Passage.
5. Run **Materialize Passage** so fixed Wings conform to it.
6. If its endpoint view changed, run **Actions > Scene Camera Handoff > Match All Scenes**.

Leaving Auto Fit enabled will intentionally replace a hand-edited curve on the next materialization.

The Passage Actor's Details panel has a **Route** section that runs this
sequence as **Edit Route → Extend to Compiled Length → Finish Route Edit**. It
shows the current spline length against the compiled requirement, warns while
Auto Fit is still enabled, and offers Scene handoff matching after
materializing. Auto Fit replacing an authored curve now logs
`INFINITY_STAGE_ROUTE_AUTOFIT_OVERWRITE`, so scripted materialization cannot
discard one silently.

The managed Passage section in the Master Sequence exposes native, keyable channels:

- Speed Multiplier;
- longitudinal, lateral and height offsets;
- pitch, yaw and roll;
- Route Look Ahead distance;
- focal length; and
- focus distance.

The Music Timeline's **Camera curve** selector paints one of these over the waveform. Commit a value at the playhead to add/update a native Sequencer key. Speed is integrated and normalized between pinned anchors, so a slowdown changes the rate within the span without missing its musical/spatial endpoint. A zero-rate span uses a visible linear fallback; negative values are clamped.

For a simple starting-height or viewing-angle adjustment, use **Height Offset**, **Pitch**, and optionally **Route Look Ahead**. Edit the spline when the whole path or endpoint geometry must change; use offsets/channels when only the photographed framing should change.

**Scrub View: Camera** matches the editor viewport to the evaluated Cine Camera component, including real FOV and aspect ratio, without permanently piloting it. **Scrub View: Overview** evaluates camera, Wings and lighting while leaving the viewport free for an overall view.

## Stage content attached to cues

Select one or more Wing rows and edit their lights, props, animation triggers
and mechanism sounds in the middle **Cue Details** view. The right-hand inspector
is deliberately limited to authoritative **Passage / Music** data; the old
Fit/Route/Stage tab strip was removed because it duplicated controls already
available in Cue Details, the Passage Actor and Actions.

An attachment is anchored to a **stable cue identity plus a relative offset**,
never to a world position or an absolute time. That is the whole point: re-fitting
wing count from new music, changing spacing or re-timing a Passage re-places the
attachment with its wing instead of orphaning it.

**Anchor** decides what it rides:

- **Station** — fixed at the pair's spline station; the wings move past it. Use
  for ground props and scenery the camera passes.
- **Left / Right / Top Panel** — rides that panel including its inward travel.
  Use for lights bolted to a moving wing.
- **Pair Centre** — the live midpoint between the Left and Right panels, so it
  closes in as they do. Position is derived; the pair's own rotation and scale
  are kept.

A panel anchor falls back to the station when that panel does not exist, so a
pair without a Top never loses its attachment. `GetAttachmentWorldTransform`
reads the live instance rather than the rest pose, so panel-anchored content
follows the mechanism as it moves.

**Actions > Add Missing Stage Lights to Selection** ensures every selected Wing
Pair has one Light attachment on its Left panel and one on its Right panel. It is
idempotent: re-running it fills missing sides without accumulating duplicates.
The fixtures begin as native Spot lights, but every Light attachment exposes its
type in Cue Details: **Spot**, **Rect**, or **Point**. Common controls
include intensity and units, colour/temperature, attenuation, indirect and
volumetric contribution, diffuse/specular scale, shadows, reflection/GI,
lighting channels, culling, IES and light-function settings. Spot cone, Point
falloff/source shape, and Rect size/barn-door/source-texture controls appear for
the relevant type. A custom Actor Class remains optional; when supplied, the
same settings are applied to its first Light Component.

Tune one Wing Pair, then multi-select an ordered range and choose **Actions >
Replicate First Pair's Lighting Across Selection**. The earliest selected pair
is the template. Its complete Light attachments replace only the Light
attachments on the other selected pairs; props, sounds and animation triggers
are preserved, and every destination keeps independent stable attachment
identities. This makes broad lighting runs repeatable while leaving individual
pairs editable afterwards.

The generated relative transforms are starting points, not prescriptions: move
any materialized light in the viewport and its **relative** offset persists, so
later re-spacing carries it along. After creating, changing type/parameters, or
replicating lights, run **Materialize Selected Passage** to update the level.

**Move an attachment in the viewport and its offset is written back to the cue
automatically** — no edit mode to enter. Grab the spawned light or prop, move it,
and the new transform is stored *relative to its anchor*, which is what makes it
survive a later re-space or re-fit. The Show is left dirty for an intentional
save; the log records `INFINITY_STAGE_ATTACHMENT_MOVED`.

Attachment actors are spawned and owned by the Passage Actor and listed in
`ManagedAttachmentActors`. Whatever materialization creates, materialization
destroys — re-materializing never accumulates duplicates, disabling an
attachment removes its actor, and clearing the Passage removes them all. A
broken reference warns with `INFINITY_STAGE_ATTACHMENT_SKIPPED` and is skipped
rather than failing the whole materialize.

Re-place attachments with **Actions > Materialize Selected Passage** (or
**Materialize All Passages**) after changing wing count, spacing, meshes or
attachments. This is the same operation as the Passage Actor's **Materialize
Passage** button, now available where the structure is actually edited. The
level is left dirty for an intentional save.

**Camera Owner** on a Scene is effectively binary: either the Scene is a series
of cuts with no authored rotation and the dog looks around, or it is moving shots
whose rotation is authored and the dog is locked out. **Dog Free Look** maps to
the receiver's Velocity mode, where stick deflection is a turn rate and the view
can circle without returning to centre. **Dog Gaze Only** maps to Absolute mode,
where deflection is an angle within the authored range and centring returns to
centre — correct when the view maps to a physical screen.

**Actions > Scene Camera Handoff > Check All Scenes** reports when a Scene has
dog look enabled *and* its cut camera also carries keyed rotation, since those
two write the same orientation. It is advisory, not enforced: authored rotation
may be intended as a base the dog looks around from.

**Animation triggers** fire on camera *distance* rather than time, so retiming
cannot desynchronise them, and scrub and reverse re-evaluate deterministically.

### Follow light behind the camera

The Camera Rig carries an optional **Follow Light**: a spot attached to the rig
root, so it travels the route with no evaluation of its own. Placed behind the
shadow figure and pointing forward, it throws the cat's shadow into the stage
ahead of the camera. Off by default, with editable offset and rotation that
apply live on construction.

### Wing mechanism sound

Each Passage carries a **Mechanism Sound** set: a bucket of Sound assets, a
selection policy, gain, an audible radius and a movement threshold. A single pair
can be silenced with **Mute Mechanism Sound** without disabling the Passage.

Selection is deterministic by design — the same wing makes the same sound on
every replay:

- **Round Robin** cycles the set by Passage order.
- **Stable Random** seeds from the cue identity, never from a call counter or
  world time, so the choice survives scrub, reverse, reload and re-materialize.
- **By Cycle Rate** reaches further into the set as the mechanism runs faster, so
  the set can be ordered by effort.

Timing is never authored here. The mechanism data already says when a pair moves
and how fast, so sound placement is derived from `CycleRateHz`, `InwardTravelCm`,
phase and the Wing channels — re-timing the music re-times the squeaks with it.
Authoring times separately would recreate exactly the stale-snapshot problem the
attachment system exists to avoid.

## Wing placement and motion

All fixed Wings are materialized editor-visible ISM instances. They are not spawned during PIE and there is no Actor Tick or timer per Wing. Ordinary lights, grounds and unique scenic objects can therefore be installed around them as on a physical stage.

For a Wing Pair:

- **Gap to Next** is longitudinal distance to the next pair.
- **Rest Opening Width (Pivot-to-Pivot)** symmetrically sets how far apart Left and Right rest positions are.
- **Opening Centre Offset** moves that opening laterally without changing its width.
- **Inward Travel Cm** is how far each panel travels toward the centre from its authored rest position.
- Left and Right use opposite pair-local inward axes regardless of asset facing.
- **Occurrence Offset** moves/rotates/scales the complete pair at its spline station.

Use **Actions > Wing Movement** for presets. Whole-Passage undulations now store a live phase step on the Passage. The phase derives from each Wing Pair's current cue ordinal, so drag/drop reordering immediately changes the travelling wave; there is no need to regenerate the preset. A row can opt out using its **Mechanism Phase** local-override flag.

Wing movement can also be keyed against Master time. Three native channels on the
same managed Passage section — **Wing Travel Scale**, **Wing Cycle Rate Scale**
and **Wing Phase Bias** — multiply or offset each cue's authored mechanism
values, so a musical section can open the wings wider or breathe faster without
editing rows one by one. They appear in the Music Timeline's channel selector
under Wing Movement and in Sequencer's curve editor under the Wing Movement
group. A Passage whose channels are neutral (1.0 / 1.0 / 0.0) evaluates exactly
as before. Note that the per-cue Left/Right/Top curves are a different thing:
their axis is phase within one cycle, so they shape a single breath and repeat
for the whole Passage.

**Camera Gust / Fan Reveal** is normally camera-led: the music rail moves the camera, and a configurable number of pairs immediately ahead remain revealed. The opening ramp is measured in pair spacing, so slowing or accelerating the camera automatically slows or accelerates the reveal. Open Wings remain open behind the camera; rewinding deterministically reconstructs the earlier closed frontier. The advanced timed-cascade fields are only for an explicitly selected advanced mode.

Use **Edit Selected Wing in Level Viewport** for a discrete manual correction. The temporary gizmo is an editing transport: finishing writes the result back to the Show cue and rematerializes the affected Passage. Do not edit raw ISM transforms as a separate source of truth.

When an imported mesh is consistently the wrong size or offset, correct one occurrence and use **Actions > Relative Transform** to copy that selected Left, Right or Top panel's complete saved location, rotation and scale to every use of the same mesh. The source mesh is not modified; the Show's per-occurrence `LocalTransform` values remain authoritative, and affected Passages are rematerialized for immediate review.

## Selection and playhead

With **Actions > Follow Cue Playhead in Level Viewport** enabled:

- selecting a Passage header moves to its first Master frame;
- selecting a Wing Pair moves to that occurrence's compiled pass frame; and
- PIE uses the same root Sequence Player rather than an editor-only clock.

Programmatic refreshes do not trigger surprise jumps. **Frame Selected Wing Pair(s)** is an explicit geometry-framing command and is separate from exact camera view.

## Scenes and camera handoff

A Scene cue references an artist-authored Level Sequence. The managed Master contains one purple subsequence block for it, never one block per Wing. The Scene's own Camera Cut Track owns the viewport while that Scene plays.

Run **Actions > Scene Camera Handoff > Match Selected Scene** or **Match All Scenes** after route/camera endpoint changes. The tool:

- matches/creates a Scene entry camera from the incoming Passage endpoint;
- matches/creates a Scene exit camera from the next Passage start;
- copies transform, lens and focus; and
- preserves internal artist-authored Scene cuts.

Double-click a purple Scene block to focus its sequence inside the current Sequencer. Ctrl-double-click opens it separately. The block context menu and Cue Desk both also provide **Open Scene Sequence**. Use the Sequencer breadcrumb/back control to return to the Master.

## Sequence-owned curtain interstitials

The production 19-segment Show uses SEQ rows for the opening, five interactions
and closing. These are distinct from ordinary Scene rows: their Level Sequences
own the curtain spawnable and Next Segment starts them automatically rather than
holding at frame zero.

The reusable rig is
`/Game/InfinityStage/Interactions/BP_InfinityStageSequenceCurtain`. The current
interaction template and all five production interactions contain:

- `01_Curtain_Foreground` for the curtain rig and its activation/progress tracks;
- `02_BoyCat_Behind_Curtain` for the later performance content; and
- `03_Light_Shadow_Audio_VFX` for supporting production tracks.

At 25 fps the interaction sequences run 500 frames. The curtain falls over
frames 0–75, the BoyCat window is 75–375, the hidden Passage changeover marker
is at 375, the curtain remains fully covered until 400, and rises over 400–500.
The labelled Sequencer markers are the authoring controls for those events:
`InfinityStage.CurtainFullyDown`, `InfinityStage.BoyCatStart`,
`InfinityStage.HiddenChangeover`, `InfinityStage.CurtainRiseStart` and
`InfinityStage.CurtainFullyOpen`.

Do not place a second runtime curtain in the level. Adjust the sequence
spawnable/template and its camera-relative placement tracks, then preview through
the production Show in PIE. Enable **Rehearsal**, select the SEQ row and use
**Play Selected**. The state verifier proves saved keys, markers, topology and
clean packages; it does not prove that the curtain fills the rendered viewport,
so sign off framing and depth order visually.

## PIE and operator transport

One `AInfinityStageShowRoot` owns one Master `ULevelSequencePlayer`. On Begin Play it prepares the player and claims the camera belonging to the current segment, including a held or auto-playing frame zero.

The opening uses Passage 1's starting camera unless its sequence supplies an
explicit Camera Cut. Production Auto Play now uses bounded transport, so the
opening plays and holds at Passage 1 rather than running through the full Show.
With the PIE viewport focused, **Space** plays/holds and **Left/Right Arrow**
select the previous/next segment. Right Arrow keeps the Cue Desk's existing
behavior: a new Passage holds; a Scene or SEQ starts. Use Space to GO from a
held Passage. [Opening repair evidence](OpeningPlaybackRepair-20260914.md).

The Music Timeline transport has:

- previous Master segment;
- current Passage start;
- reverse to boundary;
- stop/hold;
- forward to boundary;
- current Passage end; and
- next Master segment.

**Camera Owner** is authored per Passage and per Scene: *Timeline*, *Dog* or
*Dog (Gaze Only)*. It lives in the Show so the score records who drives the
camera at each moment, rather than depending on which actor happens to carry a
telemetry component. Timeline is the default and the fallback — the dog is not
always connected and the show must run without him.

**View → Live Camera Owner** overrides that during a running PIE session —
Follow Show, Force Timeline, Force Dog, Force Dog (Gaze Only). The override is
transient: taking the camera back mid-performance never rewrites the Show.

Camera ownership is the **only** switch between gaze and free look. Mirroring the
dog's own reported mode was tried and removed: measured on hardware, standing and
move mode both report `mode = 0`, so that field cannot distinguish them. Authored
ownership is deterministic, visible in the Cue Desk, and behaves identically when
the dog is not connected.

External input plugins should read `AInfinityStageShowRoot::GetCameraOwnerAtFrame`
rather than carrying a per-actor enable flag. Telemetry receivers that bind a
single socket cannot be duplicated onto every camera, so one receiver on a
persistent actor serves them all and the Show decides who is listening.

**View → PIE Starts At Playhead** begins Play In Editor at the Cue Desk playhead
instead of the start of the Show, so a Passage or Scene can be rehearsed without
scrubbing back each time. It applies only when the Cue Desk Show matches the one
running in PIE. It respects the Show's Auto Play preference after seeking;
with Auto Play off it holds. Turn it off for a run from the top.

**View → Sync Sequencer Playhead** moves any open Sequencer showing this Show's
managed Master to the Cue Desk playhead. PIE already follows the same absolute
Master frame, so this brings the third view into line without adding a second
clock. Sequencers with a different sequence open are left alone. Off by default.

**View → Play Through Boundaries** makes forward play run continuously to the end
of the Show, bypassing operator holds. With it off, the production Show Root's
Transport enables **Auto Play Scene After Passage**: normal forward play continues
through the following Scene, then holds at the Scene end. Opening/interstitial
playback still holds on arrival at the next Passage. Other Shows retain their
previous behavior unless this setting is enabled. All thirteen production
non-wing cues now use their containing sequence lengths; use **Actions → Rebuild
Managed Master Sequence** after changing those ranges. Nested shots must still
fit inside their containing Scene. [Verified transition record](SceneTransitionRepair-20260914.md).

**Actions → Scene Camera Handoff → Check All Scenes (read-only)** compares every
Scene's handoff cameras against the current evaluated Passage endpoints and
reports any that no longer match. Handoff cameras are a **snapshot** taken when
matching last ran, so changing a Passage route or camera curve afterwards — a
focal length key is the easy one to forget — leaves them stale and produces a
visible jump at the boundary. The check writes nothing, and it deliberately
ignores boundaries whose camera is artist-authored rather than a generated
handoff camera, because a lens change there may be a deliberate cut.

**View → Rehearsal Transport** ignores declared external sound locks so seek,
reverse and hold work while the playhead sits inside a Scene. Performance mode
remains the runtime default and refuses those moves, so a live show cannot
desynchronize from an external clock. The preference persists per project and is
pushed onto every running PIE Show Root for the current Show.

The visible **Rehearsal** checkbox is paired with **Play Selected**. In PIE,
select one Scene or SEQ row and use Play Selected to cue its exact first frame,
apply the rehearsal bypass and play only that segment to its boundary. Next
Segment also auto-plays SEQ/interstitial cues; Passage and Scene entries hold at
their exact start.

To stop the engine's default pawn appearing in shot, set the level's **World
Settings → GameMode Override** to `InfinityStageShowGameMode`. It spawns no pawn
and no HUD and starts players as spectators, leaving the Passage Camera Rigs to
own the view.

With the Cue Desk focused, **Left** and **Right** step whole segments — Passage
to Scene to Passage — rather than individual wings, which is the granularity an
operator rehearses at. They route through the same transport as the previous/next
segment buttons, so performance constraints still apply.

With the Cue Desk focused, **Space** toggles the playhead: it stops playback when
running and plays forward when stopped. It works for both editor preview and PIE,
and routes through the same transport command as the buttons, so performance-mode
constraints still apply — an externally unpausable Scene rejects the pause exactly
as it rejects the stop button. Space is ignored while typing in a text field.

Use previous/next segment in PIE to rehearse later Passages without replaying from Passage 1. Every jump checks readiness before moving. In performance mode, an externally unpausable Scene rejects seek, reverse, hold and non-1× shuttling; ordinary forward 1× playback remains allowed. Rehearsal mode may seek when external synchronization is deliberately ignored.

## Materialization, files and rendering

The Passage Actor Details panel exposes both **Materialize Passage** and **Clear Materialized Passage**. The first is a parameterless Call in Editor wrapper around the validated materializer. A failed rebuild retains the previous valid materialization where possible.

**Actions > Wing Sequence Files** exports lossless `.infinitywings.json` files. The usual import mode, **Apply Saved Arrangement to Current Passage**, repeats or trims only the ordered Wing designs to the current row count. It does not rename the Passage or rows and does not overwrite music, timing, spacing or stable identity. Advanced replace/insert modes are explicitly separate.

**Actions > Render Selected Range** creates a managed render wrapper, nests the authoritative Master, exposes Passage cameras through a standard Camera Cut Track and opens Movie Render Queue (Unreal's offline high-quality video renderer). Scene intervals retain their nested Camera Cut authority. This is separate from live PIE performance output.

## Lighting, sky and ground

The celestial rig can follow Master time or use manual editor lighting. Use the Cue Desk lighting menu to choose a manual editor hour or select the rig for direct artistic adjustment. PIE remains deterministic from the Show. The default development setup is dusky, but it is not meant to replace artist lighting.

Ground is ordinary authored level content. Separate Passage bays can use independent forest, concrete, wood, water or Landscape/mesh ground without becoming plugin-generated data. This is intentional: the plugin owns timing, route, fixed Wing placement and camera/Scene handoff, not the scenic floor design.

## Safe authoring rule

For automated or scripted changes, follow `Docs/CodexUnrealMCPRunbook.md`: inspect the Show first, make a narrowly targeted deterministic edit, materialize only affected Passage actors, save only the Show and affected level/sequence assets, then read back and verify an explicit log marker. Never use Save All merely to make an Infinity Stage edit.
