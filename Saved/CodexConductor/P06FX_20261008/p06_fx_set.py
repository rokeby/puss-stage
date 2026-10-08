"""DRY/APPLY/REVERT the first P06 FX attachment set; never edits foreign FX.

Defaults: motes at Wing 052, one isolated WingBurn on Wing 044 Left, and one
light-module-disabled FireBasket at Wing 049 Left. Candle/smoke are held false.
Existing car, bee glints, atmosphere, lighting and topple data are read-only.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p06_fx_common as C  # noqa: E402
import p06_fx_blueprints as B  # noqa: E402
import p06_wingburn_mi as W  # noqa: E402

unreal = C.unreal
RUN = C.stamp("P06FXSET")
ARGS = os.path.join(HERE, "p06_fx_set_args.json")
RECORD = os.path.join(HERE, "p06_fx_set_record.json")
REPORT = os.path.join(HERE, "p06_fx_set_report.json")
BPS_RECORD = os.path.join(HERE, "p06_fx_blueprints_record.json")
MI_RECORD = os.path.join(HERE, "p06_wingburn_mi_record.json")
LABEL_PREFIX = "P06 FX 20261008 - "


TYPE_NAMES = {
    "Motes": ("MOTES",),
    "Fire": ("FIRE",),
    "WingBurn": ("WING_BURN", "WINGBURN"),
}
ANCHOR_NAMES = {
    "PAIR_CENTRE": ("PAIR_CENTRE", "PAIRCENTRE"),
    "LEFT_PANEL": ("LEFT_PANEL", "LEFTPANEL"),
    "RIGHT_PANEL": ("RIGHT_PANEL", "RIGHTPANEL"),
    "STATION": ("STATION",),
}


def label_for(row):
    return LABEL_PREFIX + row["id"]


def dependency_gate(args, asset_exists, bp_record, mi_record, live_mi, live_bps=True):
    bad = []
    needed = {"Motes": "Motes", "Fire": "FireBasket", "WingBurn": "WingBurn"}
    for p in args["placements"]:
        name = needed[p["type"]]
        if not asset_exists.get(C.D.EFFECT_SPECS[name]["bp"]):
            bad.append("BP_MISSING|" + name)
    if not bp_record or bp_record.get("status") != "applied":
        bad.append("BP_RECORD_NOT_APPLIED")
    elif bp_record.get("args", {}).get("fire_particle_light_enabled") is not False:
        bad.append("FIRE_PARTICLE_LIGHT_NOT_OFF")
    if not live_bps:
        bad.append("BP_LIVE_READBACK")
    if not mi_record or mi_record.get("status") != "applied":
        bad.append("WING_MI_RECORD_NOT_APPLIED")
    elif not live_mi:
        bad.append("WING_MI_LIVE_READBACK")
    return sorted(set(bad))


def _attachment_rows(show):
    rows = []
    for cue in list(show.get_editor_property("cues")):
        pair = cue.get_editor_property("wing_pair")
        for item in list(pair.get_editor_property("attachments")):
            rows.append({"cue": str(cue.get_editor_property("label")),
                         "cue_guid": C.guid_text(cue.get_editor_property("cue_guid")),
                         "guid": C.guid_text(item.get_editor_property("attachment_guid")),
                         "label": str(item.get_editor_property("label"))})
    return rows


def _target_panel(show, placement):
    cues = list(show.get_editor_property("cues"))
    _, cue = C.cue_by_identity(cues, placement["cue_label"], placement["cue_guid"])
    side = "left" if placement["anchor"] == "LEFT_PANEL" else "right"
    panel = cue.get_editor_property("wing_pair").get_editor_property(side)
    mesh = panel.get_editor_property("mesh")
    C.require(mesh is not None, "BURN_MESH")
    return mesh


def _mi_live(show, mi_record):
    if not mi_record or mi_record.get("status") != "applied":
        return False
    args = mi_record["args"]
    rows = mi_record["plan"]["rows"]
    want = {r["slot"]: r["child"] for r in rows}
    try:
        return W._show_readback(args, rows) == want
    except Exception:  # noqa: BLE001 - dependency refusal, reported by caller
        return False


def _bps_live(args):
    needed = {"Motes": "Motes", "Fire": "FireBasket", "WingBurn": "WingBurn"}
    try:
        for placement in args["placements"]:
            name = needed[placement["type"]]
            row = dict(C.D.EFFECT_SPECS[name])
            row["name"] = name
            B._readback(row)
        light = B._fire_light_readback(unreal.load_asset(C.D.FIRE_NO_LIGHT))
        return bool(light and all(abs(r["spawn_fraction"]) <= 1e-8
                                  and not r["high_quality_lights"]
                                  and not r["shadow_casting_lights"] for r in light))
    except Exception:  # noqa: BLE001 - dependency refusal, reported by caller
        return False


def _snapshot(show, guids=None):
    wanted = set(guids or [])
    out = {}
    for cue in list(show.get_editor_property("cues")):
        pair = cue.get_editor_property("wing_pair")
        for item in list(pair.get_editor_property("attachments")):
            guid = C.guid_text(item.get_editor_property("attachment_guid"))
            if wanted and guid not in wanted:
                continue
            if not str(item.get_editor_property("label")).startswith(LABEL_PREFIX):
                continue
            settings = item.get_editor_property("effect")
            tr = item.get_editor_property("relative_transform")
            out[guid] = {
                "cue_label": str(cue.get_editor_property("label")),
                "cue_guid": C.guid_text(cue.get_editor_property("cue_guid")),
                "label": str(item.get_editor_property("label")),
                "enabled": bool(item.get_editor_property("enabled")),
                "anchor": str(item.get_editor_property("anchor")),
                "type": str(settings.get_editor_property("type")),
                "output": float(settings.get_editor_property("output")),
                "active_radius_cm": float(settings.get_editor_property("active_radius_cm")),
                "linked_light_guid": C.guid_text(settings.get_editor_property("linked_light_attachment_guid")),
                "location": [float(tr.translation.x), float(tr.translation.y), float(tr.translation.z)],
                "burn_start_ahead_cm": float(settings.get_editor_property("burn_start_ahead_cm")),
                "burn_span_cm": float(settings.get_editor_property("burn_span_cm")),
                "ignition_uv": [float(settings.get_editor_property("ignition_uv").x),
                                  float(settings.get_editor_property("ignition_uv").y)],
                "burn_u_axis": [float(settings.get_editor_property("burn_u_axis").x),
                                  float(settings.get_editor_property("burn_u_axis").y)],
                "burn_v_axis": [float(settings.get_editor_property("burn_v_axis").x),
                                  float(settings.get_editor_property("burn_v_axis").y)],
                "measured_mesh": C.asset_id(settings.get_editor_property("burn_uv_measured_mesh")),
                "motes_extent_cm": [float(settings.get_editor_property("motes_extent_cm").x),
                                     float(settings.get_editor_property("motes_extent_cm").y),
                                     float(settings.get_editor_property("motes_extent_cm").z)],
                "flicker_amount": float(settings.get_editor_property("flicker_amount")),
            }
    return out


def _configure(show, placement, guid):
    cues = list(show.get_editor_property("cues"))
    index, cue = C.cue_by_identity(cues, placement["cue_label"], placement["cue_guid"])
    pair = cue.get_editor_property("wing_pair")
    attachments = list(pair.get_editor_property("attachments"))
    hits = [i for i, item in enumerate(attachments)
            if C.guid_text(item.get_editor_property("attachment_guid")) == guid]
    C.require(len(hits) == 1, "NEW_ATTACHMENT|%s|%d" % (guid, len(hits)))
    item = attachments[hits[0]]
    item.set_editor_property("enabled", True)
    settings = item.get_editor_property("effect")
    settings.set_editor_property("output", float(placement["output"]))
    settings.set_editor_property("active_radius_cm", float(placement["active_radius_cm"]))
    settings.set_editor_property("feeds_local_medium", False)
    if placement["type"] == "Motes":
        settings.set_editor_property("motes_extent_cm", unreal.Vector(*placement["motes_extent_cm"]))
    elif placement["type"] == "Fire":
        settings.set_editor_property("flicker_amount", float(placement.get("flicker_amount", 0.0)))
        linked = C.guid_text(settings.get_editor_property("linked_light_attachment_guid"))
        C.require(not linked or linked == "0" * 32, "FIRE_LINKED_LIGHT_PRESENT|" + linked)
    else:
        settings.set_editor_property("burn_start_ahead_cm", float(placement["burn_start_ahead_cm"]))
        settings.set_editor_property("burn_span_cm", float(placement["burn_span_cm"]))
        settings.set_editor_property("ignition_uv", unreal.Vector2D(*placement["ignition_uv"]))
    item.set_editor_property("effect", settings)
    attachments[hits[0]] = item
    pair.set_editor_property("attachments", attachments)
    cue.set_editor_property("wing_pair", pair)
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _add(show, placement, claim_guid=None):
    effect_type = C.enum_member(unreal.InfinityStageEffectType, *TYPE_NAMES[placement["type"]])
    anchor = C.enum_member(unreal.InfinityAttachmentAnchor, *ANCHOR_NAMES[placement["anchor"]])
    rotation = placement["rotation"]
    transform = unreal.Transform(location=unreal.Vector(*placement["location"]),
                                 rotation=unreal.Rotator(roll=rotation[0], pitch=rotation[1], yaw=rotation[2]),
                                 scale=unreal.Vector(1.0, 1.0, 1.0))
    cues = list(show.get_editor_property("cues"))
    _, cue = C.cue_by_identity(cues, placement["cue_label"], placement["cue_guid"])
    guid = unreal.InfinityStageEffectLibrary.add_effect_attachment(
        show, cue.get_editor_property("cue_guid"), effect_type, anchor, transform, label_for(placement))
    text = C.guid_text(guid)
    C.require(len(text) == 32 and any(c != "0" for c in text), "ADD_GUID")
    if claim_guid is not None:
        claim_guid(text)  # persist ownership before any post-add configuration can fail
    _configure(show, placement, text)
    if placement["type"] == "WingBurn":
        mesh = _target_panel(show, placement)
        uv = W._measure_uv(mesh)
        ok = unreal.InfinityStageEffectLibrary.set_wing_burn_uv_mapping(
            show, cue.get_editor_property("cue_guid"), guid,
            unreal.Vector2D(*uv["u_axis"]), unreal.Vector2D(*uv["v_axis"]), mesh)
        C.require(ok, "SET_BURN_UV")
    return text


def _remove(show, guids):
    wanted = set(guids)
    cues = list(show.get_editor_property("cues"))
    removed = []
    for i, cue in enumerate(cues):
        pair = cue.get_editor_property("wing_pair")
        attachments = list(pair.get_editor_property("attachments"))
        kept = []
        for item in attachments:
            guid = C.guid_text(item.get_editor_property("attachment_guid"))
            if guid in wanted:
                C.require(str(item.get_editor_property("label")).startswith(LABEL_PREFIX), "FOREIGN_GUID|" + guid)
                removed.append(guid)
            else:
                kept.append(item)
        if len(kept) != len(attachments):
            pair.set_editor_property("attachments", kept)
            cue.set_editor_property("wing_pair", pair)
            cues[i] = cue
    C.require(set(removed) == wanted and len(removed) == len(wanted), "REMOVE_SET|%s|%s" % (removed, sorted(wanted)))
    show.modify()
    show.set_editor_property("cues", cues)


def _actor_readback(guids):
    out = {}
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        try:
            guid = C.guid_text(actor.get_editor_property("attachment_guid"))
        except Exception:  # noqa: BLE001
            continue
        if guid in guids:
            out[guid] = {"class": str(actor.get_class().get_path_name()), "label": str(actor.get_actor_label())}
    return out


def main():
    try:
        args = C.D.validate_set(C.read_json(ARGS))
    except C.D.ConfigError as error:
        raise C.ToolError(str(error))
    C.editor_guard()
    before = C.require_clean("PRE")
    show, _ = C.show_and_cues()
    foreign_before = _attachment_rows(show)
    duplicates = [r for r in foreign_before if r["label"].startswith(LABEL_PREFIX)]
    bpr = C.read_json(BPS_RECORD) if os.path.isfile(BPS_RECORD) else None
    mir = C.read_json(MI_RECORD) if os.path.isfile(MI_RECORD) else None
    assets = {spec["bp"]: bool(unreal.EditorAssetLibrary.does_asset_exist(spec["bp"]))
              for spec in C.D.EFFECT_SPECS.values()}
    live_bps = _bps_live(args)
    gate = dependency_gate(args, assets, bpr, mir, _mi_live(show, mir), live_bps)
    plan = {"args": args, "gate_refusals": gate, "existing_owned": duplicates,
            "foreign_attachment_count": len(foreign_before), "live_blueprint_readback": live_bps}
    if args["mode"] == "DRY":
        C.require(C.census() == before, "DRY_CENSUS")
        C.write_json(REPORT, {"run": RUN, "mode": "DRY", "plan": plan,
                              "census_before": before, "census_after": C.census()})
        unreal.log("P06FXSET_DRY_OK|run=%s|placements=%d|gate_refusals=%d|owned_existing=%d|foreign=%d|census_equal=1" %
                   (RUN, len(args["placements"]), len(gate), len(duplicates), len(foreign_before)))
        return
    if args["mode"] == "APPLY":
        C.require(not gate, "GATE|" + ";".join(gate))
        C.require(not duplicates, "OWNED_ALREADY_EXISTS")
        C.require(not os.path.exists(RECORD), "RECORD_EXISTS")
        backup = C.backup("PreP06FxSet", RUN, [C.D.SHOW, C.D.EXPECTED_WORLD],
                          "Show and level before first P06 FX attachment set.")
        record = {"run": RUN, "status": "prepared", "args": args, "plan": plan,
                  "backup": backup, "foreign_before": foreign_before, "guids": []}
        C.write_json(RECORD, record, exclusive=True)
        def claim_guid(guid):
            record["guids"].append(guid)
            C.write_json(RECORD, record)

        for placement in args["placements"]:
            _add(show, placement, claim_guid)
        expected = _snapshot(show, record["guids"])
        C.require(len(expected) == len(args["placements"]), "IN_MEMORY_READBACK")
        C.require(C.p06_actor(show).materialize_passage(), "P06_MATERIALIZE")
        C.require(C.census() == {"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]},
                  "DIRTY_SCOPE|" + json.dumps(C.census(), sort_keys=True))
        C.save_show_level()
        saved = _snapshot(unreal.load_asset(C.D.SHOW), record["guids"])
        actors = _actor_readback(set(record["guids"]))
        C.require(saved == expected, "SAVED_READBACK")
        C.require(set(actors) == set(record["guids"]), "ACTOR_READBACK|%s" % sorted(actors))
        foreign_after = [r for r in _attachment_rows(unreal.load_asset(C.D.SHOW))
                         if not r["label"].startswith(LABEL_PREFIX)]
        C.require(foreign_after == foreign_before, "FOREIGN_ATTACHMENT_DRIFT")
        record.update({"status": "applied", "expected": expected, "actors": actors})
        C.write_json(RECORD, record)
        C.write_json(REPORT, {"run": RUN, "mode": "APPLY", "backup": backup,
                              "attachments": saved, "actors": actors, "census_after": C.census()})
        unreal.log("P06FXSET_APPLY_OK|run=%s|attachments=%d|actors=%d|readback=1|backup=%s|dirty_after=0+0" %
                   (RUN, len(saved), len(actors), backup["root"]))
        return
    C.require(os.path.isfile(RECORD), "RECORD_MISSING")
    record = C.read_json(RECORD)
    C.require(record.get("status") in ("prepared", "applied"), "RECORD_STATUS")
    guids = record["guids"]
    owned_rows = [r for r in _attachment_rows(show) if r["label"].startswith(LABEL_PREFIX)]
    C.require(len(owned_rows) == len(guids) and {r["guid"] for r in owned_rows} == set(guids),
              "LIVE_OWNED_SET_DRIFT|%s" % sorted(r["guid"] for r in owned_rows))
    live = _snapshot(show, guids) if guids else {}
    C.require(set(live) == set(guids), "LIVE_OWNED_GUID_DRIFT|%s" % sorted(live))
    if record.get("status") == "applied":
        C.require(live == record["expected"], "LIVE_STATE_DRIFT")
    current_foreign = [r for r in _attachment_rows(show) if not r["label"].startswith(LABEL_PREFIX)]
    C.require(current_foreign == record["foreign_before"], "PRE_REVERT_FOREIGN_ATTACHMENT_DRIFT")
    backup = C.backup("PreP06FxSetRevert", RUN, [C.D.SHOW, C.D.EXPECTED_WORLD],
                      "Show and level before removing only recorded P06 FX attachments.")
    record["revert_intent"] = {"run": RUN, "backup": backup}
    C.write_json(RECORD, record)
    if guids:
        _remove(show, guids)
        C.require(C.p06_actor(show).materialize_passage(), "P06_REVERT_MATERIALIZE")
        C.require(C.census() == {"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]}, "REVERT_DIRTY_SCOPE")
        C.save_show_level()
    C.require(not _snapshot(unreal.load_asset(C.D.SHOW), guids), "REVERT_READBACK_PRESENT")
    C.require(not _actor_readback(set(guids)), "REVERT_ACTOR_PRESENT")
    foreign_after = [r for r in _attachment_rows(unreal.load_asset(C.D.SHOW))
                     if not r["label"].startswith(LABEL_PREFIX)]
    C.require(foreign_after == record["foreign_before"], "REVERT_FOREIGN_ATTACHMENT_DRIFT")
    archived = C.archive_record(RECORD, RUN)
    C.write_json(REPORT, {"run": RUN, "mode": "REVERT", "removed": guids,
                          "backup": backup, "archived_record": archived, "census_after": C.census()})
    unreal.log("P06FXSET_REVERT_OK|run=%s|removed=%d|backup=%s|record=%s|dirty_after=0+0" %
               (RUN, len(guids), backup["root"], archived))


if unreal is not None and __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        unreal.log_error("P06FXSET_STOPPED|run=%s|%s|do not Save All; inspect exact census" % (RUN, error))
        raise
