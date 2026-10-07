"""Offline preview of the proposed bulb placement per passage (after SCALE x3, then RELOCATE), for Gary to approve.

  python fixtures_preview.py [P01 ...]     -> previews/<P>_topdown.png, previews/<P>_routecam.png, previews/summary.json
  python fixtures_preview.py --from-dry <fixfollow_relocate_report_P0N_DRY_*.json>   (exact plan from a live DRY)

SCHEMATIC, not a render (inferred, per AGENTS.md tiers):
* bays are unrolled on a straight line at a NOMINAL pitch (BAY_PITCH_CM) because station distances are not in any file;
  positions INSIDE a bay are the plan's own route-relative (pair-frame) numbers -- exact;
* floor at pair z = 0; the wet-floor reflection is drawn as a mirror image (z -> -z) at 35 % opacity -- the idea of
  what a glossy floor returns, not a Lumen result;
* route camera: pinhole, 60 deg horizontal FOV, 60 cm above the floor on the lane centre, looking down the route.
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
OUT = os.path.join(HERE, "previews")
BAY_PITCH_CM = 600.0
F = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "fixtures_common.py"), run_name="_fc_preview"))

COLOURS = {"BULB_HANG": "#3b82f6", "BULB_GROUND_LYING": "#f59e0b", "BULB_GROUND_STANDING": "#d97706",
           "GLIMMER_TO_BULB_HANG": "#db2777", "GLIMMER_TO_BULB_GROUND": "#db2777"}


def apply_changes(cues, plan):
    rows = {c["guid"]: c for t in plan["targets"] for c in t["changes"]}
    out = []
    for cue in cues:
        new = dict(cue)
        new["attachments"] = [dict(rows[r["guid"]]["after"], ext=r.get("ext")) if r["guid"] in rows else r
                              for r in cue["attachments"]]
        out.append(new)
    return out


def plan_for(passage, table):
    cues, meta = F.snapshot_passage(passage)
    h = meta["meshy_housing"]
    sp = F.scale_plan(passage, cues, table, meta["derived_index"], {"lantern": h["lantern"], "body_size_cm": h["body_size_cm"]},
                      F.SCALE_DEFAULTS)
    scaled = apply_changes(cues, sp)
    rp = F.relocate_plan(passage, scaled, table, meta["derived_index"], F.RELOCATE_DEFAULTS)
    return scaled, rp, sp


def bulb_items(plan, cues, table):
    order = {c["guid"]: i for i, c in enumerate(cues)}
    items = []
    for t in plan["targets"]:
        bay = order.get(t["cue_guid"], 0)
        cords = {c["guid"]: c for c in t["changes"] if "CORD" in c["what"]}
        for c in t["changes"]:
            if c["what"] not in COLOURS:
                continue
            variant = c.get("variant")
            s = c["after"]["relative_transform"]["scale"][0]
            fx = table[variant]
            items.append({"bay": bay, "cue": t["cue_label"], "what": c["what"], "x": c["glass"][0], "y": c["glass"][1],
                          "z": c["glass"][2] if "HANG" in c["what"] else fx["glass_width"] * s * 0.5,
                          "r": fx["glass_width"] * s * 0.5, "label": c["label"]})
        for c in cords.values():
            tr = c["after"]["relative_transform"]
            lo, hi = plan["cord_bounds"]
            items.append({"bay": bay, "what": "CORD", "x": tr["location"][0], "y": tr["location"][1],
                          "z0": tr["location"][2] + lo[2] * tr["scale"][2], "z1": tr["location"][2] + hi[2] * tr["scale"][2]})
    return items


def housed(cues):
    out = []
    for i, cue in enumerate(cues):
        for r in cue["attachments"]:
            if F.is_kind(r, "LIGHT") and r["enabled"] and F.is_station(r):
                loc = r["relative_transform"]["location"]
                out.append((i, loc[0], loc[1], loc[2], r["label"].split(" ")[-1]))
    return out


def topdown(passage, cues, plan, items, path, bays_per_row=12):
    n = len(cues)
    rows = max(1, math.ceil(n / bays_per_row))
    fig, axes = plt.subplots(rows, 1, figsize=(18, 3.2 * rows), squeeze=False)
    lane, lat = plan["opts"]["lane_half_width_cm"], plan["opts"]["lateral_max_cm"]
    lights_after = housed(apply_changes(cues, plan))
    for r in range(rows):
        ax = axes[r][0]
        b0, b1 = r * bays_per_row, min(n, (r + 1) * bays_per_row)
        x0, x1 = b0 * BAY_PITCH_CM - 400, b1 * BAY_PITCH_CM
        ax.add_patch(Rectangle((x0, -lane), x1 - x0, 2 * lane, color="#e5e7eb", zorder=0))
        for s in (-1, 1):
            ax.axhline(s * lat, color="#9ca3af", lw=0.6, ls="--")
        for bay in range(b0, b1):
            ax.axvline(bay * BAY_PITCH_CM, color="#d1d5db", lw=0.5)
            ax.text(bay * BAY_PITCH_CM, 1480, cues[bay]["label"].replace("Wing ", "W"), fontsize=6, ha="center")
        for bay, x, y, z, role in lights_after:
            if b0 <= bay < b1:
                ax.plot(bay * BAY_PITCH_CM + x, y, "s", ms=3, color="#6b7280", alpha=0.6)
        for it in items:
            if not (b0 <= it["bay"] < b1) or it["what"] == "CORD":
                continue
            ax.add_patch(plt.Circle((it["bay"] * BAY_PITCH_CM + it["x"], it["y"]), max(it["r"], 12),
                                    color=COLOURS[it["what"]], alpha=0.85))
        ax.set_xlim(x0, x1)
        ax.set_ylim(-1550, 1550)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=6)
    axes[0][0].set_title("%s proposed bulbs (schematic top-down; bays unrolled at %d cm): blue hang, amber ground, pink "
                         "ex-glimmer; grey squares = housed lights AFTER (lanterns that remain); grey band = camera lane"
                         % (passage, BAY_PITCH_CM), fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def routecam(passage, cues, plan, items, path, bays_ahead=7):
    cam = [-350.0, 0.0, 60.0]
    f = 1.0 / math.tan(math.radians(30.0))
    W, H = 1600, 900

    def proj(p):
        d = p[0] - cam[0]
        if d < 30.0:
            return None
        return (W / 2 + f * (p[1] - cam[1]) / d * W / 2, H / 2 - f * (p[2] - cam[2]) / d * W / 2, d)

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#0b0b10")
    ax.set_facecolor("#0b0b10")
    for yline in (-600, -plan["opts"]["lateral_max_cm"], plan["opts"]["lateral_max_cm"], 600):
        a, b = proj([0, yline, 0]), proj([bays_ahead * BAY_PITCH_CM, yline, 0])
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#374151", lw=0.8)
    for bay in range(bays_ahead + 1):
        a, b = proj([bay * BAY_PITCH_CM, -700, 0]), proj([bay * BAY_PITCH_CM, 700, 0])
        if a and b:
            ax.plot([a[0], b[0]], [a[1], b[1]], color="#1f2937", lw=0.6)
        top = proj([bay * BAY_PITCH_CM, -1350, plan["cord_top_z_cm"]]), proj([bay * BAY_PITCH_CM, 1350, plan["cord_top_z_cm"]])
        if top[0] and top[1]:
            ax.plot([top[0][0], top[1][0]], [top[0][1], top[1][1]], color="#4b5563", lw=1.5)
    drawn = sorted([it for it in items if it["bay"] <= bays_ahead], key=lambda it: -(it["bay"] * BAY_PITCH_CM + it["x"]))
    for it in drawn:
        wx = it["bay"] * BAY_PITCH_CM + it["x"]
        if it["what"] == "CORD":
            a, b = proj([wx, it["y"], it["z0"]]), proj([wx, it["y"], it["z1"]])
            if a and b:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#6b7280", lw=0.7)
            continue
        p = proj([wx, it["y"], it["z"]])
        m = proj([wx, it["y"], -it["z"]])
        if not p:
            continue
        rad = f * it["r"] / p[2] * W / 2
        c = COLOURS[it["what"]]
        ax.add_patch(plt.Circle((p[0], p[1]), max(rad, 1.5), color="#fde68a", alpha=0.95))
        ax.add_patch(plt.Circle((p[0], p[1]), max(rad, 1.5) * 1.8, color=c, alpha=0.18))
        if m:
            ax.add_patch(plt.Circle((m[0], m[1]), max(rad, 1.5), color="#fde68a", alpha=0.35))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("%s route camera (schematic pinhole, 60 cm high, first %d bays): bulbs + mirrored wet-floor reflections; "
                 "top line = crossbeam underside the cords hang from" % (passage, bays_ahead), fontsize=9, color="white")
    fig.tight_layout()
    fig.savefig(path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def main(argv):
    os.makedirs(OUT, exist_ok=True)
    table = F.M.load_fixture_table(check_files=False)
    passages = [a for a in argv if a in F.PASSAGES] or list(F.PASSAGES)
    summary = {"schematic": True, "bay_pitch_cm_nominal": BAY_PITCH_CM, "passages": {}}
    for p in passages:
        cues, rp, sp = plan_for(p, table)
        items = bulb_items(rp, cues, table)
        topdown(p, cues, rp, items, os.path.join(OUT, "%s_topdown.png" % p))
        routecam(p, cues, rp, items, os.path.join(OUT, "%s_routecam.png" % p))
        summary["passages"][p] = {"relocate_counts": rp["counts"], "bulb_scale_after_scale": sp["opts"]["expected_bulb_scale"] * sp["opts"]["bulb_factor"],
                                  "glimmer_bulb_scale": rp["glimmer_bulb_scale"], "plan_sha256_offline": F.plan_sha(rp)}
        print("FIXPREVIEW|%s|%s" % (p, json.dumps(rp["counts"]["by_kind"], sort_keys=True)))
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, sort_keys=True)
    print("FIXPREVIEW_OK|%s" % OUT)


if __name__ == "__main__":
    main(sys.argv[1:])
