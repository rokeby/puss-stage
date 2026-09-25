"""Run the guarded read-only Wing assignment audit through Unreal MCP."""

import json
import sys
import urllib.request


URL = "http://127.0.0.1:8000/mcp"


def decode_response(raw):
    text = raw.decode("utf-8")
    if not text.strip():
        return None
    if text.lstrip().startswith("{"):
        return json.loads(text)
    values = [
        json.loads(line[5:].strip())
        for line in text.splitlines()
        if line.startswith("data:")
    ]
    return values[-1] if values else {"raw": text}


def send(payload, session=None, timeout=45):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    request = urllib.request.Request(URL, json.dumps(payload).encode(), headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return decode_response(response.read()), response.headers.get("Mcp-Session-Id")


def call_script(session, relative_path):
    response, _ = send(
        {
            "jsonrpc": "2.0",
            "id": relative_path,
            "method": "tools/call",
            "params": {
                "name": "call_tool",
                "arguments": {
                    "toolset_name": "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset",
                    "tool_name": "ExecuteProjectPythonFile",
                    "arguments": {"relativeSavedPath": relative_path},
                },
            },
        },
        session,
    )
    if response and response.get("error"):
        raise RuntimeError(response["error"])
    result = (response or {}).get("result", {})
    if result.get("isError"):
        raise RuntimeError(result)
    for block in result.get("content", []):
        if block.get("type") != "text":
            continue
        try:
            returned = json.loads(block.get("text", "")).get("returnValue", {})
        except (ValueError, AttributeError):
            continue
        if returned.get("bSuccess") is False:
            raise RuntimeError(returned)
    print(json.dumps(response, indent=2))


initialized, session = send(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "PussStageWingHandednessAudit", "version": "1.0"},
        },
    }
)
if initialized and initialized.get("error"):
    raise RuntimeError(initialized["error"])
if not session:
    raise RuntimeError("MCP initialization returned no session id")
send({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)

tools_response, _ = send(
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session
)
tool_names = [
    item.get("name") for item in (tools_response or {}).get("result", {}).get("tools", [])
]
if "call_tool" not in tool_names or "list_toolsets" not in tool_names:
    raise RuntimeError(f"Expected MCP meta-tools are missing: {tool_names}")

scripts = sys.argv[1:] or [
    "CodexWingIntegration/remote_healthcheck.py",
    "CodexWingHandedness/audit_assigned_wings_readonly.py",
]
for script in scripts:
    call_script(session, script)
