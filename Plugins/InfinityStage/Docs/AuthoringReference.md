# Infinity Stage Authoring Reference

This is the production-facing reference for controls that an artist is expected to adjust. The Cue Score and its managed Master Sequence are the time authority; Passage Actors, camera rigs and Scene sequences are spatial/playback adapters.

## Safe update order

1. Edit Cue order, music, timing, spacing or Passage settings in the Cue Desk.
2. Select each affected `InfinityStagePassageActor` and run **Materialize Passage**.
3. Choose **Actions > Rebuild Managed Master Sequence** after timing, order or duration changes.
4. Choose **Actions > Scene Camera Handoff > Match Selected Scene** (or **Match All Scenes**) after changing a route endpoint, camera framing or Scene entry/exit view.
5. Scrub the Music Timeline in **Camera View** for framing or **Overview** for the complete moving stage.

## Reusable Wing Sequence files

The Cue Desk can save an ordered block of Wing Pair occurrences as a human-readable, versioned `.infinitywings.json` file outside Unreal Content. This is the preferred way to archive a good sequence, move it between Show Assets, or switch a Passage to a different authored arrangement without creating a second source of truth.

Open **Actions > Wing Sequence Files**:

- **Export Selected Wing Pair(s)…** writes the selected rows in chronological Show order.
- **Export Whole Current Passage…** writes every row plus that Passage's lead/tail frames and distances, fit mode, preferred spacing and preferred camera speed.
- **Apply Saved Arrangement to Current Passage…** is the normal restore/switch operation. It applies the saved ordered panel, transform and movement designs across the Passage's existing rows, repeating or trimming the pattern to fit. It preserves the target Passage name, row names, row count, music-derived timing, spacing, stable IDs and all Passage-wide settings.
- **Import and Insert After Selection…** inserts fresh copies after the latest selected Cue (or after the selected Passage heading). If nothing is selected, it appends them to the Show.
- **Advanced: Replace Complete Passage Rows…** replaces every Wing row in the explicitly selected Passage after confirmation. This intentionally adopts the file's row count, row labels, timing, spacing and saved layout/camera envelope.

The default library folder is `Saved/InfinityStage/WingSequences`, but the native file dialog may save or open the JSON anywhere.

### What a file preserves

Each occurrence keeps its label/tags and complete Left, Right and optional Top definitions: soft mesh and material references, local transforms, facing policy, explicit legacy image-flip state, shadow/visibility/collision settings, row interval, gap, occurrence offset, local override mask, movement mode/rate/phase/travel, normalized curves and Camera Gust settings. Source asset packages themselves are not copied or modified.

The document records its source display/tick frame rates. Import uses exact Unreal frame-rate transformation with nearest-frame rounding for `Interval To Next`, explicit mechanism-origin frames and a complete Passage's lead/tail frames. Distance, transforms and curves are not resampled.

Imported cues always receive new Cue and Occurrence GUIDs. Camera Gust group anchors are remapped to the new GUIDs when the saved anchor is inside the file; an orphaned anchor from a partial selection safely becomes a one-pair group. This prevents duplicate stable identities or references back into the source Show.

### Arrangement, insert and complete-row replacement

Use **Apply Saved Arrangement** for the usual artistic task: bring a tuned Wing order into a Passage whose duration and row count are already governed by its music. If the file contains fewer rows than the target, its complete order repeats; if it contains more, the tail is trimmed. This does not rename either the Passage or its existing Wing rows.

To establish or re-establish the music-derived row count, select the Passage heading, open the **Fit** tab, confirm **Music / Passage**, **Camera speed**, **Wing spacing** and clearances, then press **Reset wing count from music**. The resize uses the complete current Wing order as its repeat pattern rather than cloning only the last row. Existing row names and identities survive; added rows receive new identities. The clearest restore workflow is therefore: fit the count first, then apply the saved arrangement.

Insert imports rows only. A complete-Passage envelope in the file does not unexpectedly overwrite the surrounding Passage's settings.

