# GO1 → UE5 Telemetry: Progress Report

**Date:** 2026-08-18
**Status:** Working end to end. Remote → dog → Mac → UE5 camera rotation, verified live.
**Remaining:** calibration and performance, not plumbing.

## Keeping this document current

This is the **authoritative handover for the telemetry subsystem**, registered
in the overall project handover as thread 17 of
`Docs/PussProjectTaskTracker.md`. When this subsystem changes materially:

1. Update the affected section here (status table, measurements, configuration,
   open items) — not a transcript, only what changes a future decision.
2. Add a row to the **Progress and verification ledger** in
   `Docs/PussProjectTaskTracker.md`, with evidence, not just a claim.
3. If the change produces a durable lesson, add it to **Key learnings and
   mistakes not to repeat** in that same tracker.
4. If it changes how the thing is *operated*, update `Docs/Go1TelemetrySetup.md`
   and the offline card in `go1_pi_bridge/README.md` too — those are what get
   read on the dog's hotspot with no internet.
5. Keep `AGENTS.md`'s pointer accurate if file locations move.

State findings as verified or unverified, and say which. Several claims here
were wrong before they were measured; the value of this file is that it now
distinguishes the two.

Companion documents:
- `Docs/Go1TelemetrySetup.md` — how to run it, step by step.
- `go1_pi_bridge/README.md` — offline command card and troubleshooting.
- `~/Documents/Codex/2026-08-16/i-h/dog-pi-ue5-telemetry-plan.md` — original plan, amended.

---

## 1. What works

| Stage | Status | Evidence |
|---|---|---|
| SSH into dog's internal Pi | Working | key-based login, survives reboots |
| Bridge reads remote via SDK | Working | axes sweep to ±1.00, buttons decode |
| UDP dog → Mac | Working | 1489 packets / 30 s, **0 gaps** |
| UE receives and parses | Working | `age` 3–10 ms on Ethernet |
| Camera rotation from stick | Working | absolute mode, 30.3° range |
| Fail-safe on packet loss | Working | axes snap to zero, readout turns red |
| Show camera ownership | Working | resolved live in the automated PIE fixture |
| Wireless (dog hotspot) | **Untested** | command prepared, not yet run |

## 2. Architecture

```
GO1 handheld remote
      │  Unitree's own radio link (untouched)
      ▼
GO1 robot ──► internal head Pi (192.168.123.161)   go1_remote_bridge (C++)
                        │  UDP :9876, JSON, 100 Hz
                        ▼
              Mac (192.168.123.162 wired / 192.168.12.71 hotspot)
                        │
                        ▼
              UE 5.8 + Go1Input plugin ──► Passage 1 Camera rotation
```

No extra hardware was needed. The bridge runs on the Raspberry Pi already
inside the dog, using the Unitree SDK that already ships on it.

## 3. What was built

**On the dog** (`~/go1_bridge/`, nothing in `~/Unitree` modified):
- `go1_remote_bridge.cpp` — reads `HighState.wirelessRemote` via the Legged SDK,
  sanitises, sequences, sends JSON UDP at a fixed rate. Sends an idle `HighCmd`
  (mode 0, all motion fields zeroed every tick) purely to solicit state replies;
  it never commands motion.

**In the project:**
- `go1_pi_bridge/` — bridge source, `listen.py` test listener, README.
- `Plugins/Go1Input/` — UE plugin, one component `Go1 Remote Receiver`:
  socket-thread receive with latest-value handoff, receiver-clock staleness,
  deadzone + smoothing + response curve, absolute and velocity rotation modes,
  dog-mode mirroring, editor-mode operation, on-screen diagnostics.
- `Docs/Go1TelemetrySetup.md`, this file.

## 4. Measurements

| Quantity | Value | Note |
|---|---|---|
| Robot `HighState` publish rate | **exactly 50 Hz** | measured by polling at 200 Hz; hard ceiling on stick resolution |
| Bridge send rate | 100 Hz | oversamples to bound value age at ~10 ms rather than ~20 ms |
| Packet loss (Ethernet) | 0 gaps / 1489 packets | |
| Packet age in UE (Ethernet) | 3–10 ms | |
| UE frame rate (PIE) | ~22 fps | the current weak link — see §7 |
| Dog hotspot | 5 GHz, channel 165 | `Unitree_Go505540A` |

