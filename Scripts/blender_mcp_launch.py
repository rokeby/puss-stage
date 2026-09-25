"""Open Blender with the MCP for Blender add-on enabled and its socket server started (TCP localhost:9876).

    "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --python Scripts/blender_mcp_launch.py [file.blend]

Claude connects through the `blender` MCP server (uvx blender-mcp), which talks to this socket.
"""
import bpy

try:
    bpy.ops.preferences.addon_enable(module="blender_mcp_addon")
    bpy.ops.wm.save_userpref()
except Exception as exc:  # noqa: BLE001
    print(f"BLENDER_MCP_ADDON_ENABLE_FAILED|{exc!r}")


def _start(_scene=None):
    try:
        bpy.ops.blendermcp.start_server()
        print(f"BLENDER_MCP_SERVER_STARTED|port={bpy.context.scene.blendermcp_port}")
    except Exception as exc:  # noqa: BLE001
        print(f"BLENDER_MCP_SERVER_START_FAILED|{exc!r}")
    return None


bpy.app.timers.register(_start, first_interval=1.0)
