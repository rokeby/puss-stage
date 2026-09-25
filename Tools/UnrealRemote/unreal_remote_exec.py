#!/usr/bin/env python3
"""Execute one Python file in the loopback PussStage Unreal Editor.

The wire protocol is provided by Epic's UE 5.8 PythonScriptPlugin
``remote_execution.py`` module. This wrapper adds project filtering, absolute
file validation, bounded discovery and machine-readable terminal output.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time


ENGINE_REMOTE_MODULE = Path(
    "/Users/Shared/Epic Games/UE_5.8/Engine/Plugins/Experimental/"
    "PythonScriptPlugin/Content/Python/remote_execution.py"
)
PROJECT_NAME = "PussStage"
CLIENT_LOOPBACK = "127.0.0.1"


def load_epic_remote_module():
    if not ENGINE_REMOTE_MODULE.is_file():
        raise RuntimeError(f"Epic Remote Python module missing: {ENGINE_REMOTE_MODULE}")
    spec = importlib.util.spec_from_file_location("ue_remote_execution", ENGINE_REMOTE_MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load: {ENGINE_REMOTE_MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if sys.platform == "darwin":
        # Epic binds both Editor and client to the same concrete address/port.
        # On macOS, SO_REUSEPORT can hash multicast packets to only one of those
        # sockets. A wildcard receive bind plus explicit lo0 multicast
        # membership preserves loopback-only traffic and delivers discovery to
        # both peers.
        def init_broadcast_socket(connection):
            config = connection._config
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            if hasattr(socket, "SO_REUSEPORT"):
                udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            else:
                udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            udp.bind(("", config.multicast_group_endpoint[1]))
            udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, config.multicast_ttl)
            interface = socket.inet_aton(config.multicast_bind_address)
            udp.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface)
            udp.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(config.multicast_group_endpoint[0]) + interface,
            )
            udp.settimeout(0.1)
            connection._broadcast_socket = udp

        module._RemoteExecutionBroadcastConnection._init_broadcast_socket = (
            init_broadcast_socket
        )
    return module


def discover(remote, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = [
            node
            for node in remote.remote_nodes
            if node.get("project_name") == PROJECT_NAME
        ]
        if len(matches) > 1:
            raise RuntimeError(f"Multiple PussStage Remote Python nodes found: {matches}")
        if matches:
            return matches[0]
        time.sleep(0.1)
    raise RuntimeError("No loopback PussStage Unreal Python node discovered")


def execute(script_path: Path, timeout: float) -> tuple[dict, dict]:
    ue_remote = load_epic_remote_module()
    config = ue_remote.RemoteExecutionConfig()
    config.multicast_ttl = 0
    config.multicast_group_endpoint = ("239.0.0.1", 6766)
    config.multicast_bind_address = CLIENT_LOOPBACK
    config.command_endpoint = (CLIENT_LOOPBACK, 6776)
    remote = ue_remote.RemoteExecution(config)
    remote.start()
    try:
        node = discover(remote, timeout)
        remote.open_command_connection(node["node_id"])
        result = remote.run_command(
            str(script_path),
            unattended=True,
            exec_mode=ue_remote.MODE_EXEC_FILE,
            raise_on_failure=False,
        )
        return node, result
    finally:
        remote.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    script_path = args.script.expanduser().resolve()
    if not script_path.is_file():
        parser.error(f"Python file does not exist: {script_path}")
    node, result = execute(script_path, args.timeout)
    print("DISCOVERED", json.dumps(node, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"UNREAL_REMOTE_EXEC_ERROR|{type(exc).__name__}|{exc}", file=sys.stderr)
        raise