## 5. Findings that cost time

1. **Robot endpoint is `192.168.123.161:8082`** (sport service on the Pi itself).
   The control board at `192.168.123.10:8007` — which the SDK's own
   `example_wifi_joy.cpp` targets — never replies on firmware 1.3.8.
2. **The on-dog SDK's `CMakeLists.txt` is broken** (references example sources
   that don't exist), so `cmake ..` fails. We build with a direct `g++` call.
3. **That SDK's own example is stale relative to its headers** — it sets
   `forwardSpeed`/`sideSpeed`, while `comm.h` defines `velocity[2]`/`yawSpeed`.
   Headers are the source of truth.
4. **The SDK only warns on local-port bind failure**, then silently receives
   nothing. Symptom is a permanent `source_lost`. Try another local port.
5. **Rotation must be written in `TG_DuringPhysics`.** `TG_PostUpdateWork` runs
   after the camera POV snapshot, so the actor rotates but nothing renders —
   indistinguishable from the input being dead. This cost a debugging round.
6. **Absolute beats velocity mapping for this use case.** Velocity mode ran into
   the pitch clamp and juddered against it; absolute mode has no limit to hit.
7. **The hotspot is 5 GHz**, not 2.4 GHz as the original plan assumed.

## 6. Current configuration

Component on the "Passage 1 Camera + Shadow figures" actor:

| Setting | Value | Rationale |
|---|---|---|
| `Rotation Mode` | Absolute (GAZE) | stick = angle; no clamp to hit |
| `Yaw Range Deg` | 30.3 | `atan(1.75 / 3)` for a 3.5 m screen at 3 m |
| `Pitch Range Deg` | 18.2 | same, 16:9 vertical |
| Camera FOV | 60.5° | twice the yaw range; makes the screen a window |
| `Invert Pitch` | on | matched to preference |
| `Smoothing Time Ms` | 60 | tune by feel |
| `Max Axis Rate Per Sec` | 0 (off) | slew limit — 0.5 caps the sweep at ~15 deg/s with a 30.3 deg range, as if the sticks were handled gently |
| `Response Exponent` | 1.0 | try 1.5–2.0 for finer centre control |
| `Rotation Tick Group` | During Physics | must precede camera POV snapshot |
| `Follow Dog Mode` | on | mirrors dog state; cannot drift |
| `Run In Editor` | off | see limitations |

## 7. Open items

0. ~~Integrate with InfinityStage camera ownership.~~ **Done 2026-08-20** — see
   §10.

1. **Dog mode mirroring — tested on hardware, removed.** Measured 2026-08-20 over
   the wired link with the bridge at 50 Hz: standing/Select reported `mode = 0`
   on 501/501 packets and move mode (START) reported `mode = 0` on 401/401. The
   value `2` that `Dog Mode For Turn` expected **never appeared in any state**.
   An earlier noisy 0/1 mix turned out to be a transitional settling condition,
   not a property of standing. `HighState.mode` as forwarded therefore cannot
   distinguish the two states, so `bFollowDogMode`, `DogModeForGaze` and
   `DogModeForTurn` were deleted rather than left as dead tuning knobs.
   **Superseded by Show-authored ownership:** `EInfinityCameraOwner` on the
   Passage or Scene decides gaze versus free look, which is deterministic, part
   of the score, and still correct when the dog is absent. `DogMode` is still
   parsed and shown in the debug readout, since the field does arrive and is
   useful diagnostically.

2. **~22 fps.** Not a telemetry problem — `age` is 3–10 ms — but it undercuts
   the feel. Measure a standalone build before optimising; PIE in a heavy
   InfinityStage scene is usually far worse than a packaged run.
3. **Wireless untested.** Command is prepared. Watch `gaps` and `age`.
4. **Feel tuning:** smoothing time and response exponent.
5. **Multi-passage:** if more than one passage camera should be dog-driven, do
   not duplicate the component — only one can hold UDP 9876. Use a single
   receiver on a persistent actor and read `Get Right Stick` / `Is Fresh` from
   Blueprint on the others.

## 8. Known limitations

