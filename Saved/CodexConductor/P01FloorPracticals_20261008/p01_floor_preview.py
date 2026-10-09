"""PNG maps of a P01 FLOOR plan (before -> after, per bay), for Gary to judge before APPLY.

  python p01_floor_preview.py <p01_floor_report_<MODE>_<run>.json>   -> p01_floor_topdown_<tag>.png,
                                                                       p01_floor_elevation_<tag>.png (next to it)
Called directly by p01_floor.py COUNT/DRY when matplotlib is importable (the editor's Python may not have it).

SCHEMATIC, per AGENTS.md tiers:
* positions are the plan's pair-frame numbers (exact for the plan) [measured for the plan file];
* panel rectangles are the plan's pair-frame panel AABBs: live ISM bounds in a DRY, Saved/CodexFlatV3 records in
  COUNT (inferred +-35 cm, and a median fallback where P01 has no FlatV3 record);
* lantern boxes are the C++ housing formula mirrored in Python (fixtures_common.housing_pose), not a render.
"""
import json
import math
import os
import runpy
import sys
import types

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
F = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "p01_floor_common.py"), run_name="_p01_floor_common_pv"))
EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]
COL = {"dead": "#d97706", "light": "#2563eb", "can": "#60a5fa", "body": "#7c3aed", "glimmer": "#db2777",
       "working": "#6b7280", "panel": "#d1d5db"}


def _box_pts(t, lo, hi, pair_world=None):
    pts = F.corners_of(t, lo, hi)
    return pts if pair_world is None else [F.to_pair(pair_world, p) for p in pts]


def _lantern_pts(plan, cue_guid, light_t):
    ctx = plan["ctx"][cue_guid]
    lw = F.xf_compose(light_t, ctx["pair_world"])
    lan = plan["lantern"]
    pose = F.FC.housing_pose(lw, ctx["across_world"], lan["bounds"][0], lan["bounds"][1], lan["body_size"])
    return [F.to_pair(ctx["pair_world"], p) for p in F.corners_of(pose, lan["bounds"][0], lan["bounds"][1])]


def _outline(ax, pts, i, j, **kw):
    for a, b in EDGES:
        ax.plot([pts[a][i], pts[b][i]], [pts[a][j], pts[b][j]], lw=0.6, **kw)


