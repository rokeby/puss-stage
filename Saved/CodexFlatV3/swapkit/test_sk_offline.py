#!/usr/bin/env python3
"""Offline fake-Unreal harness for slot SK positive and negative controls."""

from __future__ import annotations

import ast
import json
import sys
import types
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class EnumValue(str):
    pass


class FakePackage:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class FakeTexture:
    def __init__(self, path, width=1024, height=2048):
        self.path = path
        self.width = width
        self.height = height
        self.properties = {
            "mip_gen_settings": EnumValue("TMGS_FROM_TEXTURE_GROUP"),
            "flip_green_channel": False,
            "srgb": False,
            "compression_settings": EnumValue("TC_DEFAULT"),
            "lod_group": EnumValue("TEXTUREGROUP_World"),
            "never_stream": False,
            "virtual_texture_streaming": False,
        }

    def modify(self):
        return True

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def get_editor_property(self, name):
        return self.properties[name]

    def blueprint_get_size_x(self):
        return self.width

    def blueprint_get_size_y(self):
        return self.height

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[-1]

    def get_outermost(self):
        return FakePackage(self.path)


class FakeMaterialInstance:
    def __init__(self, path, textures):
        self.path = path
        self.textures = dict(textures)


class FakeEditorAssetLibrary:
    loaded = {}
    dirty = set()

    @classmethod
    def load_asset(cls, path):
        return cls.loaded.get(path)

    @classmethod
    def does_asset_exist(cls, path):
        return path in cls.loaded

    @classmethod
    def find_package_referencers_for_asset(cls, _path, _load):
        return []

    @classmethod
    def delete_loaded_asset(cls, asset):
        cls.loaded.pop(asset.path, None)
        cls.dirty.discard(asset.path)
        return True


def fake_unreal_module():
    unreal = types.ModuleType("unreal")
    unreal.Texture2D = FakeTexture
    unreal.MaterialInstanceConstant = FakeMaterialInstance
    unreal.TextureMipGenSettings = types.SimpleNamespace(
        TMGS_FROM_TEXTURE_GROUP=EnumValue("TMGS_FROM_TEXTURE_GROUP"),
        TMGS_NO_MIPMAPS=EnumValue("TMGS_NO_MIPMAPS"),
    )
    unreal.TextureCompressionSettings = types.SimpleNamespace(
        TC_DEFAULT=EnumValue("TC_DEFAULT"),
        TC_MASKS=EnumValue("TC_MASKS"),
        TC_NORMALMAP=EnumValue("TC_NORMALMAP"),
    )
    unreal.EditorAssetLibrary = FakeEditorAssetLibrary
    unreal.Paths = types.SimpleNamespace(
        project_content_dir=lambda: str(ROOT / "Content"),
        project_dir=lambda: str(ROOT),
        project_saved_dir=lambda: str(ROOT / "Saved"),
        convert_relative_path_to_full=lambda value: str(value),
    )
    unreal.find_object = lambda _outer, object_path: FakeEditorAssetLibrary.loaded.get(
        object_path.split(".", 1)[0]
    )
    unreal.log = lambda *_args: None
    unreal.log_error = lambda *_args: None
    unreal.SystemLibrary = types.SimpleNamespace(collect_garbage=lambda: None)
    return unreal


def expect_failure(callable_value, marker):
    try:
        callable_value()
    except Exception as exc:
        if marker not in str(exc):
            raise RuntimeError("WRONG_FAILURE|wanted=%s|actual=%s" % (marker, exc))
        return str(exc)
    raise RuntimeError("NEGATIVE_CONTROL_DID_NOT_FAIL|wanted=" + marker)


def assert_no_reload_calls(paths):
    failures = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name and "reload" in name.lower():
                failures.append("%s:%d:%s" % (path.name, node.lineno, name))
    if failures:
        raise RuntimeError("OFFLINE_RELOAD_CALL_FORBIDDEN|" + json.dumps(failures))
    return [path.name for path in paths]


