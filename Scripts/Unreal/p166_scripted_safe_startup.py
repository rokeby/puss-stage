"""Transient rendering limits for the opt-in ScriptedSafe editor profile.

The custom config runs :func:`install` only when the editor was started with
``-CustomConfig=ScriptedSafe``.  Values are captured before the limits are
applied, restored at BeginPIE, and re-applied at EndPIE.  Nothing here writes a
package or a config file.
"""
from __future__ import annotations

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "P166_SCRIPTED_SAFE"
SHOW_MAP = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SAFE_VALUES = {
    "r.Lumen.DiffuseIndirect.Allow": 0,
    "r.Lumen.Reflections.Allow": 0,
    "r.Lumen.HardwareRayTracing": 0,
    "r.DistanceFields.TextureUploadLimitKBytes": 1024,
    "fx.NiagaraAllowGPUParticles": 0,
    "fx.Niagara.QualityLevel": 0,
    "t.MaxFPS": 30,
}

_ORIGINAL_VALUES: dict[str, int] = {}
_INSTALLED = False


def _world():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return editor.get_game_world() or editor.get_editor_world()


def _get_int(name):
    return int(unreal.SystemLibrary.get_console_variable_int_value(name))


def _set_int(name, value):
    world = _world()
    if world is None:
        raise RuntimeError("WORLD_MISSING")
    unreal.SystemLibrary.execute_console_command(world, "%s %d" % (name, int(value)), None)
    readback = _get_int(name)
    if readback != int(value):
        raise RuntimeError("CVAR_READBACK_FAILED|%s|wanted=%d|got=%d" %
                           (name, int(value), readback))


def apply_values(values, reason):
    """Apply and read back a complete cvar set; pure mutation is mockable offline."""
    for name, value in values.items():
        _set_int(name, value)
    summary = ";".join("%s=%d" % (name, _get_int(name)) for name in values)
    unreal.log("%s_APPLIED|reason=%s|%s" % (MARK, reason, summary))
    return {name: _get_int(name) for name in values}


def apply_safe_settings(reason="manual"):
    """Apply the scripted-work limits and disable realtime level viewports."""
    result = apply_values(SAFE_VALUES, reason)
    level_editor = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    level_editor.editor_set_viewport_realtime(False)
    unreal.log("%s_VIEWPORT|reason=%s|realtime=false" % (MARK, reason))
    return result


def restore_show_settings(reason="manual"):
    """Restore values captured before safe mode, for PIE or a show-look still."""
    if not _ORIGINAL_VALUES:
        raise RuntimeError("ORIGINAL_VALUES_NOT_CAPTURED")
    return apply_values(_ORIGINAL_VALUES, reason)


def _pre_begin_pie(_is_simulating):
    try:
        restore_show_settings("pre-begin-pie")
    except Exception as exc:
        unreal.log_error("%s_PIE_RESTORE_FAILED|%r" % (MARK, exc))


def _end_pie(_is_simulating):
    try:
        apply_safe_settings("end-pie")
    except Exception as exc:
        unreal.log_error("%s_POST_PIE_REAPPLY_FAILED|%r" % (MARK, exc))


def install():
    """Capture project values, bind PIE guards, and enable safe editor mode."""
    global _INSTALLED
    if unreal is None:
        raise RuntimeError("UNREAL_UNAVAILABLE")
    if _INSTALLED:
        unreal.log("%s_ALREADY_INSTALLED" % MARK)
        return False

    _ORIGINAL_VALUES.clear()
    _ORIGINAL_VALUES.update((name, _get_int(name)) for name in SAFE_VALUES)
    unreal.EditorDelegates.pre_begin_pie.add_callable_unique(_pre_begin_pie)
    unreal.EditorDelegates.end_pie.add_callable_unique(_end_pie)
    _INSTALLED = True
    try:
        apply_safe_settings("editor-start")
    except Exception:
        _INSTALLED = False
        raise
    originals = ";".join("%s=%d" % item for item in _ORIGINAL_VALUES.items())
    unreal.log("%s_INSTALLED|pie_guard=true|startup_map=/Engine/Maps/Entry|originals=%s" %
               (MARK, originals))
    return True
