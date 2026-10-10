"""Pure-Python positive and required negative controls for job 56."""
from __future__ import annotations

import os
import sys

from p56_chandelier_candles import (
    OWNER_TAG,
    P56Error,
    build_plan,
    parse_socket_document,
    select_revert_labels,
    validate_args,
)


def sockets(count=3):
    return {"schema": "chandelier_sockets_v1", "units": "cm", "sockets": [
        {"name": "Candle_%02d" % index,
         "location_cm": [index * 10.0, 0.0, 100.0],
         "rotation_deg": [0.0, 0.0, 0.0]}
        for index in range(1, count + 1)
    ]}


def args(mode="DRY", confirm=""):
    return {
        "mode": mode,
        "confirm": confirm,
        "actor_label": "Rodin Chandelier Iron2",
        "socket_json": "D:/review/chandelier_Iron2_sockets.json",
    }


def negative(name, function):
    try:
        function()
    except P56Error:
        print("PASS negative %s" % name)
        return 0
    print("FAIL negative %s" % name)
    return 1


def main():
    failures = 0
    positive = 0
    rows = parse_socket_document(sockets())
    if [row["name"] for row in rows] == ["Candle_01", "Candle_02", "Candle_03"]:
        positive += 1
        print("PASS positive socket parsing")
    else:
        failures += 1

    valid = validate_args(args())
    plan = build_plan(valid, rows)
    if (len(plan["placements"]) == 3 and plan["component_auto_activate"] is False
            and plan["uses_point_light"] is False and plan["flame_scale"] == [0.035] * 3):
        positive += 1
        print("PASS positive plan builder")
    else:
        failures += 1

    actor_rows = [
        {"label": "wanted", "tags": [OWNER_TAG, "P56_TARGET_Rodin_Chandelier_Iron2"]},
        {"label": "other-job", "tags": ["P55"]},
        {"label": "other-target", "tags": [OWNER_TAG, "P56_TARGET_Other"]},
    ]
    selected = select_revert_labels(
        actor_rows, [OWNER_TAG, "P56_TARGET_Rodin_Chandelier_Iron2"])
    if selected == ["wanted"]:
        positive += 1
        print("PASS positive exact REVERT tag selection")
    else:
        failures += 1

    failures += negative("no sockets", lambda: parse_socket_document({"sockets": []}))
    failures += negative("missing BP_Effect_Candle", lambda: validate_args(args(), source_exists=False))
    failures += negative("non-chandelier actor", lambda: validate_args({
        "mode": "DRY", "actor_label": "SM_Table", "socket_json": "sockets.json"}))
    failures += negative("APPLY without confirm", lambda: validate_args(args("APPLY")))

    source = open(os.path.join(os.path.dirname(__file__), "p56_chandelier_candles.py"),
                  "r", encoding="utf-8").read()
    if ("BlueprintEditorLibrary.get_blueprint_parent_class(bp)" in source
            and 'get_editor_property("parent_class")' not in source
            and "isinstance(cdo, source_class)" not in source
            and ".is_child_of(source_class)" not in source
            and "actor.get_root_component()" not in source):
        positive += 1
        print("PASS positive UE5.8 parent/root API contract")
    else:
        failures += 1

    if failures == 0:
        print("P56_CHANDELIER_HARNESS_OK|positive=%d|negative=4" % positive)
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
