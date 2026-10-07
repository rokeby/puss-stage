"""OFFLINE planner for the S4 hangar IN-PLACE resize (7 Oct; S4_HANGAR_REBUILD_PLAN.md). System Python only:
never imports unreal, never touches Unreal. Reads hangar_build.py's OWN plan_for()/ranked() and HANGAR defaults by
AST (so the geometry is hangar_build's, not a copy), plans OLD (live S4 params) and NEW (hangar_resize_s4_args.json),
and writes hangar_resize_s4_targets.json: per label the box-frame (root-relative, ASSEMBLED pose) loc/size before and
after, plus the exit-door pieces, apron, pinned-exposure volume and the lattice fly Z key values.

Asserts (exit 1 on failure): identical label sets (so every LS_S4_HangarRise binding, every S4 Arrival
PreSceneFloatDrive and every exit-door label survives), K unchanged, the rail/bulb clearance under the roof through
the roof swing, Klara's set inside the new box with the reveal's own side margin and comfort, the ghost light
outside her set. Run:  python hangar_resize_s4_plan.py   (prints HANGAR_RESIZE_S4_PLAN_OK|...)
"""
import ast
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "hangar_build.py")
ARGS = os.path.join(HERE, "hangar_resize_s4_args.json")
OUT = os.path.join(HERE, "hangar_resize_s4_targets.json")
DOOR_W, DOOR_H = 300.0, 450.0          # hangar_exit_doors.py DOOR_WIDTH_CM / DOOR_HEIGHT_CM


def load_builder():
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    ns = {"math": math}
    keep = []
    defaults = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("ranked", "plan_for", "corners"):
            keep.append(node)
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "HANGAR" for t in node.targets):
            defaults = ast.literal_eval(node.value)
    if defaults is None or len(keep) != 3:
        raise SystemExit("HANGAR_RESIZE_S4_PLAN_STOPPED|reason=builder functions/defaults not found in hangar_build.py")
    exec(compile(ast.Module(body=keep, type_ignores=[]), SRC, "exec"), ns)
    return ns, defaults


def k_of(h):
    return math.sqrt(max(h["depth"], 2.0 * h["height"]) / 6000.0)


def door_pieces(h):
    """The five S4 exit-door pieces in the root frame, generalised from hangar_exit_doors_record.json (S4 rows at
    half_w 1000 reproduce exactly: checked below)."""
    d, w, wt, ht = h["depth"], h["half_w"], h["wall_t"], h["height"]
    x = d + wt / 2.0
    outer = w + wt
    side = outer - DOOR_W / 2.0
    return {
        "S4 Hangar Far Wall Above Exit": {"loc": [x, 0.0, (DOOR_H + ht) / 2.0], "size": [wt, 2.0 * outer, ht - DOOR_H]},
        "S4 Hangar Far Wall Left of Exit": {"loc": [x, -(outer + DOOR_W / 2.0) / 2.0, DOOR_H / 2.0], "size": [wt, side, DOOR_H]},
        "S4 Hangar Far Wall Right of Exit": {"loc": [x, (outer + DOOR_W / 2.0) / 2.0, DOOR_H / 2.0], "size": [wt, side, DOOR_H]},
        "S4 Hangar Exit Door Leaf": {"loc": [x - 0.05, 0.0, DOOR_H / 2.0], "size": [wt, DOOR_W - 1.0, DOOR_H - 1.0]},
        "S4 Hangar Exit Black": {"loc": [d + wt + 2.0, 0.0, DOOR_H / 2.0], "size": [2.0, DOOR_W, DOOR_H]},
    }


