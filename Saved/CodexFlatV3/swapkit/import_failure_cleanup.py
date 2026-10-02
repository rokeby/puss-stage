"""Fail-closed cleanup for packages created by one Flat V3 import run.

This module never saves.  It only discards packages that were both absent on
disk and unloaded at the run snapshot, then observed loaded by this run.
"""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]
import json
import os

import unreal


def package_disk_filename(package_path):
    if not str(package_path).startswith("/Game/"):
        raise RuntimeError("CLEANUP_NON_GAME_PACKAGE|path=" + str(package_path))
    content = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir())
    relative = str(package_path)[len("/Game/"):].replace("/", os.sep)
    return os.path.normpath(os.path.join(content, relative + ".uasset"))


def package_exists_on_disk(package_path):
    return os.path.isfile(package_disk_filename(package_path))


def _object_path(package_path):
    return "%s.%s" % (package_path, str(package_path).rsplit("/", 1)[-1])


def _find_loaded_asset(package_path):
    return unreal.find_object(None, _object_path(package_path))


def _normalise_reference(value):
    return str(value).split(".", 1)[0]


def _delete_rank(path):
    if "/StaticMeshes/" in path:
        return 0
    if "/Materials/" in path or "/MaterialInstances/" in path:
        return 1
    if "/Textures/" in path:
        return 2
    return 3


class ImportRunTracker:
    """Snapshot prospective paths and own only packages created after it."""

    def __init__(self, slot, planned_paths, pre_import_census, census_fn):
        self.slot = str(slot)
        self.planned_paths = sorted(set(str(path) for path in planned_paths))
        self.pre_import_census = {
            "content": sorted(pre_import_census.get("content", [])),
            "maps": sorted(pre_import_census.get("maps", [])),
        }
        self.census_fn = census_fn
        self.eligible_absent_unloaded = []
        self.excluded_at_start = {}
        self.created = set()
        for path in self.planned_paths:
            reasons = []
            if package_exists_on_disk(path):
                reasons.append("ON_DISK")
            if _find_loaded_asset(path) is not None:
                reasons.append("LOADED")
            if reasons:
                self.excluded_at_start[path] = reasons
            else:
                self.eligible_absent_unloaded.append(path)

    def start_report(self):
        return {
            "pre_import_census": self.pre_import_census,
            "eligible_absent_unloaded": list(self.eligible_absent_unloaded),
            "excluded_at_start": dict(self.excluded_at_start),
        }

    def observe_created(self):
        """Discover partial creations without loading any prospective asset."""
        for path in self.eligible_absent_unloaded:
            asset = _find_loaded_asset(path)
            if asset is not None:
                package = str(asset.get_outermost().get_name()).split(".", 1)[0]
                if package != path:
                    raise RuntimeError("CLEANUP_CREATED_PACKAGE_MISMATCH|path=%s|package=%s" %
                                       (path, package))
                self.created.add(path)
        return sorted(self.created)

    def defer_legacy_cleanup(self, _paths):
        """Replace per-asset deletion; the outer failure boundary owns cleanup."""
        self.observe_created()
        return []

    def install_deferred_cleanup(self, slot_a_module):
        slot_a_module.delete_unsaved_created = self.defer_legacy_cleanup

    def _external_referencers(self, path):
        refs = {
            _normalise_reference(value)
            for value in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)
        }
        return sorted(ref for ref in refs if ref not in self.created)

    def cleanup(self):
        """Discard the exact run-created set or fail before unsafe deletion."""
        self.observe_created()
        current = self.census_fn()
        pre_content = set(self.pre_import_census["content"])
        pre_maps = set(self.pre_import_census["maps"])
        new_dirty = set(current["content"]) - pre_content
        new_maps = set(current["maps"]) - pre_maps
        untracked_dirty = sorted(new_dirty - self.created)
        if new_maps:
            raise RuntimeError("CLEANUP_NEW_DIRTY_MAPS|paths=" + json.dumps(sorted(new_maps)))
        if untracked_dirty:
            on_disk = sorted(path for path in untracked_dirty if package_exists_on_disk(path))
            marker = "CLEANUP_ON_DISK" if on_disk else "CLEANUP_UNTRACKED_DIRTY"
            raise RuntimeError("%s|paths=%s|on_disk=%s" %
                               (marker, json.dumps(untracked_dirty), json.dumps(on_disk)))

        loaded_created = sorted(path for path in self.created
                                if _find_loaded_asset(path) is not None)
        appeared_on_disk = sorted(path for path in loaded_created if package_exists_on_disk(path))
        if appeared_on_disk:
            raise RuntimeError("CLEANUP_ON_DISK|paths=" + json.dumps(appeared_on_disk))

        external = {}
        for path in loaded_created:
            refs = self._external_referencers(path)
            if refs:
                external[path] = refs
        if external:
            raise RuntimeError("CLEANUP_EXTERNAL_REFERENCER|refs=" +
                               json.dumps(external, sort_keys=True))

        deleted = []
        order = sorted(loaded_created, key=lambda path: (_delete_rank(path), path))
        for path in order:
            # Re-check both safety properties immediately before each mutation.
            if package_exists_on_disk(path):
                raise RuntimeError("CLEANUP_ON_DISK|path=" + path)
            refs = self._external_referencers(path)
            if refs:
                raise RuntimeError("CLEANUP_EXTERNAL_REFERENCER|path=%s|refs=%s" %
                                   (path, json.dumps(refs)))
            asset = _find_loaded_asset(path)
            if asset is None:
                raise RuntimeError("CLEANUP_CREATED_NOT_LOADED|path=" + path)
            if not unreal.EditorAssetLibrary.delete_loaded_asset(asset):
                raise RuntimeError("CLEANUP_DELETE_FAIL|path=" + path)
            if (_find_loaded_asset(path) is not None or
                    unreal.EditorAssetLibrary.does_asset_exist(path)):
                raise RuntimeError("CLEANUP_DELETE_READBACK_FAIL|path=" + path)
            deleted.append(path)

        after = self.census_fn()
        if after != self.pre_import_census:
            raise RuntimeError("CLEANUP_CENSUS_MISMATCH|expected=%s|actual=%s" %
                               (json.dumps(self.pre_import_census, sort_keys=True),
                                json.dumps(after, sort_keys=True)))
        remaining_loaded = sorted(path for path in self.created
                                  if (not package_exists_on_disk(path) and
                                      _find_loaded_asset(path) is not None))
        if remaining_loaded:
            raise RuntimeError("CLEANUP_CREATED_REMAINING|paths=" +
                               json.dumps(remaining_loaded))
        return {
            "status": "CLEAN",
            "created": sorted(self.created),
            "deleted": deleted,
            "delete_order": order,
            "census": after,
        }


def cleanup_after_failure(slot, run, tracker, census_fn):
    if tracker is None:
        return ({"status": "NOT_REQUIRED", "created": [], "deleted": [],
                 "census": census_fn()}, None)
    try:
        return tracker.cleanup(), None
    except Exception as exc:
        remaining = census_fn()
        result = {
            "status": "FAIL",
            "reason": str(exc),
            "created": sorted(tracker.created),
            "remaining_dirty": remaining,
        }
        unreal.log_error("FLATV3_%s_IMPORT_CLEANUP_FAIL run=%s reason=%s remaining_dirty=%s" %
                         (slot, run, str(exc).replace("\n", "\\n"),
                          json.dumps(remaining, separators=(",", ":"), sort_keys=True)))
        return result, exc