def simulate_apply(c, sk_apply, cfg, fail_passage=None):
    instances = {
        row["mi"]: FakeMaterialInstance(row["mi"], row["old_textures"])
        for row in cfg["rows"]
    }
    dirty = set()
    saved_events = []
    logs = []
    releases = []
    calls = []
    garbage_collections = []
    state = {"passage": None, "new_sets": 0}

    patch_names = [
        "assert_context", "require_marker", "require_token_unused",
        "require_run_unused", "require_run_open", "require_batch_marker",
        "verify_texture_pair",
        "load_asset", "assert_mi", "set_mi_textures", "census", "save_exact",
        "write_report", "release",
    ]
    originals = {name: getattr(c, name) for name in patch_names}
    original_log = sk_apply.unreal.log
    original_collect = sk_apply.unreal.SystemLibrary.collect_garbage

    def fake_assert_mi(instance, expected, label):
        actual = {kind: instance.textures.get(kind) for kind in c.KINDS}
        return c.assert_texture_map(actual, expected, label)

    def fake_set_mi(instance, textures):
        is_new = any(str(value).endswith("_o2") for value in textures.values())
        if is_new and state["passage"] == fail_passage:
            state["new_sets"] += 1
            if state["new_sets"] == 2:
                raise RuntimeError("INJECTED_BATCH3_FAILURE")
        instance.textures = dict(textures)
        dirty.add(instance.path)

    def fake_save(paths):
        values = sorted(set(paths))
        if sorted(dirty) != values:
            raise RuntimeError(
                "OFFLINE_SAVE_DIRTY_MISMATCH|dirty=%s|paths=%s"
                % (sorted(dirty), values)
            )
        saved_events.append({"passage": state["passage"], "paths": values})
        dirty.clear()
        return values

    try:
        c.assert_context = lambda clean=True: (None, None)
        c.require_marker = lambda marker, run: {"marker": marker, "run": run}
        c.require_token_unused = lambda token: {"unused": token}
        c.require_run_unused = lambda run: {"unused_run": run}
        c.require_run_open = lambda run: {"open_run": run}
        c.require_batch_marker = lambda run, passage: {
            "run": run, "passage": passage
        }
        c.verify_texture_pair = lambda original, replacement, kind: {
            "old": original, "new": replacement, "kind": kind
        }
        c.load_asset = lambda path, expected_type=None: instances.get(path, FakeTexture(path))
        c.assert_mi = fake_assert_mi
        c.set_mi_textures = fake_set_mi
        c.census = lambda: {"content": sorted(dirty), "maps": []}
        c.save_exact = fake_save
        c.write_report = lambda name, value: str(HERE / name)
        c.release = lambda run, status, saved, phase, reason=None: releases.append({
            "run": run, "status": status, "saved": list(saved), "phase": phase
        })
        sk_apply.unreal.log = lambda message: logs.append(str(message))
        sk_apply.unreal.SystemLibrary.collect_garbage = (
            lambda: garbage_collections.append(state["passage"])
        )

        failure = None
        for passage in c.PASSAGES:
            state["passage"] = passage
            state["new_sets"] = 0
            calls.append(passage)
            try:
                sk_apply.main(passage)
            except Exception as exc:
                failure = str(exc)
                break
        return {
            "instances": instances,
            "saved_events": saved_events,
            "logs": logs,
            "releases": releases,
            "calls": calls,
            "garbage_collections": garbage_collections,
            "failure": failure,
        }
    finally:
        for name, value in originals.items():
            setattr(c, name, value)
        sk_apply.unreal.log = original_log
        sk_apply.unreal.SystemLibrary.collect_garbage = original_collect


