# go1_pi_bridge

Dog-side bridge for GO1 remote → UE5 telemetry, plus the Mac test listener.

- `go1_remote_bridge.cpp` — runs on the GO1's internal head Pi. Reads the
  handheld remote via the Unitree Legged SDK and sends JSON UDP packets
  (protocol v1) to the UE host. Built inside a copy of `unitree_legged_sdk`
  on the Pi itself.
- `listen.py` — run on the Mac to verify packets before involving Unreal:
  `python3 listen.py [port]`.

Full step-by-step setup (SSH, SDK download, build, test, UE wiring):
see [`../Docs/Go1TelemetrySetup.md`](../Docs/Go1TelemetrySetup.md).

Quick reference (verified working, firmware 1.3.8, Ethernet path):

```
# Mac: SSH to the dog
ssh -i ~/.ssh/id_go1 pi@192.168.123.161

# Dog: run the bridge (Mac is 192.168.123.162 over Ethernet)
cd ~/go1_bridge && ./go1_remote_bridge 192.168.123.162 9876 50 192.168.123.161 8082 8092
```

Args: `<ue_host_ip> <ue_port> <rate_hz> <robot_ip> <robot_port> <local_port>`.

## Wireless card (offline reference)

On the dog's own hotspot — **no internet on the Mac**, so no Claude access
unless an iPhone is tethered over USB for internet at the same time.

1. Join Wi-Fi `Unitree_Go505540A`, password `00000000` (5 GHz, ch 165).
   macOS may silently hop back to a network that has internet — turn Auto-Join
   off on the usual network if that happens.
2. Confirm the Mac's address: `ipconfig getifaddr en0` (was `192.168.12.71`).
3. Run, substituting that address if it changed:

```
ssh -i ~/.ssh/id_go1 pi@192.168.12.1 'cd ~/go1_bridge && ./go1_remote_bridge 192.168.12.71 9876 100 192.168.123.161 8082 8092'
```

Only the Mac's IP and the SSH host change versus Ethernet. The robot endpoint
`192.168.123.161 8082` is internal to the dog and never changes. Unreal needs
no change; it binds `0.0.0.0`.

Troubleshooting offline:
- `NO DATA` in UE → bridge not running, or wrong Mac IP in argument 1.
- `lost=1` in bridge stats → wrong robot endpoint (must be `.161 8082`).
- `Bind client ip&port failed` → local port busy; try 8091/8095/8099.
- Only one thing can hold UDP 9876: untick `Run In Editor` before using PIE.
- Watch `gaps` in `listen.py` on Wi-Fi; steadily climbing means radio trouble.

Two hard-won details: robot state comes from the sport service at
`192.168.123.161:8082` (the control board at `.10:8007` never replies on this
firmware), and the local port must be free — the SDK only warns on bind
failure, then silently receives nothing.

Packet format (JSON v1):
`{"v":1,"seq":123,"t":<ms>,"lx":…,"ly":…,"rx":…,"ry":…,"keys":<bitmask>,"source_lost":false}`

Button bit order (bit 0 → 15): R1, L1, Start, Select, R2, L2, F1, F2,
A, B, X, Y, Up, Right, Down, Left.

The UE-side receiver lives in `Plugins/Go1Input/` (component:
`Go1 Remote Receiver`).