- **One socket, one owner.** Editor mode and PIE both want UDP 9876; whichever
  binds second gets nothing. Untick `Run In Editor` before pressing Play. Since
  §10, a single receiver on the Show Root can serve every camera, so this stops
  being a constraint on multi-camera use once the component is moved there.
- **Editor mode rotates the camera for real**, dirtying the level package. The
  camera is put back as it was when editor mode is switched off, but do not
  Save All while it runs. It also does not change the main viewport view unless you
  are piloting the camera or watching its preview thumbnail — so its usefulness
  for framing is limited.
- **Superseded 2026-09-29 (source; unbuilt as of writing, see §10 "Look
  layering"):** Absolute mode used to *override* sequence-driven camera
  rotation, and Velocity mode lost to a live rotation track. Both are replaced
  by a look offset layered on the camera component, which composes with the
  route or sequence instead. That is the "gaze pivot" this section once named,
  done inside the component rather than as authoring data.
- **No auto-start.** The bridge is a foreground process by choice; it stays
  manual until the setup has proven itself over several sessions.
- **Wi-Fi means no internet on the Mac**, so no Claude access while untethered
  unless an iPhone supplies internet over USB.

## 9. Safety position

The dog stayed prone for the entire session, with the remote in the operator's
hands. The bridge sends `mode = 0` with every velocity, position and euler field
explicitly zeroed on each tick — it solicits state and commands nothing. Nothing
in `~/Unitree` was modified, no `sudo` was used, no packages were installed, and
no system or service configuration was changed. The only writes to the dog were
`~/.ssh/authorized_keys` and the new `~/go1_bridge/` folder.

Not yet exercised: the dog **standing** while the bridge is connected. Keep the
remote in hand the first time.

## 10. Infinity Stage camera ownership (2026-08-20)

Arbitration now belongs to the Show, not to this component.
`UGo1RemoteReceiverComponent` consults
`AInfinityStageShowRoot::GetCurrentCameraOwner()` each tick and maps:

| Authored owner | Behaviour |
| --- | --- |
| `Timeline` | The look eases back to zero, then the component writes **nothing**. The sequence drives the camera. |
| `DogGazeOnly` | Absolute mode — stick is a bounded angle off the driven view, springs back to it. |
| `DogFreeLook` | Velocity mode — stick is a turn rate, the view holds. |

**Operational consequence — read this before wondering why the dog is dead.**
The authored default is `Timeline`, so after this change the dog controls
nothing until ownership says otherwise. Give it control by setting Camera Owner
on the Passage or Scene (Cue Desk), or by using the Show Root's transient live
override (`bOverrideCameraOwner` + `CameraOwnerOverride`), which is the right
tool mid-performance because it never rewrites the score. To bypass ownership
entirely and return to the previous behaviour, untick
`Use Show Camera Ownership` on the component.

While ownership is governing, `Follow Dog Mode` and the remote mode-toggle are
**ignored** — the Show is authoritative about gaze versus free look. They remain
as fallbacks for a level with no Show Root.

**Which camera gets rotated.** `Target Camera Actor` is empty by default, in
which case the component rotates the player's current view target — so it
follows Sequencer camera cuts across Passages and Scenes, and one receiver
serves every camera. This is why the receiver should live on the **Show Root**
rather than on a camera. Set `Target Camera Actor` explicitly to pin one camera,
or for editor mode, where there is no player controller to ask. It falls back to
the component's own actor, so the original "component on the camera" setup still
works.

Transitions do not snap: see "Look layering" below for what happens at owner
changes, cuts and blends.

**Blended handovers (verified 2026-09-26).** The transport can blend a
handover instead of cutting (Show Root → Transport → Transport|Handover; both
blend defaults ship at 0.0, i.e. cuts). While a blend is in flight, UE 5.8's
`GetViewTarget()` reports the **pending (incoming)** camera, so the receiver
already steers and re-centres on the shot the audience is watching arrive, from
the blend's first frame. Verified by
`InfinityStage.Go1.ReceiverDrivesIncomingCameraDuringBlend`. That test also
asserts the engine behaviour, so an engine upgrade that changes it is caught.
*Correction:* on 2026-09-25 this section said the opposite, that
`GetViewTarget()` reports the outgoing camera mid-blend, and a code change
(50a07fd) was made on that premise. The test disproved it; the change was
removed as redundant.

**Look layering (2026-09-29, Look & camera; conductor-approved. Source only:
UNBUILT and UNTESTED until the conductor's build batch runs).** This replaces
the 26 Sep re-centre scheme below it.

*The regression it fixes (diagnosed in source 29 Sep, independently confirmed
by a second audit).* Absolute mode wrote `SetActorRotation(Base + stick)` every
frame in `TG_DuringPhysics`, after Sequencer, where `Base` was a world rotation
captured once. It did this even with no telemetry. So on a dog-owned Passage
the camera held its starting direction however the route bent, and the mouse
stand-in's turn was thrown away on the next frame. Velocity mode's write was
gated on fresh telemetry, so with no dog the mouse worked in the Void (Free
Look) and rubber-banded in every Passage (Gaze). This went live on 26 Sep, when
every Passage became Dog Gaze. Under Timeline ownership the cameras had
followed the route tangent correctly.

*What it does now.* The look is a pitch/yaw **offset** written to the live
camera's component: the first active camera below the root, or the root when
there is none. The root keeps its route or sequence rotation, so the view is
driven + look. Yaw turns about world up and pitch about the camera's right, so
the horizon never rolls. Min/Max Pitch limit only what the look adds. Anything
that writes that component between our writes (the route, a sequence, an
operator) is adopted as the new driven rotation, so a held playhead never
accumulates. On a rig, the shadow cat and follow light hang off the root: they
stay on the route when the dog looks away. On 26–29 Sep they swung with the
gaze.

| Situation | Look |
| --- | --- |
| Gaze | stick × range off the driven view; mouse (no dog) adds up within the same range |
| Free Look | stick rate and mouse integrate; the view holds |
| Timeline | eases to zero over `LookHandoverSeconds` (0.6 s), then hands off entirely |
| Owner change, dog arrives or drops out, re-centre | eases from the look as it stands, so nothing steps (Gary: "don't jump") |
| Cut between dog-owned cameras | the look carries across unchanged |
| Hard cut into a Timeline shot | the look drops at once; the shot opens as authored. Timeline taking over within 0.1 s after a cut counts as the same cut |
| Blend | the incoming camera carries the look; the outgoing one keeps its look until the blend lands, then is put back as driven |

The remote re-centre button and `RecenterRotation()` now mean *look back down
the driven view*: they clear what Free Look and the mouse accumulated. In Gaze
the stick still decides the angle. `ComposeGazeRotation`, `CentreKeepingView`
and the captured base are gone.

Tests (new, unbuilt): `InfinityStage.Go1.LookLayersOnDrivenCamera`,
`InfinityStage.Go1.MouseLookHoldsInGazeAndFreeLook` (pins the Gaze/Free Look
asymmetry above) and `InfinityStage.Go1.LookHandoverEasesWithoutStep`.
`ReceiverDrivesIncomingCameraDuringBlend` gains the blend-hold assertions.
`RecentreKeepsViewWithStickHeld` is removed, because the functions it tested
no longer exist. Backup: `Backups/PreGo1LookLayering-20260929-1434`.

**Re-centre without a jump (2026-09-26; SUPERSEDED 29 Sep by Look layering
above).** The automatic re-centres subtracted the stick's present deflection
from a captured world base. That base was the root cause of the route-follow
regression.

**Camera owners (2026-09-26, Gary).** Passages 1–6 are Dog Gaze Only, Scene 6
(the Void) is Dog Free Look, and everything else is Timeline. The live
**Force Dog** override no longer applies inside Sequence cues (the Opening, the
five Interactions, the Closing), so walking the dog cannot swing the camera
behind the curtain. **Force Timeline** still wins everywhere (the dog-failure
drill).

**Verified:** UE 5.8 build clean; `nm` confirms `GetDrivenCameraActor`,
`ResolveShowRoot` and `bUseShowCameraOwnership` in the **base** dylib with the
editor closed and no numbered side-libraries; **37/37 automation tests pass**
(`Saved/Logs/Go1OwnershipIntegration.log`, exit code 0, zero `Result={Fail}`).
In the `SavedFixturePIE` functional test the component logged
`Show Root found: InfinityStageShowRoot_0` and
`Camera owner -> Timeline (input released)`, proving live resolution against the
saved vertical-slice level. **No Show, level or Master content was opened or
saved.**

**Receiver relocated to the Show Root (2026-08-20).** The component now lives on
`InfinityStageShowRoot_0` ("Infinity Stage — One Master Authority") instead of
`InfinityStageCameraRig_0` ("Passage 01 — Camera + Shadow Figures"), with
`Target Camera Actor` empty so it drives the live view target. One receiver now
serves every camera and the one-socket constraint no longer limits multi-camera
use.

Done headlessly with the editor closed, after backing up the level to
`Saved/Go1Move/Backup/`. `add_component_by_class` is not exposed in this build;
the editor's own `SubobjectDataSubsystem` path was used instead, and
`destroy_component()` requires its calling object as an argument. Scripts are
kept in `Saved/Go1Move/` (inspect / move / verify).

Read-back in a fresh process confirms: exactly **one** component, hosted on
`InfinityStageShowRoot`, all 26 settings preserved (`yaw_range_deg` 30.3,
`pitch_range_deg` 18.2, `response_exponent` 1.5, `invert_pitch` true, Absolute,
`TG_DuringPhysics`), `target_camera_actor` and `show_root` both empty so both
resolve automatically. **Exactly one content file was written** — the level —
and **37/37 tests still pass** with the runtime log showing the receiver
starting from its new home and resolving `Show Root found:
InfinityStageShowRoot_0`.

---

# Appendix: Complete command reference

Every command needed to run what we've built, grouped by task. Commands are
labelled **[Mac]** or **[Dog]** — "Dog" means inside an SSH session on the
internal head Pi.

## A. One-time setup (already done — for rebuild or a new machine)

**[Mac]** Give the Mac a static address on the dog's wired subnet. Adapter
service name may differ; list them with `networksetup -listnetworkserviceorder`.

```
sudo networksetup -setmanual "USB 10/100/1000 LAN" 192.168.123.162 255.255.255.0
```

**[Mac]** Create an SSH key and install it on the dog (asks for the dog's
password, `123`; the terminal shows nothing while you type it):

```
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_go1
```

```
ssh-copy-id -i ~/.ssh/id_go1.pub pi@192.168.123.161
```

**[Dog]** Create the working folder (nothing in `~/Unitree` is ever modified):

```
mkdir -p ~/go1_bridge
```

## B. Daily run — Ethernet

**[Mac]** Start the bridge and leave the tab open:

```
ssh -i ~/.ssh/id_go1 pi@192.168.123.161 'cd ~/go1_bridge && ./go1_remote_bridge 192.168.123.162 9876 100 192.168.123.161 8082 8092'
```

Stop it with Ctrl-C. Then open the project and press Play.

## C. Daily run — Wireless (dog's hotspot)

Join Wi-Fi `Unitree_Go505540A`, password `00000000`. No internet on the Mac
while connected unless an iPhone is tethered over USB.

**[Mac]** Confirm the Mac's address on that network:

```
ipconfig getifaddr en0
```

**[Mac]** Run the bridge, substituting that address as the first argument:

```
ssh -i ~/.ssh/id_go1 pi@192.168.12.1 'cd ~/go1_bridge && ./go1_remote_bridge 192.168.12.71 9876 100 192.168.123.161 8082 8092'
```

Only the SSH host and the Mac's IP differ from Ethernet. The robot endpoint
`192.168.123.161 8082` is internal to the dog and never changes.

## D. Rebuilding after a code change

**[Mac]** Copy the bridge source to the dog:

```
scp -i ~/.ssh/id_go1 "/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/go1_pi_bridge/go1_remote_bridge.cpp" pi@192.168.123.161:~/go1_bridge/
```

**[Dog]** Compile it (no Boost, no LCM, no installs needed):

```
S=$HOME/Unitree/sdk/unitree_legged_sdk; cd ~/go1_bridge && g++ -O2 -std=c++11 -o go1_remote_bridge go1_remote_bridge.cpp -I$S/include $S/lib/libunitree_legged_sdk_arm64.so -lpthread -Wl,-rpath,$S/lib
```

Silence means success.

**[Mac]** Rebuild the UE plugin (the editor must be restarted afterwards to
load it; building while the editor runs is fine):

```
"/Users/Shared/Epic Games/UE_5.8/Engine/Build/BatchFiles/Mac/Build.sh" UnrealEditor Mac Development -Project="/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/PussStage.uproject" -WaitMutex
```

## E. Testing and diagnostics

**[Mac]** Watch raw packets without involving Unreal (Unreal must not be
holding the port; Ctrl-C to stop):

```
python3 "/Users/zhexi-mbp-22/Documents/Unreal Projects/PussStage/go1_pi_bridge/listen.py"
```

Use `python3 -u` instead if redirecting output to a file, or Python buffers it
and the file looks empty.

**[Mac]** Find what is holding the UDP port — the first thing to check when UE
shows `NO DATA`, or when editor mode and PIE conflict:

```
lsof -nP -iUDP:9876
```

**[Mac]** Confirm the dog is reachable and SSH is up:

```
ping -c 3 192.168.123.161
```

```
nc -z -G 3 192.168.123.161 22
```

**[Dog]** Is the bridge running?

```
pgrep -a go1_remote_bridge
```

**[Dog]** Stop every bridge instance (use before restarting, or after a
network change, so a stale one isn't sending to a dead address):

```
pkill -f go1_remote_bridge
```

**[Dog]** Find a free local port if the SDK reports
`Bind client ip&port failed` (it only warns, then silently receives nothing):

```
for p in 8090 8091 8092 8095 8099; do ss -uln | grep -q ":$p " && echo "$p BUSY" || echo "$p free"; done
```

**[Dog]** Run detached for 30 minutes, surviving terminal closure, logging to
a file:

```
cd ~/go1_bridge && nohup timeout 1800 ./go1_remote_bridge 192.168.123.162 9876 100 192.168.123.161 8082 8092 > /tmp/bridge.log 2>&1 &
```

```
tail -f /tmp/bridge.log
```

## F. Reading the bridge's stats line

```
[stats] seq=200 lost=0 sock_err=0 poll/s=100 state_chg/s=50 remote_chg/s=38 mode=0 gait=0 lx=+0.00 ly=+0.00 rx=+0.00 ry=+0.00 keys=0x0000
```

- `lost=1` — no replies from the robot. Wrong endpoint; must be `.161 8082`.
- `sock_err` — sends to the Mac are failing. Wrong IP, or Wi-Fi dropped.
- `state_chg/s` — robot publish rate; should read 50.
- `remote_chg/s` — only meaningful while the sticks are moving.
- `mode` / `gait` — the dog's own state. Reads 0 while prone.
- `keys` — button bitmask. Verified: X = `0x0400`, Y = `0x0800`.

## G. Undoing things

**[Mac]** Return the Ethernet adapter to DHCP:

```
sudo networksetup -setdhcp "USB 10/100/1000 LAN"
```

**[Dog]** Remove everything we added (the SSH key line must be deleted by hand
from `~/.ssh/authorized_keys` if you want that gone too):

```
rm -rf ~/go1_bridge
```

Nothing else on the dog was modified, so there is nothing else to undo.

---

# Appendix: Running from a Windows PC

Nothing on the dog changes — the bridge, the SDK build, the robot endpoint and
the protocol are all identical. Only the receiving machine differs. Commands
below run in **PowerShell**; those marked *(admin)* need "Run as Administrator".

## H1. Move the project

1. Copy the whole project, including `Plugins/Go1Input/`.
2. Delete `Binaries/` and `Intermediate/` — they hold Mac `.dylib`s that are
   meaningless on Windows and can confuse the build.
3. Right-click `PussStage.uproject` → **Generate Visual Studio project files**,
   then open it; UE will offer to rebuild the missing modules. Requires Visual
   Studio 2022 with the "Desktop development with C++" workload.

The plugin source is cross-platform (`FUdpSocketReceiver`, `FSocket`), so no
code changes are needed. To build from the command line instead:

```
& "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" UnrealEditor Win64 Development -Project="C:\path\to\PussStage.uproject" -WaitMutex
```

## H2. Network — Ethernet path

List adapters to find the right name (often "Ethernet" or "Ethernet 2"):

```
Get-NetAdapter
```

*(admin)* Give it a static address on the dog's wired subnet. No gateway is
specified deliberately, so Wi-Fi remains the default route and the PC keeps
internet:

```
New-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 192.168.123.162 -PrefixLength 24
```

Verify, then check the dog answers:

```
Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress
```

```
ping 192.168.123.161
```

## H3. Firewall — required, and the most likely thing to trip you up

Windows blocks inbound UDP by default, so without this the PC receives nothing
and Unreal sits at `NO DATA` with no other symptom.

*(admin)* Allow the telemetry port on **all** profiles — the dog's network is
usually classified "Public", and a rule limited to Private will not apply:

```
New-NetFirewallRule -DisplayName "GO1 Telemetry" -Direction Inbound -Protocol UDP -LocalPort 9876 -Action Allow -Profile Any
```

Confirm it exists:

```
Get-NetFirewallRule -DisplayName "GO1 Telemetry"
```

Expect Windows to raise separate prompts for the UE **editor** and for a
**packaged build** — they are different executables. The port rule above covers
both; allow the prompt anyway if it appears.

## H4. SSH — one difference from macOS

Windows 10/11 include the OpenSSH client, so `ssh`, `scp` and `ssh-keygen` work
as on the Mac. But **`ssh-copy-id` does not exist on Windows.** Create the key,
then install it manually:

```
ssh-keygen -t ed25519 -N '""' -f $env:USERPROFILE\.ssh\id_go1
```

```
type $env:USERPROFILE\.ssh\id_go1.pub | ssh pi@192.168.123.161 "cat >> ~/.ssh/authorized_keys"
```

That prompts once for the dog's password (`123`). Afterwards:

```
ssh -i $env:USERPROFILE\.ssh\id_go1 pi@192.168.123.161
```

## H5. Daily run

Find the PC's address on whichever network reaches the dog:

```
ipconfig
```

Wired — the PC is `192.168.123.162`:

```
ssh -i $env:USERPROFILE\.ssh\id_go1 pi@192.168.123.161 'cd ~/go1_bridge && ./go1_remote_bridge 192.168.123.162 9876 100 192.168.123.161 8082 8092'
```

Wireless — join `Unitree_Go505540A` (password `00000000`), then substitute the
PC's `192.168.12.x` address as the first argument:

```
ssh -i $env:USERPROFILE\.ssh\id_go1 pi@192.168.12.1 'cd ~/go1_bridge && ./go1_remote_bridge 192.168.12.55 9876 100 192.168.123.161 8082 8092'
```

## H6. Diagnostics, Windows equivalents

| Task | macOS | Windows |
|---|---|---|
| What holds UDP 9876 | `lsof -nP -iUDP:9876` | `Get-NetUDPEndpoint -LocalPort 9876` |
| …then identify it | (shown) | `Get-Process -Id <OwningProcess>` |
| Own IP | `ipconfig getifaddr en0` | `ipconfig` |
| Reachability | `ping -c 3 <ip>` | `ping <ip>` |
| Test listener | `python3 listen.py` | `python listen.py` |
| Unbuffered listener | `python3 -u listen.py` | `python -u listen.py` |
| Revert adapter to DHCP | `networksetup -setdhcp …` | `Set-NetIPInterface -InterfaceAlias "Ethernet" -Dhcp Enabled` *(admin)* |

`netstat -ano | findstr :9876` also works if you prefer it, followed by
`tasklist /FI "PID eq <pid>"`.

## H7. Checklist when it doesn't work on the PC

In the order worth checking:

1. **Firewall rule missing or wrong profile** — by far the most common cause.
   The dog's network is usually "Public".
2. **Wrong destination IP** in argument 1 of the bridge command. The PC's
   address on the dog's network is not its usual LAN address.
3. **Something else holding UDP 9876** — `Run In Editor` left ticked, a stray
   `listen.py`, or a previous editor process.
4. **Bridge not running**, or a stale one still sending to the old Mac address —
   `pkill -f go1_remote_bridge` on the dog, then restart it.
5. **Python not on PATH** — `python` may need to be `py` on some installs.

Everything else — the robot endpoint, the local port, the 100 Hz rate, the
component settings, the button bits — is unchanged from the Mac setup.
