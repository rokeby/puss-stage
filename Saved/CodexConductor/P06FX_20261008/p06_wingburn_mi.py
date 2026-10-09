"""DRY/APPLY/REVERT per-flat child MIs for one P06 WingBurn target.

The tool never edits a shared material or material graph. It creates Front/Flap
children of the target panel's currently resolved per-flat MIs, enables
UseBurn only on those children, writes measured UV spans, assigns only those
two panel override slots, materializes P06, and reads back Show plus component.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import p06_fx_common as C  # noqa: E402

unreal = C.unreal
RUN = C.stamp("P06WINGBURNMI")
ARGS = os.path.join(HERE, "p06_wingburn_mi_args.json")
RECORD = os.path.join(HERE, "p06_wingburn_mi_record.json")
REPORT = os.path.join(HERE, "p06_wingburn_mi_report.json")
ALLOWED_MASTERS = {
    "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master",
    "/Game/Scenes/Wings/PaintedSurface/Billboard/M_Wing_Billboard_Master_v2",
}
TOL = 1.0e-4


def linear_fit(xs, ys):
    C.require(len(xs) == len(ys) and len(xs) >= 3, "FIT_COUNT")
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    variance = sum((x - mx) ** 2 for x in xs)
    C.require(variance > 1e-12, "FIT_DEGENERATE")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / variance
    intercept = my - slope * mx
    residual = max(abs(y - (slope * x + intercept)) for x, y in zip(xs, ys))
    return slope, intercept, residual


def plan_slots(slot_rows, wanted, child_root, suffix):
    by = {r["slot"]: r for r in slot_rows}
    C.require(set(wanted) <= set(by), "SLOT_MISSING|" + ",".join(sorted(set(wanted) - set(by))))
    out = []
    for slot in wanted:
        row = dict(by[slot])
        C.require(row.get("material") and row.get("master") in ALLOWED_MASTERS,
                  "MATERIAL_CHAIN|%s|%s" % (slot, row.get("master")))
        C.require(row.get("burn_contract"), "BURN_CONTRACT_BINARY|" + slot)
        row["child"] = "%s/MI_%s_%s" % (child_root.rstrip("/"), suffix, slot)
        out.append(row)
    return out


def _target(show, args):
    cues = list(show.get_editor_property("cues"))
    index, cue = C.cue_by_identity(cues, args["cue_label"], args["cue_guid"])
    pair = cue.get_editor_property("wing_pair")
    panel = pair.get_editor_property(args["side"])
    mesh = panel.get_editor_property("mesh")
    C.require(mesh is not None, "MESH_MISSING")
    expected = C.D.CURRENT_P06[args["cue_label"]].get(args["side"] + "_mesh")
    if expected:
        C.require(C.asset_id(mesh) == expected, "MESH_DRIFT|expected=%s|actual=%s" % (expected, C.asset_id(mesh)))
    return cues, index, cue, pair, panel, mesh


def _master_of(material):
    chain, current = [], material
    for _ in range(8):
        path = C.asset_id(current)
        chain.append(path)
        if path in ALLOWED_MASTERS:
            return path, chain
        if current is None or current.get_class().get_name() != "MaterialInstanceConstant":
            break
        current = current.get_editor_property("parent")
    return None, chain


def _binary_has_burn(master_path):
    path = C.package_file(master_path)
    if not os.path.isfile(path):
        return False
    with open(path, "rb") as handle:
        data = handle.read()
    return all(token in data for token in (b"UseBurn", b"BurnPreview", b"UVSpanUCm", b"UVSpanVCm"))


def _slot_rows(mesh, panel):
    overrides = list(panel.get_editor_property("material_overrides"))
    rows = []
    for index, static in enumerate(list(mesh.get_editor_property("static_materials"))):
        slot = str(static.get_editor_property("material_slot_name"))
        material = overrides[index] if index < len(overrides) and overrides[index] else static.get_editor_property("material_interface")
        master, chain = _master_of(material)
        rows.append({"index": index, "slot": slot, "material": C.asset_id(material),
                     "master": master, "parent_chain": chain,
                     "burn_contract": bool(master and _binary_has_burn(master))})
    return rows, [C.asset_id(x) for x in overrides]


def _slot_vertex_instances(desc, mesh, slots):
    """Vertex-instance ids of the polygon groups whose material slot is in `slots`.
    [meas W&T Q3 9 Oct] Wing 044 L Front/Flap UV0 are planar (residual <=3.3e-8); only Timber is tiled
    (3.807/8.502) -- pooling every section made the old probe refuse with a false UV_NOT_PLANAR."""
    names = [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")]
    ids = []
    for g in range(desc.get_polygon_group_count()):
        gid = unreal.PolygonGroupID(); gid.set_editor_property("id_value", g)
        try:
            slot = str(desc.get_polygon_group_material_slot_name(gid))
        except Exception:  # noqa: BLE001 - API name unverified in 5.8 Python; group index == slot index fallback [inferred]
            slot = names[g] if g < len(names) else ""
        if slot not in slots:
            continue
        for poly in desc.get_polygon_group_polygons(gid):
            for vi in desc.get_polygon_vertex_instances(poly):
                ids.append(int(vi.get_editor_property("id_value")))
    C.require(ids, "UV_SLOT_GROUPS_EMPTY|%s" % (list(slots),))
    return sorted(set(ids))


def _measure_uv(mesh, slots=("Front", "Flap")):
    desc = mesh.get_static_mesh_description(0)
    C.require(desc is not None, "MESH_DESCRIPTION")
    ys, zs, us, vs = [], [], [], []
    for i in _slot_vertex_instances(desc, mesh, set(slots)):
        vi = unreal.VertexInstanceID()
        vi.set_editor_property("id_value", i)
        pos = desc.get_vertex_position(desc.get_vertex_instance_vertex(vi))
        uv = desc.get_vertex_instance_uv(vi, 0)
        ys.append(float(pos.y)); zs.append(float(pos.z)); us.append(float(uv.x)); vs.append(float(uv.y))
    au, bu, ru = linear_fit(ys, us)
    av, bv, rv = linear_fit(zs, vs)
    C.require(abs(au) > 1e-9 and abs(av) > 1e-9 and ru <= 1e-5 and rv <= 1e-5,
              "UV_NOT_PLANAR|u=%g|v=%g" % (ru, rv))
    return {"mesh": C.asset_id(mesh), "u_axis": [au, bu], "v_axis": [av, bv],
            "u_span_cm": 1.0 / abs(au), "v_span_cm": 1.0 / abs(av),
            "u_error": ru, "v_error": rv, "samples": len(us)}


def _set_switch(mi, name, value):
    mel = unreal.MaterialEditingLibrary
    try:
        mel.set_material_instance_static_switch_parameter_value(mi, name, bool(value))
    except TypeError:
        mel.set_material_instance_static_switch_parameter_value(
            mi, name, bool(value), unreal.MaterialParameterAssociation.GLOBAL_PARAMETER)


def _create_child(row, uv, args):
    C.require(not unreal.EditorAssetLibrary.does_asset_exist(row["child"]), "CHILD_EXISTS|" + row["child"])
    parent = unreal.load_asset(row["material"])
    C.require(parent is not None, "PARENT_LOAD|" + row["material"])
    child = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        row["child"].rsplit("/", 1)[-1], row["child"].rsplit("/", 1)[0],
        unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    C.require(child is not None, "CHILD_CREATE|" + row["child"])
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(child, parent)
    _set_switch(child, "UseBurn", True)
    mel.set_material_instance_scalar_parameter_value(child, "BurnPreview", float(args["burn_preview"]))
    mel.set_material_instance_scalar_parameter_value(child, "UVSpanUCm", float(uv["u_span_cm"]))
    mel.set_material_instance_scalar_parameter_value(child, "UVSpanVCm", float(uv["v_span_cm"]))
    mel.update_material_instance(child)
    C.require(unreal.EditorAssetLibrary.save_loaded_asset(child, only_if_is_dirty=False), "CHILD_SAVE|" + row["child"])
    return _child_readback(row, uv)


def _child_readback(row, uv):
    mi = unreal.load_asset(row["child"])
    C.require(mi is not None and C.asset_id(mi.get_editor_property("parent")) == row["material"], "CHILD_PARENT|" + row["child"])
    mel = unreal.MaterialEditingLibrary
    values = {
        "UseBurn": bool(mel.get_material_instance_static_switch_parameter_value(mi, "UseBurn")),
        "BurnPreview": float(mel.get_material_instance_scalar_parameter_value(mi, "BurnPreview")),
        "UVSpanUCm": float(mel.get_material_instance_scalar_parameter_value(mi, "UVSpanUCm")),
        "UVSpanVCm": float(mel.get_material_instance_scalar_parameter_value(mi, "UVSpanVCm")),
    }
    C.require(values["UseBurn"] and abs(values["BurnPreview"]) <= TOL
              and abs(values["UVSpanUCm"] - uv["u_span_cm"]) <= TOL
              and abs(values["UVSpanVCm"] - uv["v_span_cm"]) <= TOL,
              "CHILD_VALUES|%s|%s" % (row["child"], json.dumps(values, sort_keys=True)))
    return {"parent": row["material"], "values": values}


def _assign(show, args, rows, restore=None):
    cues, index, cue, pair, panel, mesh = _target(show, args)
    del mesh
    overrides = list(panel.get_editor_property("material_overrides"))
    max_index = max(r["index"] for r in rows)
    while len(overrides) <= max_index:
        overrides.append(None)
    if restore is None:
        for row in rows:
            overrides[row["index"]] = unreal.load_asset(row["child"])
    else:
        for row in rows:
            path = restore[row["slot"]]
            overrides[row["index"]] = unreal.load_asset(path) if path else None
    panel.set_editor_property("material_overrides", overrides)
    pair.set_editor_property(args["side"], panel)
    cue.set_editor_property("wing_pair", pair)
    cues[index] = cue
    show.modify()
    show.set_editor_property("cues", cues)


def _show_readback(args, rows):
    show = unreal.load_asset(C.D.SHOW)
    _, _, _, _, panel, _ = _target(show, args)
    overrides = list(panel.get_editor_property("material_overrides"))
    return {row["slot"]: C.asset_id(overrides[row["index"]]) if row["index"] < len(overrides) else None for row in rows}


def _component_readback(show, args, rows):
    actor = C.p06_actor(show)
    refs = [r for r in list(actor.get_editor_property("materialized_panels"))
            if C.guid_text(r.get_editor_property("cue_guid")) == args["cue_guid"]
            and args["side"].upper() in str(r.get_editor_property("side")).upper()]
    C.require(len(refs) == 1, "PANEL_REF|%d" % len(refs))
    comp = refs[0].get_editor_property("component")
    return {row["slot"]: C.asset_id(comp.get_material(row["index"])) for row in rows}


def main():
    try:
        args = C.D.validate_wing_mi(C.read_json(ARGS))
    except C.D.ConfigError as error:
        raise C.ToolError(str(error))
    C.editor_guard()
    before = C.require_clean("PRE")
    show, _ = C.show_and_cues()
    _, _, _, _, panel, mesh = _target(show, args)
    slot_rows, original_overrides = _slot_rows(mesh, panel)
    uv = _measure_uv(mesh)
    rows = plan_slots(slot_rows, args["slots"], args["child_root"], args["name_suffix"])
    exists = {r["child"]: bool(unreal.EditorAssetLibrary.does_asset_exist(r["child"])) for r in rows}
    plan = {"args": args, "mesh": C.asset_id(mesh), "uv": uv, "rows": rows,
            "original_overrides": original_overrides, "child_exists": exists}
    if args["mode"] == "DRY":
        C.require(not any(exists.values()), "DRY_CHILD_ALREADY_EXISTS|" + json.dumps(exists, sort_keys=True))
        C.require(C.census() == before, "DRY_CENSUS")
        C.write_json(REPORT, {"run": RUN, "mode": "DRY", "plan": plan,
                              "census_before": before, "census_after": C.census()})
        unreal.log("P06WINGBURNMI_DRY_OK|run=%s|cue=%s|side=%s|mesh=%s|children=%d|uv_span=%.3fx%.3f|census_equal=1" %
                   (RUN, args["cue_label"], args["side"], C.asset_id(mesh), len(rows),
                    uv["u_span_cm"], uv["v_span_cm"]))
        return
    if args["mode"] == "APPLY":
        C.require(not os.path.exists(RECORD), "RECORD_EXISTS")
        C.require(not any(exists.values()), "CHILD_EXISTS")
        parents = sorted({r["material"] for r in rows})
        backup = C.backup("PreP06WingBurnMI", RUN, [C.D.SHOW, C.D.EXPECTED_WORLD] + parents,
                          "Show, level, and resolved per-flat parents before child-MI isolation.")
        restore = {r["slot"]: (original_overrides[r["index"]] if r["index"] < len(original_overrides) else None)
                   for r in rows}
        record = {"run": RUN, "status": "prepared", "args": args, "plan": plan,
                  "backup": backup, "restore": restore, "created": [], "child_readback": {}}
        C.write_json(RECORD, record, exclusive=True)
        for row in rows:
            record["created"].append(row["child"])
            C.write_json(RECORD, record)  # claim deterministic absent target before mutation
            record["child_readback"][row["child"]] = _create_child(row, uv, args)
            C.write_json(RECORD, record)
        C.require_clean("POST_CHILD_SAVE")
        _assign(show, args, rows)
        C.require(C.p06_actor(show).materialize_passage(), "P06_MATERIALIZE")
        expected_dirty = {"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]}
        C.require(C.census() == expected_dirty, "DIRTY_SCOPE|%s" % json.dumps(C.census(), sort_keys=True))
        C.save_show_level()
        want = {r["slot"]: r["child"] for r in rows}
        show_rb, component_rb = _show_readback(args, rows), _component_readback(show, args, rows)
        C.require(show_rb == want and component_rb == want, "ASSIGN_READBACK|%s|%s" % (show_rb, component_rb))
        record.update({"status": "applied", "show_readback": show_rb, "component_readback": component_rb})
        C.write_json(RECORD, record)
        C.write_json(REPORT, {"run": RUN, "mode": "APPLY", "backup": backup,
                              "children": record["child_readback"], "show": show_rb,
                              "component": component_rb, "census_after": C.census()})
        unreal.log("P06WINGBURNMI_APPLY_OK|run=%s|cue=%s|side=%s|children=%d|show_readback=1|component_readback=1|backup=%s|dirty_after=0+0" %
                   (RUN, args["cue_label"], args["side"], len(rows), backup["root"]))
        return
    C.require(os.path.isfile(RECORD), "RECORD_MISSING")
    record = C.read_json(RECORD)
    C.require(record.get("status") in ("prepared", "applied"), "RECORD_STATUS")
    rows = record["plan"]["rows"]
    claimed = record["created"]
    created = [p for p in claimed if unreal.EditorAssetLibrary.does_asset_exist(p)]
    backup = C.backup("PreP06WingBurnMIRevert", RUN, [C.D.SHOW, C.D.EXPECTED_WORLD] + created,
                      "Show, level, and created children before confirmed permanent REVERT deletion.")
    record["revert_intent"] = {"run": RUN, "backup": backup, "delete": created,
                               "claimed_but_absent": sorted(set(claimed) - set(created))}
    C.write_json(RECORD, record)  # before first revert mutation
    show = unreal.load_asset(C.D.SHOW)
    live = _show_readback(args, rows)
    wanted = {r["slot"]: r["child"] for r in rows}
    C.require(live in (wanted, record["restore"]), "LIVE_ASSIGN_DRIFT|%s" % live)
    if live == wanted:
        _assign(show, args, rows, restore=record["restore"])
        C.require(C.p06_actor(show).materialize_passage(), "P06_REVERT_MATERIALIZE")
        C.require(C.census() == {"content": [C.D.SHOW], "maps": [C.D.EXPECTED_WORLD]}, "REVERT_DIRTY_SCOPE")
        C.save_show_level()
    C.require(_show_readback(args, rows) == record["restore"], "RESTORE_READBACK")
    for path in reversed(created):
        refs = [str(x).split(".", 1)[0] for x in unreal.EditorAssetLibrary.find_package_referencers_for_asset(path, False)]
        C.require(not refs, "CHILD_REFERENCED|%s|%s" % (path, refs))
        C.require(unreal.EditorAssetLibrary.delete_asset(path), "CHILD_DELETE|" + path)
    C.require_clean("POST_REVERT")
    archived = C.archive_record(RECORD, RUN)
    C.write_json(REPORT, {"run": RUN, "mode": "REVERT", "restored": record["restore"],
                          "claimed": claimed, "deleted": created, "backup": backup, "archived_record": archived,
                          "census_after": C.census()})
    unreal.log("P06WINGBURNMI_REVERT_OK|run=%s|restored=%d|deleted=%d|backup=%s|record=%s|dirty_after=0+0" %
               (RUN, len(rows), len(created), backup["root"], archived))


if unreal is not None and __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        unreal.log_error("P06WINGBURNMI_STOPPED|run=%s|%s|do not Save All; inspect exact census" % (RUN, error))
        raise
