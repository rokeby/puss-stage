# GO1 Remote → UE5 Camera: Setup Guide

Getting joystick telemetry from the Unitree GO1's handheld remote into UE 5.8
camera rotation. **Parts 1–3 are verified working** on this dog (firmware
1.3.8) as of 2026-08-17; Part 4 (Unreal) is the remaining step.

**What talks to what:**

```
GO1 handheld remote
      │ (Unitree's own radio link — untouched)
      ▼
GO1 robot ──► internal head Pi (192.168.123.161)   runs: go1_remote_bridge
                        │ Ethernet, UDP port 9876
                        ▼
              Mac (192.168.123.162)                runs: UE editor + Go1Input plugin
```

Note the bridge reads robot state from the **sport-mode service at
`192.168.123.161:8082`** — i.e. a service on the head Pi itself. The control
board at `192.168.123.10:8007` (which the SDK's own `example_wifi_joy.cpp`
targets) does **not** reply on this firmware. This was the single biggest
gotcha in bring-up.

---

## Part 1 — Network (Ethernet, verified)

Ethernet from the dog's belly RJ45 to the Mac. This is the reliable path and
leaves the Mac's Wi-Fi internet intact.

1. Power on the dog, wait ~1 minute for the boards to boot.
2. Give the Mac a static address on the dog's wired subnet (once, persists):

```bash
sudo networksetup -setmanual "USB 10/100/1000 LAN" 192.168.123.162 255.255.255.0
```

   No gateway is specified deliberately — Wi-Fi stays the default route.
   If your adapter has a different service name, find it with
   `networksetup -listnetworkserviceorder`.

3. Verify the dog answers:

```bash
ping -c 3 192.168.123.161
```

4. SSH in (password `123` on this unit):

```bash
ssh pi@192.168.123.161
```