Complete-row Replace applies the saved layout/camera envelope, but deliberately preserves the target Passage's stable Passage GUID, label, Music Rail binding, celestial temporality, and adjacent Scene/camera-handoff ownership. Every operation is one Unreal transaction and supports Undo/Redo. After an import, the plugin reconciles the authoritative Show Asset, rematerializes only affected Passage Actors, rebuilds plugin-owned Master tracks, selects the affected rows, and leaves the changed packages dirty for an intentional Save.

### Renaming a Passage

In nested Cue mode, double-click the bold **PASS** heading name and type the new name. The same `Passage > Label` field remains available in the selection Details panel. Renaming the Passage does not rename its Wing rows or alter its external Wing Sequence files; it only updates the Passage label and managed sequence presentation.

The interchange schema is currently `InfinityStageWingSequence` version 1. A newer unsupported schema is rejected rather than partially imported. Missing referenced assets retain their soft paths so the source content can be migrated or restored; the JSON is metadata, not an asset bundle.

## Route spline versus camera offset

Use the **Route spline** when the physical path changes. Wing stations, passage-camera direction, shadow figures and entry/exit handoffs all derive from it.

Use **Camera Offset** when only the camera composition changes. Height, lateral position or a small fore/aft adjustment should not move the wings or redefine the stage route.

| Desired change | Correct control |
|---|---|
| Raise the camera for the complete Passage | Camera Rig > Camera Offset Z |
| Move only the camera left/right | Camera Rig > Camera Offset Y |
| Change the path followed by camera and wings | Passage Actor > Route spline |
| Curve, snake or raise the complete stage path | Passage Actor > Route spline |
| Change wide/telephoto framing | Music Timeline > Camera Curve > Focal Length, or the Passage section's native Focal Length channel in Sequencer |
| Change camera pitch without changing the stage | Music Timeline > Camera Curve > Camera Pitch, or the Passage section's native Pitch channel in Sequencer |

### Editing a route

Passage Actors initially use `bAutoFitStraightRoute = true`. Materialization then regenerates a two-point straight spline exactly long enough for the compiled Passage.

The Passage Actor's Details panel has a **Route** section that runs this
workflow and reports the two conditions that otherwise fail silently:

1. Select `Passage NN — Fixed Wings` in the World Outliner.
2. Read the Route status line. It shows the current spline length against the
   compiled requirement, and warns while Auto Fit is still enabled.
3. Press **Edit Route**. This disables Auto Fit and selects the `Route` spline.
4. Add, move and rotate spline points in the Level viewport.
5. Press **Extend to Compiled Length** if the status line reports a shortfall.
   The tail is extended along its final tangent; wings occupy the route from
   distance zero forward, so only the unused tail changes.
6. Press **Finish Route Edit**. It validates the length, extends the tail if
   still short, materializes this Passage onto the new curve, then offers
   **Match All Scenes** as an explicit action.
7. Save the level, and the Scene sequences if handoffs were re-matched.

The same steps remain available manually: disable **Auto Fit Straight Route**,
edit the spline, then use **Materialize Passage** and
**Match Scene Camera Handoffs**.

Re-enabling Auto Fit and materializing will replace the custom spline with a
straight one. When it detects a route that leaves the local +X axis, the
materializer logs `INFINITY_STAGE_ROUTE_AUTOFIT_OVERWRITE` first, so a scripted
or MCP-driven materialization cannot discard an authored curve unnoticed.

`GetRouteLengthStatus` and `ExtendRouteToCompiledLength` are Blueprint- and
Python-callable on the Passage Actor for the same checks in automation.

## Camera movement and Passage Camera channels

Each Wing Pair row supplies a `(pass frame, route distance)` anchor:

- `Interval To Next` advances the pass frame.
- `Gap To Next Cm` advances route distance.
- Passage `Lead In/Out Frames` and `Lead In/Out Distance` close the start and end of the curve.

