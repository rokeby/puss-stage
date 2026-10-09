"""Pure planning helpers for Codex job 96 (P04 -> S4 dark hard cut).

This module imports no Unreal symbols.  The offline harness exercises the same
state validation used by the editor adapter.
"""
from __future__ import annotations

import hashlib
import json
import re


SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_04"
COPY = "/Game/InfinityStage/KlaraHookin/LS_Children_S4Hangar"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ENTRY = "Scene 4 — External Sound — Entry Handoff Camera"
GLIDE = "Klara Reveal - S4 Reveal Glide Camera"
EXIT = "Scene 4 — External Sound — Exit Handoff Camera"
CURTAIN = "P04 Backcloth (baked)"
EXPECTED_END = 4890
EXPECTED_CUT = 405


class PlanError(ValueError):
    pass


def enum_name(value):
    """Normalise UE enums without trusting str(enum)'s '<E.V: n>' wrapper."""
    named = getattr(value, "name", None)
    if named:
        return str(named).split(".")[-1].upper()
    text = str(value)
    wrapped = re.match(r"^<[^.>]+\.([^:>]+):\s*[^>]+>$", text)
    return (wrapped.group(1) if wrapped else text.split(".")[-1]).upper()


def channel_base(value):
    """Channel names can carry numeric suffixes (Location.X_0, Visibility_2)."""
    return re.sub(r"_\d+$", "", str(value))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def overlaps(a, b):
    return int(a[0]) < int(b[1]) and int(a[1]) > int(b[0])


def _one(rows, field, value, reason):
    got = [row for row in rows if row.get(field) == value]
    if len(got) != 1:
        raise PlanError("%s|got=%d|want=1" % (reason, len(got)))
    return got[0]


def _track_action(target):
    wanted = list(target["range"])
    exact = []
    conflicts = []
    inert = []
    for row in target.get("visibility_tracks") or []:
        prop = row.get("property")
        if prop == "bHiddenInGame":
            inert.append(row)
            continue
        if prop != "bHidden":
            continue
        sections = row.get("sections") or []
        for section in sections:
            rng = list(section.get("range") or [])
            if not overlaps(rng, wanted):
                continue
            if (rng == wanted and section.get("default") is False
                    and not section.get("keys")
                    and section.get("completion") == "RESTORE_STATE"):
                exact.append(row)
            else:
                conflicts.append(row)
    if conflicts:
        raise PlanError("VISIBILITY_CONFLICT|%s|%s" %
                        (target.get("path"), canonical(conflicts)))
    if len(exact) > 1:
        raise PlanError("VISIBILITY_DUPLICATE_EXACT|%s|%d" %
                        (target.get("path"), len(exact)))
    return "already_dark" if exact else "add", inert


def plan_change(state):
    """Validate a live census and return a deterministic, minimal edit plan."""
    if state.get("world") != WORLD:
        raise PlanError("WORLD|got=%s" % state.get("world"))
    if state.get("scene") != SCENE or int(state.get("scene_end", -1)) != EXPECTED_END:
        raise PlanError("SCENE_OR_END|scene=%s|end=%s" %
                        (state.get("scene"), state.get("scene_end")))

    cuts = list(state.get("root_cuts") or [])
    entry = _one(cuts, "camera", ENTRY, "ENTRY_CUT_COUNT")
    glide = _one(cuts, "camera", GLIDE, "GLIDE_CUT_COUNT")
    exit_cut = _one(cuts, "camera", EXIT, "EXIT_CUT_COUNT")
    slots = [row for row in state.get("nested_slots") or []
             if row.get("sequence") == COPY and row.get("active")]
    if len(slots) != 1:
        raise PlanError("KLARA_SLOT_COUNT|got=%d|want=1" % len(slots))
    slot = slots[0]
    cut = int(slot["range"][0])
    if cut != EXPECTED_CUT:
        raise PlanError("CUT_FRAME|got=%d|want=%d" % (cut, EXPECTED_CUT))
    if (list(entry.get("range") or []) != [0, 119] or not entry.get("active")
            or list(glide.get("range") or []) != [119, 4865] or not glide.get("active")
            or list(exit_cut.get("range") or []) != [4865, EXPECTED_END]
            or not exit_cut.get("active")):
        raise PlanError("ROOT_CUT_BASELINE|%s" % canonical(cuts))
    if list(slot.get("range") or []) != [EXPECTED_CUT, 4500]:
        raise PlanError("KLARA_SLOT_RANGE|%s" % (slot.get("range"),))

    resolutions = list(state.get("cut_resolutions") or [])
    required = {"root_entry", "root_exit", "klara_at_cut"}
    names = {row.get("role") for row in resolutions}
    if names != required:
        raise PlanError("CUT_RESOLUTION_ROLES|got=%s" % sorted(names))
    for row in resolutions:
        if int(row.get("resolved_count", 0)) != 1:
            raise PlanError("CUT_BINDING_UNRESOLVED|role=%s|count=%s" %
                            (row.get("role"), row.get("resolved_count")))

    groups = state.get("target_groups") or {}
    expected_groups = {"p04_lights", "hangar_lights_and_emissives", "klara_precut", "curtain"}
    if set(groups) != expected_groups:
        raise PlanError("TARGET_GROUPS|got=%s" % sorted(groups))
    if not groups["p04_lights"]:
        raise PlanError("P04_LIGHTS_EMPTY")
    if not groups["hangar_lights_and_emissives"]:
        raise PlanError("HANGAR_DARK_TARGETS_EMPTY")
    if not groups["klara_precut"]:
        raise PlanError("KLARA_PRECUT_TARGETS_EMPTY")
    if len(groups["curtain"]) != 1:
        raise PlanError("CURTAIN_COUNT|got=%d|want=1" % len(groups["curtain"]))

    seen = {}
    actions = []
    inert = []
    for group in sorted(groups):
        for row in groups[group]:
            path = row.get("path")
            if not path:
                raise PlanError("TARGET_PATH_EMPTY|group=%s" % group)
            if path in seen:
                raise PlanError("TARGET_DUPLICATE|%s|%s|%s" % (path, seen[path], group))
            seen[path] = group
            action, ignored = _track_action(row)
            actions.append({"group": group, "path": path, "label": row.get("label"),
                            "range": list(row["range"]), "action": action,
                            "binding_guid": row.get("binding_guid")})
            inert.extend({"path": path, "track": item} for item in ignored)

    return {
        "scene": SCENE,
        "cut_frame": cut,
        "scene_end": EXPECTED_END,
        "camera": {
            "entry_section_index": entry["section_index"],
            "entry_before": entry,
            "entry_after_range": [0, cut],
            "glide_section_index": glide["section_index"],
            "glide_before": glide,
            "glide_after_active": False,
            "exit_unchanged": exit_cut,
            "slot_unchanged": slot,
        },
        "visibility": actions,
        "inert_tracks_reported": inert,
        "counts": {group: len(rows) for group, rows in groups.items()},
        "already_dark": sum(1 for row in actions if row["action"] == "already_dark"),
        "to_add": sum(1 for row in actions if row["action"] == "add"),
    }


def applied_state(plan, state):
    """Expected pure-state camera projection used by harness and live checks."""
    out = json.loads(json.dumps(state))
    cuts = out["root_cuts"]
    cuts[plan["camera"]["entry_section_index"]]["range"] = list(plan["camera"]["entry_after_range"])
    cuts[plan["camera"]["glide_section_index"]]["active"] = False
    return out
