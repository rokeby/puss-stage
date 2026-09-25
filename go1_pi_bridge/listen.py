#!/usr/bin/env python3
"""Phase-1 test listener. Run on the Mac while the bridge runs on the dog:

    python3 listen.py [port]

Prints a live line with the stick axes and buttons, warns on sequence gaps,
and shows packet age so you can eyeball latency/staleness. Ctrl-C to stop.
"""
import json
import socket
import sys
import time

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9876

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(1.0)
print(f"listening on udp 0.0.0.0:{PORT} ... (Ctrl-C to stop)")

last_seq = None
gaps = 0
count = 0
last_print = 0.0

while True:
    try:
        data, addr = sock.recvfrom(2048)
    except socket.timeout:
        print("  ... no packets in the last second")
        continue

    now = time.time()
    try:
        p = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print(f"  !! unparseable packet from {addr}: {data[:60]!r}")
        continue

    seq = p.get("seq", 0)
    if last_seq is not None:
        if seq <= last_seq:
            continue  # reordered/duplicate: drop silently, like UE will
        if seq != last_seq + 1:
            gaps += seq - last_seq - 1
    last_seq = seq
    count += 1

    if now - last_print >= 0.2:  # print at ~5 Hz so the terminal stays readable
        last_print = now
        print(
            f"seq={seq:8d} from={addr[0]} "
            f"lx={p['lx']:+.2f} ly={p['ly']:+.2f} rx={p['rx']:+.2f} ry={p['ry']:+.2f} "
            f"keys=0x{p.get('keys', 0):04x} lost={p.get('source_lost')} "
            f"gaps={gaps} rx_count={count}"
        )
