"""Preview of a P01 note-lamps plan (Saved/CodexConductor/p01_note_lamps_plan.json). Offline only.

Usage: python note_lamps_preview.py <plan.json> <out.png>

Three panels:
  1. Notes: every onset (grey, by pitch), notable ones (ringed), chosen ones coloured by behaviour,
     Gary's marks as dashed lines.
  2. Lamp response over time: each chosen lamp's intensity scale (port of the held patch's EvaluateFlash,
     plus strike when the plan keeps it), stacked per lamp, labelled bay/role.
  3. Top-down: the P01 route (x = route distance m, y = lateral m), every eligible lamp grey, chosen lamps
     coloured by behaviour (size = number of notes), and the camera position at each chosen note joined to
     the lamp it fires (shows the 15-45 m look-ahead).
The route used is the plan's own (INFERRED model in PLAN mode, live compiled law in DRY).
"""
import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLOURS = {"glint": "#e8a33d", "bloom": "#d1495b", "stay": "#2e86ab"}


def interp(t, a_t, a_d, b_t, b_d):
    if b_t <= a_t:
        return b_d
    alpha = min(1.0, max(0.0, (t - a_t) / (b_t - a_t)))
    return a_d + (b_d - a_d) * alpha


def distance_at(route, t):
    wings = route["wings"]
    if t <= route["first_pass_s"]:
        return interp(t, route["segment_start_s"], 0.0, route["first_pass_s"], route["first_pass_cm"])
    for a, b in zip(wings, wings[1:]):
        if t <= b["pass_s"]:
            return interp(t, a["pass_s"], a["distance_cm"], b["pass_s"], b["distance_cm"])
    return interp(t, route["last_pass_s"], route["last_pass_cm"], route["segment_end_s"], route["total_cm"])


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def level(drama, lamp_cm, cam_cm):
    scale = 1.0
    if drama.get("strike_on_approach"):
        ahead = lamp_cm - cam_cm
        start = max(0.0, float(drama["strike_distance_cm"]))
        unstruck = float(drama.get("unstruck_intensity_scale") or 0.0)
        scale = unstruck
        if ahead <= start:
            scale = unstruck + (1 - unstruck) * smoothstep((start - ahead) / max(1.0, float(drama["strike_ramp_cm"])))
    if drama.get("flash"):
        past = cam_cm - lamp_cm
        attack = max(0.1, float(drama["flash_attack_cm"]))
        decay = max(0.1, float(drama["flash_decay_cm"]))
        lv = float(drama.get("flash_rest_scale") or 0.0)
        for off in drama["flash_camera_offsets_cm"]:
            d = past - off
            if -attack <= d < 0:
                lv = max(lv, (d + attack) / attack)
            elif 0 <= d <= decay:
                lv = max(lv, (1 - d / decay) ** 3)
        scale *= lv
    return scale