**Optional but recommended** — key login, so no password each time:

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_go1 && ssh-copy-id -i ~/.ssh/id_go1.pub pi@192.168.123.161
```

`ssh-copy-id` prompts for the dog's password; the terminal shows nothing as
you type it. Then connect with `ssh -i ~/.ssh/id_go1 pi@192.168.123.161`.

### Going wireless (untethered)

The dog's own hotspot needs **no changes to the dog whatsoever** — just move the
Mac onto it. Measured from `/etc/hostapd/hostapd.conf` on this unit:

- SSID **`Unitree_Go505540A`**, password `00000000`
- **5 GHz, channel 165** (`hw_mode=a`) — not 2.4 GHz as originally assumed in
  the plan document. Clean band, good for this traffic.
- Hosted on `wlan1`; dog is `192.168.12.1`, Mac gets DHCP `192.168.12.x`.

Steps:

1. Unplug Ethernet, join the Mac to `Unitree_Go505540A`.
2. Find the Mac's address on it: `ipconfig getifaddr en0`.
3. SSH to `192.168.12.1` and run the bridge with that address as the first
   argument. **The robot endpoint stays `192.168.123.161 8082`** — that is the
   dog's internal network and is unaffected by how the Mac connects.

Unreal needs no change (it binds `0.0.0.0`). The Mac loses internet on the
hotspot; iPhone USB tethering can supply it concurrently if needed.

Before trusting this for a performance, run `listen.py` for a few minutes while
walking the dog around and watch `gaps` — Wi-Fi loss shows up there first.

*Possible later upgrade:* `wlan0` (the Pi's built-in radio) and `wlan2` are both
present but DOWN. `wlan0` could join a normal router as a client while `wlan1`
keeps hosting the hotspot, putting dog and Mac on one network with internet on
both. That requires `sudo` and edits to system network config, so it needs an
explicit decision and a rollback plan — not done.

## Part 2 — Build the bridge (verified)

The Unitree SDK **already ships on the dog** at
`~/Unitree/sdk/unitree_legged_sdk` — use it, don't download one. It matches
the installed firmware, which is exactly what you want.

Important quirks of that copy:
- Its `CMakeLists.txt` references example sources that don't exist, so
  `cmake ..` **fails**. We compile directly with `g++` instead.
- Its `example_wifi_joy.cpp` is stale relative to its own headers (uses
  `forwardSpeed`/`sideSpeed`, but `comm.h` defines `velocity[2]`/`yawSpeed`).
  The headers are the source of truth.
- Nothing inside `~/Unitree` is modified by any of this — we only read its
  headers and link its `.so`.

From the Mac, copy the source over:

```bash
scp "/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/go1_pi_bridge/go1_remote_bridge.cpp" pi@192.168.123.161:~/go1_bridge/
```

(First time only: `ssh pi@192.168.123.161 'mkdir -p ~/go1_bridge'`.)

Then on the dog, compile — no Boost, no LCM, no installs needed:

```bash
S=$HOME/Unitree/sdk/unitree_legged_sdk; cd ~/go1_bridge && g++ -O2 -std=c++11 -o go1_remote_bridge go1_remote_bridge.cpp -I$S/include $S/lib/libunitree_legged_sdk_arm64.so -lpthread -Wl,-rpath,$S/lib
```

Silence means success; the binary lands at `~/go1_bridge/go1_remote_bridge`.

## Part 3 — Telemetry test (verified: 1489 packets / 30s, 0 gaps)

**Safety:** have the dog **lying down**, clear space around it, handheld remote
in your hands. The bridge sends an idle `HighCmd` (mode 0, all velocity and
posture fields zeroed every tick) purely to solicit state replies — it never
commands motion — but the remote's L2+B damping and the power button remain
your stop.

1. On the Mac, start the listener:

```bash
python3 "/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/go1_pi_bridge/listen.py"
```

   Accept the macOS "allow incoming connections" prompt if it appears.
   (If you redirect its output to a file, use `python3 -u` or Python buffers
   it and the file looks empty.)

2. On the dog, run the bridge:

```bash
cd ~/go1_bridge && ./go1_remote_bridge 192.168.123.162 9876 100 192.168.123.161 8082 8092
```

   Arguments: `<mac_ip> <mac_port> <rate_hz> <robot_ip> <robot_port> <local_port>`.

### Rates (measured 2026-08-17)

The robot's sport service publishes `HighState` at **exactly 50 Hz** — verified
by polling at 200 Hz and counting changed states: 50/s, rock steady. That is a
hard ceiling on stick resolution; polling faster cannot reveal intermediate
values because none exist.

We nonetheless run the bridge at **100 Hz**. This doesn't create information —
roughly half the packets duplicate the previous value — but our send clock and
the robot's 50 Hz clock are independent, so oversampling bounds how long a new
value can sit unnoticed at ~10 ms instead of ~20 ms. At ~100 bytes/packet the
cost is ~10 KB/s.

The `[stats]` line reports `state_chg/s` and `remote_chg/s` for re-measuring
this at any time. Note `remote_chg/s` only means something while the sticks are
actually moving; at rest it just counts idle noise in the 40-byte block.

End-to-end budget for camera work: up to 20 ms source age + ~1 ms transit +
up to one UE frame. Fine for pan/tilt, which integrates over time rather than
snapping. If fast moves ever look steppy, add smoothing on the UE side rather
than raising the packet rate.

3. Move the sticks. Axes should sweep to ±1.00 and `keys` should change on
   button presses. Healthy looks like `lost=False`, `gaps=0`.

**Troubleshooting:**
- Every packet shows `lost=True` → wrong robot endpoint. It must be
  `192.168.123.161 8082`.
- `Bind client ip&port failed: Address already in use` → the local port is
  taken by the dog's own services. The SDK only warns, then silently fails to
  receive. Pass a different last argument (8091, 8092, 8095 all worked).
- Nothing on the Mac but the dog shows sane values → macOS firewall, or wrong
  Mac IP.

## Part 4 — Into Unreal

1. Open `PussStage.uproject`. The `Go1Input` plugin is already enabled and
   compiled — it loads automatically.
2. Select the actor whose rotation the remote should drive (your camera actor,
   or a parent it's attached to).
3. Details panel → **+ Add** → search "Go1" → **Go1 Remote Receiver**.
4. Settings worth knowing (Details panel, "Go1" categories):
   - `Listen Port` 9876, `Stale Timeout Ms` 150 — leave as is.
   - `Yaw Deg Per Sec` / `Pitch Deg Per Sec` — rotation speed at full stick.
   - `Deadzone` 0.08 — raise if the camera drifts with sticks centred.
   - `Drive Owner Rotation` — right stick rotates the actor.
   - `Show Debug` — on-screen status line while playing.
5. With the bridge running on the dog, press **Play**. Expect a green
   `GO1 LIVE | seq … | age … ms` line, and the right stick should pan/tilt.
   Ctrl-C the bridge and it should turn red (`STALE`) with rotation frozen —
   that's the fail-safe.

Left stick and buttons aren't bound to anything yet but are readable in
Blueprint from the component: `Get Left Stick`, `Is Button Down`, `Is Fresh`.

### Rotation modes

- **Absolute** (debug shows `GAZE`) — stick position *is* the angle, bounded by
  `Yaw/Pitch Range Deg`, springing back to centre when released. Reads as a head
  turn. This is the default and avoids the "runs into the clamp and jitters at
  the limit" behaviour that velocity mode has.
- **Velocity** (`TURN`) — stick is a turn rate; the view holds where you leave
  it. Reads as body rotation.

The remote can switch between them live (`Allow Remote Mode Toggle`, default
F1); switching into Absolute adopts the current view as centre so nothing
snaps. `Allow Remote Recenter` (default F2) re-captures centre on demand.
**Caution:** the dog's own controller also receives these button presses. F1/F2
are usually inert in sport mode, but verify with the dog prone first.

### Giving the dog control (do this first, since 2026-08-20)

Camera ownership is authored in the Show, not on this component. The authored
default is `Timeline`, which means **the dog controls nothing until you say
otherwise** — the most likely reason for "telemetry is live but the camera
doesn't move".

Give it control either by:

- **Authoring it:** set Camera Owner on the Passage or Scene (Cue Desk) to
  `DogGazeOnly` (bounded gaze, springs to centre) or `DogFreeLook` (free turn,
  view holds). This is the durable choice and travels with the Show.
- **Live override:** the Show Root's transient `bOverrideCameraOwner` +
  `CameraOwnerOverride`. Correct mid-performance because it never rewrites the
  score, and it is deliberately not saved.
- **Bypassing ownership:** untick `Use Show Camera Ownership` on the component
  to return to pre-integration behaviour, where the component decides for itself.

While ownership governs, `Follow Dog Mode` and the remote mode-toggle below are
ignored; the Show is authoritative about gaze versus free look.

**Recommended placement:** put the component on the **Show Root**, not on a
camera, and leave `Target Camera Actor` empty. It then rotates the player's
current view target, which follows Sequencer camera cuts across Passages and
Scenes — one receiver, one socket, every camera. Set `Target Camera Actor`
explicitly to pin a single camera, or for editor mode, which has no player
controller to ask.

### Following the dog's own mode (preferred over button toggling)

The dog's Select button switches it between movement mode (body rotates) and
standing mode (head rotates, returns to centre) — which is exactly the
GAZE/TURN distinction. The bridge forwards `HighState.mode`, so with
`Follow Dog Mode` on (default) the camera mirrors the dog's real state instead
of counting button presses, and cannot drift out of sync.

**Calibration still needed:** the mode integers were not confirmed, because the
dog was lying down all session and reports `mode=0` (idle) while prone.
`Dog Mode For Gaze` (default 1) and `Dog Mode For Turn` (default 2) follow
Unitree's documented convention but vary by firmware. To confirm: stand the dog,
watch `dog mode N` in the on-screen debug line, press Select, and note the two
values it alternates between. Set the two integer fields to match — no rebuild
required. Unrecognised values deliberately leave the current mode alone, so
mis-set values degrade gracefully rather than flapping.

### Editor mode (no PIE)

`Go1 | Editor` → `Run In Editor` receives telemetry and drives rotation in the
editor viewport without pressing Play, for framing shots while authoring.

- It **rotates the actor for real and dirties the level package**. The rotation
  at switch-on is captured and restored when switched off (or on level close /
  component unregister), but do not Save All while it is running.
- Editor mode and PIE both bind UDP 9876. Turn `Run In Editor` off before
  pressing Play, or whichever binds second gets `NO DATA`.

### Matching the physical screen

For the swing to cohere with a screen the performer is looking at, both the yaw
range and the camera FOV derive from the same two measurements:

```
YawRangeDeg = degrees( atan( (ScreenWidth / 2) / ViewerDistance ) )
Camera FOV  = 2 x YawRangeDeg
```

**This installation** — 3.5 m screen at 3 m: `Yaw Range Deg` **30.3**, camera
horizontal FOV **60.5°**, `Pitch Range Deg` **18.2** (16:9 screen, 1.97 m tall).
If FOV is wider than the screen's true angular size the image feels compressed
and under-responsive; narrower and it overshoots.

### Sequencer interaction

The component ticks in `TG_PostUpdateWork`, i.e. after LevelSequence evaluation,
so its rotation lands on top rather than alternating with the sequence (which
looks like jitter). In Absolute mode it **overrides** sequence-driven camera
*rotation* — intended here, since the Passage 1 camera's rotation keyframes are
suspended in favour of live control. Sequence-driven camera **location** still
applies, so the camera can still travel while the dog controls the gaze.

If you later want sequence rotation *and* dog gaze to compose rather than one
overriding the other, the structure is a parent "gaze pivot" actor carrying this
component with the Passage camera attached beneath it — Sequencer then animates
the camera's relative transform while the pivot adds gaze on top. That changes
level hierarchy in InfinityStage authoring data, so it's a deliberate decision,
not a default.

Verified button bits: **X = bit 10 (0x0400)**, **Y = bit 11 (0x0800)**, matching
the `EGo1RemoteButton` enum order (R1, L1, Start, Select, R2, L2, F1, F2, A, B,
X, Y, Up, Right, Down, Left).

## Part 5 — Day-to-day

- The bridge is a foreground program: SSH in, run it, Ctrl-C to stop. Keep a
  Terminal tab with it running while working in Unreal.
- Battery swaps reboot the Pi; the SSH key and the compiled binary both
  survive. Just SSH back in and start it again.
- The Mac's static IP persists across reboots.
- No auto-start service is installed (deliberately — keep it manual until the
  setup has proven itself over a few sessions).

## Part 6 — Later: PC migration

Nothing on the dog changes. On the PC: copy the project including
`Plugins/Go1Input/`, delete `Binaries/` and `Intermediate/` (they hold Mac
dylibs), rebuild, add a Windows firewall rule for inbound UDP 9876 on **all**
profiles, and pass the PC's IP as the bridge's first argument.

Full Windows command set — static IP, firewall, the `ssh-copy-id` workaround
(it does not exist on Windows), diagnostics equivalents and a troubleshooting
checklist — is in `Docs/Go1TelemetryProgress.md`, appendix H.