Without speed keys, the camera moves monotonically from spline distance zero to the Passage end and linearly interpolates between adjacent anchors. Local baseline speed is therefore `Gap To Next / Interval To Next`. `Preferred Camera Speed` is a music-fit/setup input that writes row timing and spacing; it is not a runtime speed override after those rows exist.

Each managed Passage section now exposes native Sequencer double channels while retaining its stable managed `BlockGuid`. Rebuilding the managed Master updates its section range and ownership but preserves artist channel keys and valid pinned anchors.

Available channels:

- **Speed / Time Warp**: non-negative integrated speed shape
- **Camera Longitudinal, Lateral and Height**: centimetres added to the Camera Rig's base `Camera Offset`
- **Camera Pitch, Yaw and Roll**: local route-relative degrees
- **Focal Length**: absolute millimetres
- **Focus Distance**: absolute centimetres, evaluated in manual-focus mode

There is one copy of these values: the channels on the managed Master Passage section. The Cue Desk Music Timeline paints and edits those same channels. It does not maintain proxy camera data.

### Editing camera curves against music

1. Select any Wing or the Passage header in the Cue Desk.
2. Scrub or play the Music Timeline to the desired Master frame.
3. Choose a channel from **Camera curve**.
4. Enter a value and press Return. This adds or updates a native Sequencer key at the playhead.
5. Use **Curve Actions** to remove the playhead key, reset the active curve, pin a selected Wing, or open the Master in Sequencer for tangent and multi-key editing.

**Curve Actions > Add Speed Envelope** supplies three constraint-safe starting gestures: accelerate over the first 30 seconds, slow over the last 30 seconds, or make a 30-second slowdown centred on the playhead. They add/update native Speed keys and may be refined in Sequencer.

In Sequencer, expand **Infinity Stage Passages**, then expand the relevant Passage block to see the Timing, Position, Rotation and Lens channel groups. These are the same keys shown by the Cue Desk.

With the Cue Desk focused, **Space** toggles the playhead — stop when running, play forward when stopped — for both editor preview and PIE. It calls the same transport command as the stop/play buttons, so an externally unpausable Scene rejects it exactly as it rejects the button. Text fields consume Space normally while typing.

The amber line is the selected camera curve; amber squares are its keys. Green vertical lines are pinned Wing anchors and cyan lines are playhead/music anchors. The readout shows current actual camera speed, Passage average, sampled peak, anchor count and constraint errors. Scrubbing, Sequencer playback, reverse, direct seek and live operator transport evaluate the same Master-frame channels.

### Coherent speed-curve behavior

The baseline distance curve remains defined by wing pass anchors. A non-negative **Speed Multiplier** curve is integrated over time rather than sampled as a position, preventing reversals and discontinuities. Within each unlocked span the integral is normalized so the required span distance and endpoint time remain exact.

Wing anchors may be marked through **Pin Selected Wing as Timing Anchor** and arbitrary musical moments through **Pin Playhead as Music Anchor**. Music anchors are stored relative to Passage start, so changing an earlier Scene does not detach them from their music rail. Passage start and end are always pinned. Pinned anchors divide the Passage into constraint spans. A 30-second slowdown is therefore compensated elsewhere inside its unlocked span. An all-zero rate span is invalid; preview uses a linear safety fallback and the Music Timeline reports the conflict instead of producing a discontinuity or silently moving a musical anchor.

To deliberately change Passage duration, edit music/cue timing or use the Fit controls and rebuild the managed Master. Speed curves never silently move the music rail, Passage end or Scene camera handoff.

## Wing placement controls

| Control | Effect |
|---|---|
| `Gap To Next Cm` | Longitudinal station distance to the next pair |
| `Occurrence Offset` | Whole-pair transform relative to its spline station |
| `Rest Opening Width` | Left/right pivot separation at rest |
| `Opening Centre Offset` | Lateral centre of the pair opening |
| Panel `Local Transform` | Mesh-specific placement, scale and orientation |
| `Inward Travel Cm` | Maximum inward translation of each individual panel |