def main() -> int:
    sys.modules["unreal"] = fake_unreal_module()
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import sk_common as c
    import sk_apply

    cfg = c.config()
    mapping = c.planned_textures(cfg)
    missing_sources = sorted(source for source, _kind in mapping.values()
                             if not Path(source).is_file())
    if missing_sources:
        raise RuntimeError("OFFLINE_SOURCE_MISSING|" + json.dumps(missing_sources))
    if any("skin_v3" not in Path(source).parts for source, _kind in mapping.values()):
        raise RuntimeError("OFFLINE_SOURCE_NOT_SKIN_V3")

    results = {}

    saved_profiles = {}
    mismatches = []
    for row in cfg["rows"]:
        for kind in c.KINDS:
            replacement = row["new_textures"][kind]
            if replacement in saved_profiles:
                continue
            original = row["old_textures"][kind]
            old_profile = c.saved_texture_profile(original)
            new_profile = c.saved_texture_profile(replacement)
            saved_profiles[replacement] = {
                "old": original, "kind": kind,
                "old_profile": old_profile, "new_profile": new_profile,
            }
            if old_profile != new_profile:
                mismatches.append(replacement)
    if len(saved_profiles) != 189 or mismatches:
        raise RuntimeError(
            "OFFLINE_SAVED_TEXTURE_AUDIT_FAIL|count=%d|mismatches=%s"
            % (len(saved_profiles), json.dumps(mismatches))
        )
    profile_counts = {}
    for value in saved_profiles.values():
        key = json.dumps(value["new_profile"], sort_keys=True)
        profile_counts[key] = profile_counts.get(key, 0) + 1
    results["saved_texture_settings_match_originals"] = {
        "status": "PASS", "pairs": len(saved_profiles),
        "mismatches": 0, "profile_counts": profile_counts,
        "settings_fix_required": False,
    }

    positive = {}
    for kind in c.KINDS:
        texture = FakeTexture("/Game/Fake/T_" + kind)
        positive[kind] = c.texture_settings(texture, kind)
    results["positive_texture_settings"] = {"status": "PASS", "readback": positive}

    mask = FakeTexture("/Game/Fake/T_SkinMask")
    c.texture_settings(mask, "SkinMask")
    mask.set_editor_property("srgb", True)
    failure = expect_failure(lambda: c.verify_texture(mask, "SkinMask"),
                             "TEXTURE_SETTINGS_FAIL")
    results["negative_mask_srgb"] = {"status": "PASS", "failure": failure}

    first = cfg["rows"][0]
    failure = expect_failure(
        lambda: c.assert_texture_map(first["old_textures"], first["new_textures"],
                                     "offline_old_after_apply"),
        "MI_TEXTURE_READBACK_FAIL",
    )
    results["negative_old_mi_readback"] = {"status": "PASS", "failure": failure}

    planned = ["/Game/Fake/Import/A", "/Game/Fake/Import/B", "/Game/Fake/Import/C"]
    c.cleanup_mod.package_exists_on_disk = lambda _path: False
    tracker = c.cleanup_mod.ImportRunTracker(
        "SK_OFFLINE", planned, {"content": [], "maps": []},
        lambda: {"content": sorted(FakeEditorAssetLibrary.dirty), "maps": []},
    )
    for path in planned[:2]:
        FakeEditorAssetLibrary.loaded[path] = FakeTexture(path)
        FakeEditorAssetLibrary.dirty.add(path)
    created = tracker.observe_created()
    cleanup = tracker.cleanup()
    if created != planned[:2] or cleanup["deleted"] != planned[:2]:
        raise RuntimeError("OFFLINE_EXACT_CLEANUP_FAIL")
    results["negative_import_failure_after_two"] = {
        "status": "PASS", "injected_failure": "after_two",
        "created": created, "deleted": cleanup["deleted"],
    }

    import sk_import
    failure = expect_failure(lambda: sk_import.main(), "SK_IMPORT_ALREADY_COMPLETE")
    results["completed_import_is_locked"] = {
        "status": "PASS", "failure": failure,
        "import_run_id": cfg["import_run_id"],
    }

    positive_apply = simulate_apply(c, sk_apply, cfg)
    batch_markers = [
        line for line in positive_apply["logs"]
        if line.startswith("FLATV3_SK_APPLY_BATCH_OK passage=")
    ]
    if (positive_apply["failure"] is not None or
            positive_apply["calls"] != list(c.PASSAGES) or
            len(positive_apply["saved_events"]) != 6 or
            len(batch_markers) != 6 or
            positive_apply["garbage_collections"] != list(c.PASSAGES) or
            positive_apply["releases"]):
        raise RuntimeError(
            "OFFLINE_SIX_BATCH_POSITIVE_FAIL|" + json.dumps({
                key: value for key, value in positive_apply.items()
                if key != "instances"
            }, sort_keys=True)
        )
    for row in cfg["rows"]:
        c.assert_texture_map(
            positive_apply["instances"][row["mi"]].textures,
            row["new_textures"], row["mi"] + ":positive_final",
        )
    results["positive_six_apply_batches"] = {
        "status": "PASS", "calls": positive_apply["calls"],
        "batch_markers": len(batch_markers),
        "saved_batches": len(positive_apply["saved_events"]),
        "garbage_collections": len(positive_apply["garbage_collections"]),
        "success_release_before_verify": False,
    }

    negative_apply = simulate_apply(c, sk_apply, cfg, fail_passage="P03")
    if ("INJECTED_BATCH3_FAILURE" not in str(negative_apply["failure"]) or
            negative_apply["calls"] != ["P01", "P02", "P03"] or
            len(negative_apply["releases"]) != 1 or
            negative_apply["releases"][0]["status"] != "FAIL_REVERTED"):
        raise RuntimeError(
            "OFFLINE_BATCH3_STOP_FAIL|" + json.dumps({
                key: value for key, value in negative_apply.items()
                if key != "instances"
            }, sort_keys=True)
        )
    for row in cfg["rows"]:
        expected = (row["new_textures"] if row["passage"] in ("P01", "P02")
                    else row["old_textures"])
        c.assert_texture_map(
            negative_apply["instances"][row["mi"]].textures,
            expected, row["mi"] + ":negative_final",
        )
    results["negative_batch3_failure_retains_1_2_and_stops"] = {
        "status": "PASS", "calls": negative_apply["calls"],
        "retained_passages": ["P01", "P02"],
        "failed_batch_reverted": "P03",
        "later_batches_called": False,
        "release_status": negative_apply["releases"][0]["status"],
    }

    entry_scripts = ["sk_import.py", "sk_apply.py", "sk_verify.py", "sk_revert.py"]
    missing_purge = [name for name in entry_scripts
                     if "_fv3_sys.modules" not in (HERE / name).read_text(encoding="utf-8")]
    if missing_purge:
        raise RuntimeError("OFFLINE_STALE_PURGE_MISSING|" + json.dumps(missing_purge))
    results["entry_stale_module_purge"] = {"status": "PASS", "scripts": entry_scripts}

    batch_entries = [HERE / ("sk_apply_%s.py" % passage.lower()) for passage in c.PASSAGES]
    bad_entries = [
        path.name for path, passage in zip(batch_entries, c.PASSAGES)
        if (not path.is_file() or "runpy.run_path" not in path.read_text(encoding="utf-8")
            or ('"FLATV3_PASSAGE": "%s"' % passage)
            not in path.read_text(encoding="utf-8"))
    ]
    if bad_entries:
        raise RuntimeError("OFFLINE_BATCH_ENTRY_FAIL|" + json.dumps(bad_entries))
    results["six_fixed_passage_entries"] = {
        "status": "PASS", "scripts": [path.name for path in batch_entries]
    }

    no_reload_paths = [HERE / "sk_apply.py", HERE / "sk_revert.py"] + batch_entries
    results["negative_reload_call_static_guard"] = {
        "status": "PASS", "scanned": assert_no_reload_calls(no_reload_paths),
        "rule": "any call whose function name contains reload fails",
    }
    apply_source = (HERE / "sk_apply.py").read_text(encoding="utf-8")
    verify_source = (HERE / "sk_verify.py").read_text(encoding="utf-8")
    if 'if final_status != "OK":' not in apply_source or \
            'c.release(run, status, [], "verify"' not in verify_source:
        raise RuntimeError("OFFLINE_TERMINAL_RELEASE_CONTRACT_FAIL")
    results["verify_is_terminal_release"] = {
        "status": "PASS", "apply_success_releases": False,
        "verify_success_releases": True,
    }

    report = {
        "schema_version": 1,
        "status": "PASS",
        "execution": {"offline": True, "unreal": False, "fake_unreal": True,
                      "mcp": False, "port_8010": False},
        "config": {
            "import_run_id": cfg["import_run_id"],
            "apply_run_id": cfg["apply_run_id"],
            "revert_run_id": cfg["revert_run_id"],
            "workflow": cfg["workflow"],
            "mi_count": len(cfg["rows"]),
            "texture_count": len(mapping),
            "all_sources_exist": True,
            "all_sources_skin_v3": True,
        },
        "controls": results,
    }
    output = HERE / "test_sk_offline_report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "mis": len(cfg["rows"]),
                      "textures": len(mapping), "controls": len(results),
                      "report": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
