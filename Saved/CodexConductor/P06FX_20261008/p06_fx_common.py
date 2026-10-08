"""Shared fail-closed helpers for P06 FX editor tools; importable offline."""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import shutil

try:
    import unreal  # type: ignore
except ModuleNotFoundError:
    unreal = None


HERE = os.path.dirname(os.path.abspath(__file__))


def _load_defaults():
    path = os.path.join(HERE, "p06_fx_defaults.py")
    spec = importlib.util.spec_from_file_location("p06_fx_defaults", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = _load_defaults()


class ToolError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ToolError(str(message))


def stamp(prefix):
    return "%s-%s" % (prefix, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x" if exclusive else "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_id(value):
    if value is None:
        return None
    text = str(value.get_path_name()) if hasattr(value, "get_path_name") else str(value)
    return text.split(".", 1)[0]


def guid_text(value):
    if unreal is not None:
        try:
            return str(unreal.GuidLibrary.conv_guid_to_string(value)).replace("-", "").upper()
        except Exception:  # noqa: BLE001 - wrapper differs between builds
            pass
    text = str(value).replace("-", "").replace("{", "").replace("}", "").upper()
    return "".join(c for c in text if c in "0123456789ABCDEF")[-32:]


def census():
    require(unreal is not None, "UNREAL_REQUIRED")
    lib = unreal.EditorLoadingAndSavingUtils
    return {
        "content": sorted(asset_id(p) for p in lib.get_dirty_content_packages()),
        "maps": sorted(asset_id(p) for p in lib.get_dirty_map_packages()),
    }


def require_clean(label):
    got = census()
    require(got == {"content": [], "maps": []}, "%s_DIRTY|%s" % (label, json.dumps(got, sort_keys=True)))
    return got


def editor_guard():
    require(unreal is not None, "UNREAL_REQUIRED")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    world = editor.get_editor_world()
    require(world is not None, "EDITOR_WORLD_MISSING")
    require(asset_id(world) == D.EXPECTED_WORLD,
            "WRONG_WORLD|expected=%s|actual=%s" % (D.EXPECTED_WORLD, asset_id(world)))
    return editor, world


def project_dir():
    return os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def saved_here():
    return os.path.normpath(os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexConductor", "P06FX_20261008"))


def package_file(package_path):
    require(package_path.startswith("/Game/"), "PACKAGE_OUTSIDE_GAME|" + package_path)
    base = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()),
                        package_path[len("/Game/"):].replace("/", os.sep))
    for ext in (".uasset", ".umap"):
        if os.path.isfile(base + ext):
            return os.path.normpath(base + ext)
    return os.path.normpath(base + ".uasset")


def backup(prefix, run, packages, note):
    """Create and hash a narrow backup plus a prechange manifest before mutation."""
    root = os.path.join(project_dir(), "Backups", "%s-%s" % (prefix, run))
    os.makedirs(root, exist_ok=False)
    rows = []
    for package in packages:
        source = package_file(package)
        require(os.path.isfile(source), "BACKUP_SOURCE_MISSING|" + source)
        rel = package[len("/Game/"):].replace("/", os.sep) + os.path.splitext(source)[1]
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(source, dest)
        require(sha256(source) == sha256(dest), "BACKUP_HASH|" + package)
        rows.append({"package": package, "source": source, "backup": dest,
                     "bytes": os.path.getsize(source), "sha256": sha256(source)})
    manifest = {"run": run, "note": note, "packages": rows}
    write_json(os.path.join(root, "prechange.json"), manifest, exclusive=True)
    return {"root": root, "packages": rows}


def enum_member(enum_type, *names):
    for name in names:
        if hasattr(enum_type, name):
            return getattr(enum_type, name)
    raise ToolError("ENUM_MEMBER|%s|%s" % (enum_type, ",".join(names)))


def show_and_cues():
    show = unreal.load_asset(D.SHOW)
    require(show is not None, "SHOW_LOAD")
    return show, list(show.get_editor_property("cues"))


def cue_by_identity(cues, label, guid):
    hits = [(i, c) for i, c in enumerate(cues)
            if str(c.get_editor_property("label")) == label and guid_text(c.get_editor_property("cue_guid")) == guid]
    require(len(hits) == 1, "CUE_IDENTITY|%s|%s|count=%d" % (label, guid, len(hits)))
    return hits[0]


def p06_actor(show):
    actors = []
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if (actor.get_class().get_name() == "InfinityStagePassageActor"
                and str(actor.get_actor_label()).startswith("Passage 06")
                and actor.get_editor_property("show_asset") == show):
            actors.append(actor)
    require(len(actors) == 1, "P06_ACTOR_COUNT|%d" % len(actors))
    return actors[0]


def save_show_level():
    require(unreal.EditorAssetLibrary.save_asset(D.SHOW, only_if_is_dirty=False), "SAVE_SHOW")
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "SAVE_LEVEL")
    require_clean("POST_SAVE")


def archive_record(path, run):
    archived = path + ".reverted-" + run
    os.replace(path, archived)
    return archived


def actor_census(prefixes=("ZZ_", "TEMP")):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    return sorted(str(a.get_actor_label()) for a in subsystem.get_all_level_actors()
                  if str(a.get_actor_label()).upper().startswith(tuple(p.upper() for p in prefixes)))