If both sides travel 75 cm, the opening narrows by up to 150 cm. Movement uses stored opposite inward vectors for Left and Right, so identical normalized curves close the pair symmetrically.

## Wing movement and phase

Every Wing Pair stores a playback mode, cycle rate, phase origin, phase offset, inward travel and separate Left/Right/Top normalized curves.

Current **Actions > Wing Movement** presets:

- **Gentle Wave Along Passage**: continuous 0.18 Hz loop; `-0.10` cycle phase step per ordinal pair.
- **Gentle Wave Toward Camera**: continuous 0.18 Hz loop; `+0.10` cycle phase step.
- **Breathe Together**: continuous 0.18 Hz loop; no pair-to-pair phase step.
- **Phased Breathe > 2 Phases — Alternate**: continuous 0.18 Hz loop with a `0.5`-cycle step, repeating out/in across consecutive pairs.
- **Phased Breathe > 3 Phases — 1–2–3**: the same loop distributed at one-third-cycle intervals and repeated every three pairs.
- **Phased Breathe > 4 Phases — 1–2–3–4**: the same loop distributed at quarter-cycle intervals and repeated every four pairs.
- **Camera Gust / Fan Reveal**: a camera-led reveal frontier in which a fixed number of pairs immediately ahead are open and the road beyond remains closed. The submenu provides Tight Snap, Camera-led Reveal, Broad Gust and Custom variants.
- **Hold Static**: retains the authored curve/rate but stops phase advancement.

### Top panel participation

Presets differ in whether they author a Top curve, so ceiling involvement used to be invisible. Each Wing Pair now has **Top Follows Wing Movement** in its Mechanism section:

- **On** (default) — the Top uses its own curve, falling back to the Left curve when the preset did not author one. Ticking it therefore makes a side-only preset drive the ceiling too.
- **Off** — the Top holds at rest whatever is authored, without disturbing the sides.

The default preserves existing content exactly: a preset that left the Top curve flat still produces no ceiling movement. It is an ordinary Wing Pair property, so a multi-row selection can commit it to a whole Passage at once, and `TopNormalizedCurve` remains editable for shaping afterwards.

Travelling-wave and phased-breath offsets are baked when the preset is applied. Reordering those rows does not reinterpret the baked ordinal; rerun the movement preset after scrambling their order. Phase patterns restart at each Passage boundary.

### Binding a music rail

Music Rails live on the Show Asset and are referenced by GUID. Passage and Scene
music bindings show a **rail picker** rather than that raw GUID: choose a rail by
label, clear it with **None**, or use **New Rail from Content Browser Selection**
to add a rail from a selected Sound and bind it in one step. A GUID that no
longer matches any rail reads as *Missing rail* instead of playing silence.

Scenes carry their own binding, so a Scene is no longer necessarily a silent gap.
Scene audio is built into the managed Master, so it appears only after
**Actions > Rebuild Managed Master Sequence**.

### Driving movement from music analysis

**Curve Actions > Apply Music Analysis Curve** writes an expressive envelope from
the selected Passage's analysis map onto the **active** channel, across that
Passage's span. Pick the channel in the Music Timeline's selector first; the
action follows that selection rather than adding another picker.

Curves come from the analyzer's continuous output: intensity, rhythmic density,
brightness, the low/mid/high band split and novelty. Unit values are mapped onto
a musically legible range for the target channel — 0.5 to 1.5 for Travel Scale,
Cycle Rate Scale and Speed, and -0.25 to +0.25 cycles for Phase Bias. Channels
without a meaningful unit mapping are refused rather than guessed at.

The envelope is sampled at the Passage's music position, honouring the rail's
source-in and Passage offset, then **decimated** with Ramer-Douglas-Peucker to at
most 96 keys. That matters: the raw envelope is hundreds of samples, and a curve
made of hundreds of keys cannot be adjusted by hand afterwards. Tolerance is
relaxed rather than keys truncated, so the end of a Passage is never silently
flattened.

Applying replaces the active channel's existing keys and leaves the Master dirty
for an intentional save. Analysis remains a proposal: nothing is applied until
this action is run.

