"""Transient editor-only external-sky suppression for PussStage.

Installed by the held PythonScriptPlugin StartupScripts line in
``Scripts/patches/2026-10-08_P18_sky_autohide_startup.patch``.  The module
registers UE 5.8 LevelEditorSubsystem map delegates and defers each pass by one
Slate tick so newly streamed actors exist before they are inspected.

This never changes ``hidden``/``visible`` serialized properties.  It calls only
``Actor.set_is_temporarily_hidden_in_editor`` and verifies that the dirty-package
census is byte-for-byte unchanged.  PIE is explicitly ignored.

Off switches (either one):
  * environment variable ``PUSS_EDITOR_SKY_AUTOHIDE=0``;
  * file ``Saved/CodexConductor/disable_p18_sky_autohide.flag``.
"""
from __future__ import annotations

import os

try:
    import unreal  # type: ignore
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "P18_EDITOR_SKY_AUTOHIDE"
ENV_SWITCH = "PUSS_EDITOR_SKY_AUTOHIDE"
FLAG_RELATIVE = os.path.join("Saved", "CodexConductor", "disable_p18_sky_autohide.flag")
FALSE_VALUES = {"0", "false", "off", "no", "disabled"}

_LEVEL_EDITOR = None
_TICK_HANDLE = None
_WATCH_HANDLE = None
_WATCH_ACCUMULATOR = 0.0
_LAST_LEVELS = None
_PENDING_REASONS: set[str] = set()
_INSTALLED = False


def switch_enabled(environ=None, flag_exists=False):
    """Pure policy helper used by the offline positive/negative controls."""
    env = os.environ if environ is None else environ
    return str(env.get(ENV_SWITCH, "1")).strip().lower() not in FALSE_VALUES and not bool(flag_exists)


def classify_actor(class_name, package_name, persistent_package):
    """Return the declared suppression reason, or ``None``.

    A DirectionalLight is external only when it belongs to a streamed package;
    the persistent-level P06 sunset therefore remains visible in the editor.
    """
    cls = str(class_name)
    folded = cls.lower().replace("_", "")
    if cls == "SkyLight":
        return "skylight"
    if cls == "SkyAtmosphere":
        return "atmosphere"
    if "VolumetricCloud" in cls:
        return "cloud"
    if "skysphere" in folded:
        return "sky-sphere"
    if cls == "DirectionalLight" and str(package_name) != str(persistent_package):
        return "streamed-sun"
    return None


def _project_dir():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def _flag_path():
    return os.path.join(_project_dir(), FLAG_RELATIVE)


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
        "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages()),
    }


def _actor_reason(actor, persistent_package):
    return classify_actor(actor.get_class().get_name(), actor.get_outermost().get_name(), persistent_package)


def hide_now(reason="manual"):
    """Run one transient pass.  Returns a small read-back report."""
    if unreal is None:
        raise RuntimeError("UNREAL_UNAVAILABLE")
    if not switch_enabled(flag_exists=os.path.isfile(_flag_path())):
        report = {"reason": reason, "disabled": True, "hidden": []}
        unreal.log("%s_DISABLED|reason=%s" % (MARK, reason))
        return report

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        report = {"reason": reason, "pie_ignored": True, "hidden": []}
        unreal.log("%s_PIE_IGNORED|reason=%s" % (MARK, reason))
        return report
    world = editor.get_editor_world()
    if world is None:
        raise RuntimeError("EDITOR_WORLD_MISSING")

    before = _census()
    persistent = str(world.get_outermost().get_name())
    hidden = []
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
        why = _actor_reason(actor, persistent)
        if why is None:
            continue
        actor.set_is_temporarily_hidden_in_editor(True)
        hidden.append({
            "label": str(actor.get_actor_label()),
            "class": str(actor.get_class().get_name()),
            "package": str(actor.get_outermost().get_name()),
            "reason": why,
            "readback": bool(actor.is_temporarily_hidden_in_editor()),
        })
    bad = [row["label"] for row in hidden if not row["readback"]]
    after = _census()
    if bad or before != after:
        raise RuntimeError("READBACK_OR_DIRTIED|bad=%s|before=%s|after=%s" % (bad, before, after))
    report = {"reason": reason, "disabled": False, "persistent": persistent, "hidden": hidden,
              "census_before": before, "census_after": after}
    unreal.log("%s_OK|reason=%s|n=%d|census_unchanged=true|%s" %
               (MARK, reason, len(hidden), ";".join(row["label"] for row in hidden)))
    return report


