# Sun, Moon and Stars Cycle

The Infinity Stage uses one show-wide `AInfinityStageCelestialRig`. It rotates the
sun and moon on opposite arcs, fades their directional light, blends Skylight and
height-fog colour, and reveals/rotates the built-in star dome at night.

The rig has no Tick-based clock. Each managed Passage section evaluates it from
the absolute Master Sequence frame, so play, reverse, rate changes, jumps and
scrubbing always produce the same time of day.

## Editor working light

Level editing has a separate preview policy so scrubbing a night-time passage
does not leave the whole stage too dark to work on:

1. In the Cue Desk, open **View > Editor Lighting**.
2. **Manual Editing Light** is the default. It protects the editor world from
   timeline day/night changes while wings, cameras and music continue to scrub.
3. Choose **Bright Work Light — 12:00**, **Soft Morning — 09:00**, **Dusk —
   18:00** or **Night — 00:00** for a quick working state.
4. Choose **Select Celestial Rig for Detailed Controls** for an exact 0–24 hour
   **Editor Preview Time**, Sun/Moon intensities and colors, Skylight day/night
   levels, fog colors, stars and actor bindings in the ordinary Details panel.
5. Choose **Follow Master While Editing** only when the production day/night
   progression should be visible during Cue Desk or Sequencer scrubbing.

The editor choice is stored on the Celestial Rig in the level and supports
undo/redo. It is a preview policy only: PIE, live transport, Movie Render Queue
and packaged playback always evaluate the absolute Master phase and ignore the
manual editor time.

## Passage authoring

Click the body of a **PASS** heading in the Cue Desk and edit **Temporality** in
the passage-wide inspector. The disclosure arrow is a separate control used only
to expand or collapse the Wing Pair rows.

- **Animate Time of Day** holds the sky at Passage entry when disabled.
- **Seconds Per Day/Night Cycle** is 20 seconds by default for one complete
  sunrise-to-sunrise cycle at 1x.
- **Passage Temporality Rate** is the time-compression multiplier. `1` is one cycle per
  20 seconds, `10` is ten apparent days in the same interval, and `0` holds.
- **Entry Time Jump (Days)** makes an intentional story jump without changing
  the ongoing rate. `0.5` swaps day and night; whole numbers preserve the visible
  time of day.

Passage rates integrate in chronological order. Scene/Sequence cues hold the
celestial phase unless their own Level Sequence supplies different lighting.

The phase convention is `0` midnight, `0.25` sunrise, `0.5` noon, and `0.75`
sunset. `InitialPhaseCycles` on the rig sets the show-start time.

## Fixture environment

`Scripts/add_infinity_stage_dusk_sky.py` upgrades the saved vertical-slice map
with tagged, editable Sun, Moon, Skylight, fog and atmosphere actors and binds
them to the celestial rig. Run that one-shot authoring script only while the
interactive editor is closed so two Unreal processes never save the map at once.