### Keyframing Wing movement against the music

The per-cue Left/Right/Top curves are **shape** curves: their horizontal axis is
phase within one cycle, so they describe what a single breath looks like and
repeat identically for the whole Passage. They cannot express "at the chorus,
travel doubles."

Time-varying movement uses three native channels on the managed Passage section,
alongside the camera channels. They are keyed against absolute Master time and
edit exactly like any other Sequencer curve:

| Channel | Applies as | Neutral |
|---|---|---|
| **Wing Travel Scale** | multiplies each cue's Inward Travel Cm | `1.0` |
| **Wing Cycle Rate Scale** | multiplies each cue's Cycle Rate Hz | `1.0` |
| **Wing Phase Bias** | added to the resolved phase offset, in cycles | `0.0` |

They modulate authored values rather than replacing them, so per-cue variation,
Phased Breathe presets and the live ordinal phase pattern all survive. A Passage
whose channels are neutral evaluates exactly as before.

Edit them either from **Music Timeline > Camera curve > Wing Movement**, which
paints one channel over the waveform and commits a key at the playhead, or in
Sequencer's curve editor under the **Wing Movement** group, which gives full
tangent and interpolation control in its own window.

Cycle Rate Scale is a *rate*, so mechanism phase is the integral of that rate
rather than a sample of it. The integral is taken on a fixed grid anchored at the
Passage start, which keeps scrubbing, seeking and reverse in agreement with
sequential playback. Negative values on Travel and Rate are clamped to zero.

Travel Scale also applies to Camera Gust rows, because it scales the resolved
travel distance rather than the reveal phase.

### Camera Gust / Fan Reveal

The default **Camera-led Reveal** keeps six pairs open immediately ahead of the camera. A narrow 0.25-pair opening ramp forms the moving leading edge: the next closed pair opens as the evaluated camera advances one quarter of the spacing toward the next pair. This is a spatial relationship, not a second timing system.

Music remains the rail. The managed Passage camera's integrated speed curve determines its actual distance along the spline; that evaluated distance determines the wing reveal. If music/camera timing accelerates, the reveal accelerates. If the camera holds, the wings hold. Scrubbing or reversing moves the same reveal frontier in either direction.

The effect defines closed as full configured `Inward Travel Cm` and open as each panel's authored rest transform. Left and Right therefore move equal distances away from the opening centre. Authored rest width, centre, panel transforms and `Inward Travel Cm` are never replaced by the preset.

The normal authoring fields inside **Mechanism > Camera Gust / Fan Reveal** are intentionally short:

- `Reveal Timing`: normally **Follow Camera / Music Rail**
- `Reveal Ahead / Fan Depth (Pairs)`: how many pairs immediately ahead are fully open
- `Opening Ramp (Pair Spacing)`: softness of the leading edge; smaller is snappier
- `After Opening`: normally **Hold Open Through Passage**

The camera-led mode needs no group partition, cascade duration or stagger. At any frame, pairs behind the camera remain open; the selected number ahead are open; one optional fractional pair at the frontier is transitioning; and all later pairs remain closed. Irregular Wing spacing is respected by interpolating the camera's physical spline distance into a continuous pair position.

For **Selected Wing Pairs**, only the ordered selected occurrences receive the behavior. **Whole Current Passage** installs the continuous reveal throughout the Passage. Changing Reveal Ahead or Opening Ramp takes effect directly; **Custom / Reapply Current Settings** is useful for copying the primary row's settings across a selection or Passage.

The previous seconds-based cascade is retained only as **Advanced Timed Cascade** compatibility mode; its duration, individual opening, stagger, direction and trigger-offset fields appear only when that mode is deliberately selected.

Every pair is sampled from the absolute Master frame and the camera's fully evaluated rail position. Forward play, reverse, scrub, seek, PIE transport and reload therefore produce the same transform at the same frame and camera distance. The Passage Actor remains tick-free and updates batched instances—there is no per-wing timer, event or Actor.