def main(plan_path, out_path):
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    route = plan["route"]
    events = plan["events"]
    targets = plan["targets"]
    t0, t1 = plan["window_s"]
    fig, axes = plt.subplots(3, 1, figsize=(16, 15), gridspec_kw={"height_ratios": [1.0, 1.5, 1.4]})

    # 1. notes
    ax = axes[0]
    notes = [n for n in plan["notes"] if t0 - 1 <= n["show_s"] <= t1 + 1]
    ax.scatter([n["show_s"] for n in notes], [n["midi"] for n in notes], s=6, c="#bbbbbb", zorder=1)
    nb = [n for n in notes if n["notable"]]
    ax.scatter([n["show_s"] for n in nb], [n["midi"] for n in nb], s=30, facecolors="none", edgecolors="#777777", zorder=2)
    for b, col in COLOURS.items():
        ev = [e for e in events if e["behaviour"] == b]
        ax.scatter([e["show_s"] for e in ev], [e["midi"] for e in ev], s=70, c=col, label="%s (%d)" % (b, len(ev)), zorder=3)
    for m in plan["must"]:
        mark = m["mark"]
        if isinstance(mark, list):
            ax.axvspan(mark[0], mark[1], color="#2a9d8f", alpha=0.12)
        else:
            ax.axvline(mark, color="#2a9d8f", ls="--", lw=1)
    ax.set_xlim(t0 - 1, t1 + 1)
    ax.set_ylabel("MIDI (approx)")
    ax.set_title("P01 note lamps: %d notes chosen of %d requested (%s route; dashed = Gary's marks)"
                 % (plan["selected_count"], plan["requested_count"], plan["route_basis"]))
    ax.legend(loc="upper right")
    sec = ax.secondary_xaxis("top", functions=(lambda s: s, lambda s: s))
    sec.set_xticks(range(int(t0) // 10 * 10, int(t1) + 10, 10))
    sec.set_xticklabels(["%d:%02d" % (v // 60, v % 60) for v in range(int(t0) // 10 * 10, int(t1) + 10, 10)])

    # 2. lamp traces
    ax = axes[1]
    steps = 1600
    ts = [t0 + (t1 - t0) * i / (steps - 1) for i in range(steps)]
    cams = [distance_at(route, t) for t in ts]
    order = sorted(targets, key=lambda t: t["notes_show_s"][0])
    for row, t in enumerate(order):
        drama = dict(t["drama_context"])
        drama.update(t["drama_after"])
        lv = [level(drama, t["lamp_route_cm"], c) for c in cams]
        base = row * 1.15
        col = COLOURS[t["behaviour"]]
        ax.fill_between(ts, base, [base + v for v in lv], color=col, alpha=0.75, lw=0)
        ax.text(t0 - 0.5, base + 0.3, "B%02d %s" % (t["ordinal"], t["role"]), ha="right", fontsize=7)
        passed = [ts[i] for i in range(steps) if cams[i] >= t["lamp_route_cm"]]
        if passed:
            ax.plot([passed[0]], [base + 0.5], marker="|", color="k", ms=9)
    ax.set_xlim(t0 - 1, t1 + 1)
    ax.set_yticks([])
    ax.set_xlabel("show time (s); black tick = camera passes the lamp")
    ax.set_title("Lamp intensity scale (held-patch EvaluateFlash port), one row per chosen lamp")

    # 3. top-down
    ax = axes[2]
    el = plan["eligible_lamps"]
    ax.scatter([l["route_cm"] / 100 for l in el], [l["y_cm"] / 100 for l in el], s=8, c="#cccccc")
    for w in route["wings"]:
        ax.axvline(w["distance_cm"] / 100, color="#eeeeee", lw=0.6, zorder=0)
    by_guid = {t["attachment_guid"]: t for t in targets}
    for e in events:
        t = by_guid[e["lamp_guid"]]
        ax.plot([e["camera_cm"] / 100, t["lamp_route_cm"] / 100], [0, t["y_cm"] / 100],
                color=COLOURS[e["behaviour"]], alpha=0.35, lw=0.8)
        ax.scatter([e["camera_cm"] / 100], [0], marker="^", c="k", s=14)
    for t in targets:
        ax.scatter([t["lamp_route_cm"] / 100], [t["y_cm"] / 100], s=50 + 50 * len(t["notes_show_s"]),
                   c=COLOURS[t["behaviour"]], edgecolors="k", zorder=3)
        ax.annotate("B%02d" % t["ordinal"], (t["lamp_route_cm"] / 100, t["y_cm"] / 100), fontsize=6,
                    xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("route distance (m); triangles = camera at each chosen note")
    ax.set_ylabel("lateral y (m)")
    ax.set_title("Top-down P01: grey = eligible lamps, coloured = chosen (size = notes), lines = camera -> lamp")
    fig.tight_layout()
    fig.savefig(out_path, dpi=110)
    print("NOTE_LAMPS_PREVIEW_OK|%s" % out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
