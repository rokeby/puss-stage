#!/usr/bin/env python3
"""Minimal local client for Unreal PythonScriptPlugin remote execution.

Uses the protocol documented by UE 5.8's PythonScriptRemoteExecution.cpp.
It is deliberately project-local and only connects to a discovered PussStage
Editor node on the loopback multicast interface.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time
import uuid


GROUP = "239.0.0.1"
PORT = 6766
MAGIC = "ue_py"
VERSION = 1


def message(kind: str, source: str, dest: str | None = None, data=None) -> bytes:
    payload = {"version": VERSION, "magic": MAGIC, "type": kind, "source": source}
    if dest:
        payload["dest"] = dest
    if data is not None:
        payload["data"] = data
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def make_udp() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("127.0.0.1", PORT))
    membership = struct.pack("=4s4s", socket.inet_aton(GROUP), socket.inet_aton("127.0.0.1"))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("127.0.0.1"))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
    sock.settimeout(0.25)
    return sock


def discover(udp: socket.socket, source: str, timeout: float) -> tuple[str, dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        udp.sendto(message("ping", source), (GROUP, PORT))
        until = min(deadline, time.monotonic() + 0.35)
        while time.monotonic() < until:
            try:
                raw, _ = udp.recvfrom(65535)
            except socket.timeout:
                break
            packet = json.loads(raw.decode("utf-8"))
            if (
                packet.get("version") == VERSION
                and packet.get("magic") == MAGIC
                and packet.get("type") == "pong"
                and packet.get("dest") == source
                and packet.get("data", {}).get("project_name") == "PussStage"
            ):
                return packet["source"], packet["data"]
    raise RuntimeError("No PussStage Unreal Python remote-execution node discovered")


def recv_json(sock: socket.socket, timeout: float) -> dict:
    sock.settimeout(timeout)
    chunks: list[bytes] = []
    decoder = json.JSONDecoder()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            part = sock.recv(1024 * 1024)
        except socket.timeout:
            continue
        if not part:
            break
        chunks.append(part)
        text = b"".join(chunks).decode("utf-8")
        try:
            value, end = decoder.raw_decode(text)
        except json.JSONDecodeError:
            continue
        if not text[end:].strip():
            return value
    raise RuntimeError("Timed out waiting for complete Unreal command result")


def run(script_path: str, timeout: float) -> dict:
    source = str(uuid.uuid4())
    udp = make_udp()
    tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_server.bind(("127.0.0.1", 0))
    tcp_server.listen(1)
    tcp_server.settimeout(timeout)
    command_port = tcp_server.getsockname()[1]
    node, node_info = discover(udp, source, timeout)
    print("DISCOVERED", node, json.dumps(node_info, sort_keys=True))
    udp.sendto(
        message(
            "open_connection",
            source,
            node,
            {"command_ip": "127.0.0.1", "command_port": command_port},
        ),
        (GROUP, PORT),
    )
    command_sock, _ = tcp_server.accept()
    command_sock.sendall(
        message(
            "command",
            source,
            node,
            {"command": script_path, "unattended": True, "exec_mode": "ExecuteFile"},
        )
    )
    result = recv_json(command_sock, timeout)
    udp.sendto(message("close_connection", source, node), (GROUP, PORT))
    command_sock.close()
    tcp_server.close()
    udp.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    result = run(args.script, args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    data = result.get("data", {})
    if result.get("type") != "command_result" or not data.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