def _on_tick(_delta_seconds):
    global _TICK_HANDLE
    handle, _TICK_HANDLE = _TICK_HANDLE, None
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
    reasons = sorted(_PENDING_REASONS) or ["deferred"]
    _PENDING_REASONS.clear()
    try:
        hide_now("+".join(reasons))
    except Exception as exc:  # Startup must not take down the editor.
        unreal.log_error("%s_FAILED|reason=%s|%r" % (MARK, "+".join(reasons), exc))


def queue_pass(reason, *_unused):
    """Delegate callback: coalesce events and run after the load event settles."""
    global _TICK_HANDLE
    _PENDING_REASONS.add(str(reason))
    if _TICK_HANDLE is None:
        _TICK_HANDLE = unreal.register_slate_post_tick_callback(_on_tick)


def _map_opened(_filename, _as_template):
    queue_pass("map-opened")


def _map_changed(_flags):
    # ULevelEditorSubsystem owns an OnLevelAddedOrRemoved handler in UE 5.8;
    # this dynamic MapChanged delegate is the Python-visible route.
    queue_pass("map-or-stream-change")


def _loaded_level_signature():
    """Current editor level packages; the watcher is a fallback for streamed loads."""
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    if editor.get_game_world() is not None:
        return None
    world = editor.get_editor_world()
    if world is None:
        return None
    names = []
    for level in unreal.EditorLevelUtils.get_levels(world):
        outer = level.get_outer()
        names.append(str(outer.get_name()) if outer is not None else str(level.get_name()))
    return tuple(sorted(names))


def _watch_levels(delta_seconds):
    """Low-cost 0.5 s fallback: queue a pass when the loaded level set changes."""
    global _WATCH_ACCUMULATOR, _LAST_LEVELS
    _WATCH_ACCUMULATOR += float(delta_seconds)
    if _WATCH_ACCUMULATOR < 0.5:
        return
    _WATCH_ACCUMULATOR = 0.0
    signature = _loaded_level_signature()
    if signature is None:
        return
    if _LAST_LEVELS is None:
        _LAST_LEVELS = signature
    elif signature != _LAST_LEVELS:
        _LAST_LEVELS = signature
        queue_pass("streamed-level-set-changed")


def install():
    """Idempotently install startup, map-open and streamed-level coverage."""
    global _LEVEL_EDITOR, _WATCH_HANDLE, _LAST_LEVELS, _INSTALLED
    if unreal is None:
        raise RuntimeError("UNREAL_UNAVAILABLE")
    if _INSTALLED:
        unreal.log("%s_ALREADY_INSTALLED" % MARK)
        return False
    if not switch_enabled(flag_exists=os.path.isfile(_flag_path())):
        unreal.log("%s_DISABLED_AT_STARTUP" % MARK)
        return False
    _LEVEL_EDITOR = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    _LEVEL_EDITOR.on_map_opened.add_callable_unique(_map_opened)
    _LEVEL_EDITOR.on_map_changed.add_callable_unique(_map_changed)
    _LAST_LEVELS = _loaded_level_signature()
    _WATCH_HANDLE = unreal.register_slate_post_tick_callback(_watch_levels)
    _INSTALLED = True
    queue_pass("editor-start")
    unreal.log("%s_INSTALLED|map_opened=true|map_changed=true|level_watcher=true|transient=true" % MARK)
    return True