def main():
    ns, defaults = load_builder()
    args = json.load(open(ARGS, encoding="utf-8"))
    old = dict(defaults, **args["old"])
    new = dict(defaults, **args["new"])
    old_items, old_counts = ns["plan_for"](old)
    new_items, new_counts = ns["plan_for"](new)
    fails = []
    ol, nl = {i["label"]: i for i in old_items}, {i["label"]: i for i in new_items}
    if set(ol) != set(nl):
        fails.append("LABELS_DIFFER: only_old=%s only_new=%s" % (sorted(set(ol) - set(nl))[:8], sorted(set(nl) - set(ol))[:8]))
    if old_counts != new_counts:
        fails.append("COUNTS_DIFFER: %s vs %s" % (old_counts, new_counts))
    for lab in set(ol) & set(nl):
        if ol[lab]["parent"] != nl[lab]["parent"]:
            fails.append("PARENT_CHANGES: %s %s -> %s" % (lab, ol[lab]["parent"], nl[lab]["parent"]))
    k_old, k_new = k_of(old), k_of(new)
    if abs(k_old - k_new) > 1e-9:
        fails.append("K_CHANGES: %.4f -> %.4f" % (k_old, k_new))
    # The far wall's original label became the exit-door "Above Exit" piece (hangar_exit_doors_record.json created[]
    # reused_original=true), so it is planned by door_pieces(), not plan_for.
    doors_old, doors_new = door_pieces(old), door_pieces(new)
    rec = json.load(open(os.path.join(HERE, "..", "CodexConductor", "hangar_exit_doors_record.json"), encoding="utf-8"))
    s4 = [s for s in rec["plan"]["scenes"] if int(s["scene"]) == 4][0]
    for p in s4["pieces"]:
        want = doors_old[p["label"]]
        e = max(max(abs(a - b) for a, b in zip(want["loc"], p["location_cm"])),
                max(abs(a - b) for a, b in zip(want["size"], p["size_cm"])))
        if e > 0.01:
            fails.append("DOOR_FORMULA_MISMATCH: %s %.3f cm vs the 3 Oct record" % (p["label"], e))
    # Lattice under the roof, assembled AND at the fly's rest height (the roof swings over it, 6.63-12.63 s live).
    rest_top = new["lattice_z"] + new["lattice_fly"] + 34.0 + 17.0      # rail centre +34, half height 17 (plan_for)
    if rest_top > new["height"] - 1.0:
        fails.append("LATTICE_REST_HITS_ROOF: rail top %.0f vs roof underside %.0f" % (rest_top, new["height"]))
    # Klara's set (dock frame after the reveal placement) inside the new box.
    ks = args["klara_s4"]
    x0, x1, y0, y1 = ks["set_box_local_dock_after"]
    iy = new["half_w"] - ks["side_margin_cm"]
    far_limit = new["apron"] + new["depth"] - ks["side_margin_cm"]
    checks = {"near_ok": x0 >= new["apron"] - 1e-6, "far_ok": x1 <= far_limit,
              "side_ok": y1 <= iy and y0 >= -iy,
              "side_comfort_ok": max(abs(y0), abs(y1)) + ks["comfort_cm"] <= new["half_w"],
              "under_lattice": ks["set_top_cm"] + ks["comfort_cm"] <= new["lattice_z"],
              "under_roof": ks["set_top_cm"] <= new["height"]}
    for kk, ok in checks.items():
        if not ok:
            fails.append("KLARA_%s_FAILS" % kk.upper())
    gx = new["ghost_x"] + new["apron"]
    if x0 - ks["comfort_cm"] <= gx <= x1 + ks["comfort_cm"] and y0 - ks["comfort_cm"] <= new["ghost_y"] <= y1 + ks["comfort_cm"]:
        fails.append("GHOST_INSIDE_SET: dock x %.0f y %.0f" % (gx, new["ghost_y"]))
    old_gx = old["ghost_x"] + old["apron"]
    ghost_was_inside = x0 <= old_gx <= x1 and y0 <= old["ghost_y"] <= y1
    moves = []
    for lab in sorted(nl):
        a, b = ol.get(lab), nl[lab]
        if a is None:
            continue
        dl = [b["loc"][i] - a["loc"][i] for i in range(3)]
        ds = [b["size"][i] - a["size"][i] for i in range(3)] if a["size"] and b["size"] else None
        if max(abs(v) for v in dl) > 1e-6 or (ds and max(abs(v) for v in ds) > 1e-6):
            moves.append({"label": lab, "kind": b["kind"], "parent": b["parent"], "loc_old": a["loc"], "loc_new": b["loc"],
                          "size_old": a["size"], "size_new": b["size"]})
    for lab in sorted(doors_new):
        moves.append({"label": lab, "kind": "door_piece", "parent": "S4 Hangar Root", "loc_old": doors_old[lab]["loc"],
                      "loc_new": doors_new[lab]["loc"], "size_old": doors_old[lab]["size"], "size_new": doors_new[lab]["size"]})
    # Every live piece (the tool's label contract): plan_for labels minus the renamed far wall, plus the five door
    # pieces. fly_subtree / roof_subtree let the tool compose against the LIVE fly height and roof hinge pitch.
    def chain(lab):
        out, p = [], nl[lab]["parent"]
        while p:
            out.append(p)
            p = nl[p]["parent"]
        return out

    pieces = []
    for lab in sorted(nl):
        if lab == "S4 Hangar Far Wall":
            continue
        a, b = ol[lab], nl[lab]
        anc = chain(lab)
        pieces.append({"label": lab, "kind": b["kind"], "parent": b["parent"], "ancestors": anc,
                       "fly_subtree": lab == "S4 Hangar Lattice Fly" or "S4 Hangar Lattice Fly" in anc,
                       "roof_subtree": "S4 Hangar Roof Hinge" in anc,
                       "loc_old": a["loc"], "loc_new": b["loc"], "size_old": a["size"], "size_new": b["size"]})
    for lab in sorted(doors_new):
        pieces.append({"label": lab, "kind": "door_piece", "parent": None, "ancestors": ["S4 Hangar Root"],
                       "fly_subtree": False, "roof_subtree": False,
                       "loc_old": doors_old[lab]["loc"], "loc_new": doors_new[lab]["loc"],
                       "size_old": doors_old[lab]["size"], "size_new": doors_new[lab]["size"]})
    fly_old = old["lattice_z"] + old["lattice_fly"]
    fly_new = new["lattice_z"] + new["lattice_fly"]
    keys_live = args["lattice_fly_z_keys_live"]
    remap = {round(fly_old, 3): fly_new, round(old["lattice_z"], 3): new["lattice_z"]}
    keys_new = [[t, remap[round(v, 3)]] for t, v in keys_live]
    out = {
        "tool": "hangar_resize_s4_plan", "frame": "S4 Hangar Root, ASSEMBLED pose (hangar_build.py plan_for); +x into the box",
        "old_params": args["old"], "new_params": args["new"], "k_old": k_old, "k_new": k_new,
        "counts_old": old_counts, "counts_new": new_counts, "labels": len(nl),
        "unchanged_labels": len(nl) - sum(1 for m in moves if m["kind"] != "door_piece"),
        "moves": moves,
        "pieces": pieces,
        "roof_hinge_loc": nl["S4 Hangar Roof Hinge"]["loc"],
        "cube_cm": 100.0,
        "world_fixed": {
            "S4 Hangar Apron": {"dock_loc": [new["apron"] / 2.0, 0.0, -new["floor_t"] / 2.0],
                                "scale_old": [old["apron"] / 100.0, 2.0 * old["half_w"] / 100.0, old["floor_t"] / 100.0],
                                "scale_new": [new["apron"] / 100.0, 2.0 * new["half_w"] / 100.0, new["floor_t"] / 100.0]},
            "S4 Hangar Pinned Exposure": {"note": "scale Y only; its X/Z are the 5 m-nearer live values (hangar_build.py:27-29)",
                                          "scale_y_old": (2.0 * old["half_w"] + 200.0) / 200.0,
                                          "scale_y_new": (2.0 * new["half_w"] + 200.0) / 200.0}},
        "lattice_fly": {"rest_z_old": fly_old, "rest_z_new": fly_new, "landed_z_old": old["lattice_z"],
                        "landed_z_new": new["lattice_z"], "keys_live": keys_live, "keys_new": keys_new,
                        "rail_top_at_rest_cm": rest_top, "roof_underside_cm": new["height"]},
        "klara_checks": checks, "ghost_was_inside_set": ghost_was_inside,
        "fails": fails,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    if fails:
        print("HANGAR_RESIZE_S4_PLAN_STOPPED|fails=%s" % fails)
        return 1
    print("HANGAR_RESIZE_S4_PLAN_OK|labels=%d|moves=%d|k=%.3f->%.3f|counts=%s|fly_keys=%s|ghost_was_inside=%s"
          % (len(nl), len(moves), k_old, k_new, new_counts, keys_new, ghost_was_inside))
    return 0


if __name__ == "__main__":
    sys.exit(main())