## Scene camera authority and handoff freshness

During PIE the transport claims the view target at every segment boundary. A
Passage claims its Camera Rig; a Scene claims the camera on the **Camera Cut
track of the Scene sequence itself**.

The supported split for shot-based Scenes is:

- the **Camera Cut** lives on the Scene sequence (`LS_DevScene_NN`);
- the **camera animation** may live in a Shots subsequence that animates the same
  bound camera.

The claim only needs the cut at Scene top level and does not care where the
animation lives. A Scene whose Camera Cut itself lives inside a subsequence is
**not** yet claimed — see the Scene authoring item in the project task tracker.

Camera bindings resolve through the Sequence Player, so Spawnable and custom
bindings work; a direct sequence lookup remains as a fallback for the claim that
happens before the first evaluated frame.

Handoff cameras created by **Match All Scenes** are a snapshot of the neighbouring
Passage endpoint: transform, filmback, lens, focus and focal length are copied at
match time. Any later change to that Passage's route or camera channels leaves
them stale, which reads as a jump at the boundary. Use **Check All Scenes
(read-only)** to find them; it reports the exact differing field and writes
nothing. Boundaries whose camera is artist-authored are ignored, so a deliberate
lens change across a cut is never reported as an error.

## Scene sequences and managed Master navigation

The managed Master owns one Scene subsequence block for every Scene cue. Structural identity and placement come from the Cue Score, while cameras, cuts, animation and lighting inside the child Level Sequence remain artist-authored.

- Double-click a purple Scene block to enter its child sequence in the current Sequencer.
- Ctrl-double-click to open the child in a separate Sequencer editor.
- Use the Sequencer breadcrumb/back button to return to the Master.
- Right-click the block and choose **Open Scene Sequence** or **Open in Separate Sequencer**.
- Right-click a Scene row in the Cue Desk and choose **Open Scene Sequence**.

Managed block deletion, reassignment and ordering should be performed in the Cue Score and then rebuilt, not edited structurally in Sequencer.

## Rendering a selected Passage or Cue range

`LS_InfinityStage_V1Master` intentionally does not contain fixed possessable Passage cameras. Its native Passage track resolves a Camera Rig by stable Passage GUID at evaluation time, which is correct for live PIE transport and editor scrubbing but is not the standard Camera Cut structure expected by Movie Render Queue.

Use **Cue Desk > Actions > Render Selected Range…** instead of manually adding cameras to the authoritative Master:

1. Select a **PASS** heading to render the complete Passage, including its lead-in and tail; or select one or more Cue rows to render one continuous span from the earliest selected Cue through the interval after the latest selected Cue.
2. Choose **Actions > Render Selected Range…**.
3. Infinity Stage rebuilds the managed Master, then creates or refreshes `/Game/InfinityStage/Generated/Renders/LS_<Show>_RenderSelection`.
4. The generated wrapper keeps the original absolute Master frame numbers and playback range. It nests the full Master at frame zero and exposes every intersecting Passage Camera Rig through an ordinary Camera Cut Track.
5. Scene intervals are deliberately left without a wrapper-level camera cut. The nested Scene sequence's own Camera Cut Track remains authoritative there.
6. The action saves only the Show, managed Master and generated wrapper, updates one stable Infinity Stage job without deleting other Movie Render Queue jobs, opens the wrapper in Sequencer, and opens Movie Render Queue.
7. Choose output settings and use **Render (Local)**. Save the current level and any edited Scene sequences first; **Render (Remote)** can only see saved packages.

The wrapper is fully generated and replaceable. Do not add artist tracks to it; put global artist-authored tracks on the persistent Master and shot work inside Scene sequences. Re-running the action is idempotent and updates the same queue job while preserving that job's chosen render configuration.

For robust Mac review output, render a PNG or EXR image sequence plus WAV, then encode the review movie afterward. Image sequences make an interrupted long render recoverable. Direct MP4/ProRes support depends on the enabled Unreal encoder plugins and the intended delivery codec.