def render(plan, out_dir, tag, stem="p01_floor"):
    by_cue = {}
    for t in plan["targets"]:
        by_cue[t["cue_guid"]] = t
    left = {}
    for x in plan["left"]:
        left.setdefault(x["cue_guid"], []).append(x)
    cue_guids = list(by_cue)
    for g in left:
        if g not in by_cue:
            cue_guids.append(g)
    labels = {t["cue_guid"]: t["cue_label"] for t in plan["targets"]}
    labels.update({x["cue_guid"]: x["cue"] for x in plan["left"]})
    cue_guids.sort(key=lambda g: labels[g])
    n = len(cue_guids)
    cols = 8
    rows = int(math.ceil(n / float(cols)))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.0, rows * 4.6), squeeze=False)
    for k, g in enumerate(cue_guids):
        ax = axes[k // cols][k % cols]
        ax.set_xlim(-210, 40)
        ax.set_ylim(-1250, 1250)
        ax.axhspan(-float(plan["opts"]["lane_half_width_cm"]), float(plan["opts"]["lane_half_width_cm"]),
                   color="#f3f4f6", zorder=0)
        ax.set_title(labels[g].replace(plan["passage"] + " ", ""), fontsize=8)
        ax.tick_params(labelsize=6)
        ctx = plan["ctx"].get(g)
        if ctx:
            for p in ctx["panels"]:
                ax.add_patch(Rectangle((p["min"][0], p["min"][1]), p["max"][0] - p["min"][0], p["max"][1] - p["min"][1],
                                       color=COL["panel"], zorder=1))
        t = by_cue.get(g)
        for c in (t["changes"] if t else []):
            if c["what"] == "DEAD_BULB_TO_FLOOR":
                b = c["meta"]["before_glass"]
                a = c["after"]["relative_transform"]["location"]
                ax.plot(b[0], b[1], "o", mfc="none", mec=COL["dead"], ms=4)
                pts = _box_pts(c["after"]["relative_transform"], *c["meta"]["bounds"])
                _outline(ax, pts, 0, 1, color=COL["dead"])
                ax.annotate("", xy=(a[0], a[1]), xytext=(b[0], b[1]),
                            arrowprops=dict(arrowstyle="->", color=COL["dead"], lw=0.6))
            elif c["what"] in ("UPLIGHT_LIGHT_TO_FLOOR", "ADD_UPLIGHT"):
                b = c["meta"]["before_location"] or c["after"]["relative_transform"]["location"]
                a = c["after"]["relative_transform"]["location"]
                if c["what"] == "UPLIGHT_LIGHT_TO_FLOOR":
                    ax.plot(b[0], b[1], "s", mfc="none", mec=COL["light"], ms=4)
                _outline(ax, _lantern_pts(plan, g, c["after"]["relative_transform"]), 0, 1, color=COL["can"])
                ax.plot(a[0], a[1], "s", color=COL["light"], ms=3)
                ax.annotate("", xy=(a[0] + 40, a[1]), xytext=(a[0], a[1]),
                            arrowprops=dict(arrowstyle="->", color=COL["light"], lw=0.8))
                ax.annotate("", xy=(a[0], a[1]), xytext=(b[0], b[1]),
                            arrowprops=dict(arrowstyle="->", color=COL["light"], lw=0.5, ls=":"))
            elif c["what"] == "UPLIGHT_BODY_HIDDEN":
                b = c["meta"]["before_location"]
                ax.plot(b[0], b[1], "D", mfc="none", mec=COL["body"], ms=4)
                ax.plot(b[0], b[1], "x", color=COL["body"], ms=4)
            elif c["what"] == "UPLIGHT_BODY_TO_FLOOR":
                b = c["meta"]["before_location"]
                ax.plot(b[0], b[1], "D", mfc="none", mec=COL["body"], ms=4)
                _outline(ax, _box_pts(c["after"]["relative_transform"], *c["meta"]["bounds"]), 0, 1, color=COL["body"])
        for x in left.get(g, []):
            col = COL["glimmer"] if x["why"].startswith("GLIMMER") else COL["working"]
            ax.plot(x["body_location"][0], x["body_location"][1], "x", color=col, ms=5)
    for k in range(n, rows * cols):
        axes[k // cols][k % cols].axis("off")
    nl = chr(10)
    head = ("%s %s plan (%s)" % (plan["passage"], plan["op"], tag))
    if plan["op"] == "ADD_UPLIGHTS":
        fig.suptitle(head + ": PROPOSED floor uplights, top-down per bay, pair frame (x stretched; lane shaded)." + nl +
                     "Grey: wing panel bounds. Blue square = proposed light, arrow = aim up into the wing face, light-blue "
                     "= the Structure lantern (%s) that would stand on the floor there." % plan["lantern"].get("name"),
                     fontsize=11)
    else:
        fig.suptitle(("%s: top-down per bay, pair frame (x along the route, stretched; y lateral; lane shaded)."
                 + nl + "Grey: wing panel bounds. Amber: dead bulb (hollow = before glass, outline = after, on the floor). "
                 "Blue: uplight (hollow = before light, filled = after, arrow = aim into the wing, light-blue = its lantern)."
                 + nl + "Purple: lamp body (hollow = before, outline = after). Pink x: glimmer LEFT (Conductor 5 plan). "
                 "Purple diamond+x: domestic body hidden (STRUCTURE_CAN: the lantern is the theatre uplight). "
                 "Grey x: working bulb LEFT (B04, 300 lm).").replace("%s", head, 1), fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    top = os.path.join(out_dir, "%s_topdown_%s.png" % (stem, tag))
    fig.savefig(top, dpi=70)
    plt.close(fig)

    # elevation (x-z) of one bay of each kind
    picks = []
    kinds = ("ADD_UPLIGHT",) if plan["op"] == "ADD_UPLIGHTS" else ("DEAD_BULB_TO_FLOOR", "PRACTICAL_CLAMP", "PRACTICAL_L")
    for kind in kinds:
        for t in plan["targets"]:
            hit = None
            for c in t["changes"]:
                if kind == "DEAD_BULB_TO_FLOOR" and c["what"] == kind:
                    hit = t
                elif kind == "ADD_UPLIGHT" and c["what"] == "ADD_UPLIGHT":
                    hit = t
                elif kind != "DEAD_BULB_TO_FLOOR" and c["what"] == "UPLIGHT_LIGHT_TO_FLOOR" and c["label"].endswith(kind):
                    hit = t
            if hit is not None:
                picks.append((kind, hit))
                break
    fig, axes = plt.subplots(1, max(1, len(picks)), figsize=(6 * max(1, len(picks)), 5), squeeze=False)
    for k, (kind, t) in enumerate(picks):
        ax = axes[0][k]
        ctx = plan["ctx"][t["cue_guid"]]
        for p in ctx["panels"]:
            ax.add_patch(Rectangle((p["min"][0], p["min"][2]), p["max"][0] - p["min"][0], 260.0, color=COL["panel"]))
        ax.axhline(0.0, color="#9ca3af", lw=0.8)
        for c in t["changes"]:
            if c["what"] == "DEAD_BULB_TO_FLOOR" and kind == "DEAD_BULB_TO_FLOOR":
                _outline(ax, _box_pts(c["after"]["relative_transform"], *c["meta"]["bounds"]), 0, 2, color=COL["dead"])
                b = c["meta"]["before_glass"]
                ax.plot(b[0], b[2], "o", mfc="none", mec=COL["dead"])
            if c["what"] in ("UPLIGHT_LIGHT_TO_FLOOR", "ADD_UPLIGHT") and kind != "DEAD_BULB_TO_FLOOR" and \
                    (c["label"].endswith(kind) or kind == "ADD_UPLIGHT"):
                a = c["after"]["relative_transform"]["location"]
                _outline(ax, _lantern_pts(plan, t["cue_guid"], c["after"]["relative_transform"]), 0, 2, color=COL["can"])
                p = math.radians(c["meta"]["pitch_deg"])
                ax.annotate("", xy=(a[0] + 120 * math.cos(p), a[2] + 120 * math.sin(p)), xytext=(a[0], a[2]),
                            arrowprops=dict(arrowstyle="->", color=COL["light"]))
                b = c["meta"]["before_location"]
                if b:
                    ax.plot(b[0], b[2], "s", mfc="none", mec=COL["light"])
                ax.text(a[0], a[2] + 8, "pitch %.1f" % c["meta"]["pitch_deg"], fontsize=7)
            if c["what"] == "UPLIGHT_BODY_TO_FLOOR" and kind != "DEAD_BULB_TO_FLOOR" and \
                    any(x["what"] == "UPLIGHT_LIGHT_TO_FLOOR" and x["label"].endswith(kind) for x in t["changes"]):
                _outline(ax, _box_pts(c["after"]["relative_transform"], *c["meta"]["bounds"]), 0, 2, color=COL["body"])
        ax.set_xlim(-200, 60)
        ax.set_ylim(-20, 280)
        ax.set_aspect("equal")
        ax.set_title("%s: %s (side view, x-z)" % (t["cue_label"], kind), fontsize=9)
    fig.tight_layout()
    elev = os.path.join(out_dir, "%s_elevation_%s.png" % (stem, tag))
    fig.savefig(elev, dpi=80)
    plt.close(fig)
    return [top, elev]


if __name__ == "__main__":
    path = sys.argv[1]
    with open(path, encoding="utf-8") as handle:
        report = json.load(handle)
    tag = "%s_%s" % (report["mode"], report["run"])
    stem = "%s_%s" % (report["passage"].lower(), "floor" if report["op"] == "FLOOR" else "addup")
    print(chr(10).join(render(report["plan"], os.path.dirname(os.path.abspath(path)), tag, stem)))
