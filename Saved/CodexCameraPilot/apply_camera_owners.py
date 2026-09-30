"""A.5: apply Gary's camera-owner decisions from camera_owner_plan.json.

Dry run unless the plan says "apply": true. The plan names each segment by its
exact label, so nothing is inferred:
    {"apply": false,
     "owners": {"Passage 1": "DOG_GAZE_ONLY", "Scene 1 — External Sound": "TIMELINE"}}
Allowed owners: TIMELINE, DOG_FREE_LOOK, DOG_GAZE_ONLY.

On apply: asserts the world, no PIE and zero dirty content; copies the Show
.uasset to Backups/PreCameraOwners-<timestamp>/; changes only the named
owners; asserts nothing else moved; saves only the Show.
Each change in the report carries the segment's GUID (cue_guid or passage_guid)
beside its label.
Everything runs inside main(): UE wrappers left in module globals crash the
editor when a script is re-run (MCP Python crash pattern 4).
Success markers: PUSS_CAMERA_OWNER_PLAN_DRY_RUN / PUSS_CAMERA_OWNER_PLAN_APPLIED
"""

import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
def main():
    OWNERS = {
        "TIMELINE": unreal.InfinityCameraOwner.TIMELINE,
        "DOG_FREE_LOOK": unreal.InfinityCameraOwner.DOG_FREE_LOOK,
        "DOG_GAZE_ONLY": unreal.InfinityCameraOwner.DOG_GAZE_ONLY,
    }

    saved_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    project_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    plan_path = os.path.join(saved_dir, "CodexCameraPilot", "camera_owner_plan.json")
    with open(plan_path, encoding="utf-8") as handle:
        plan = json.load(handle)
    apply = plan.get("apply") is True
    decided_by = str(plan.get("decided_by", "")).strip()
    wanted = plan.get("owners", {})
    if apply and not decided_by:
        raise RuntimeError("apply=true needs \"decided_by\": whose decision this is (A.5 is Gary's)")
    bad = {label: owner for label, owner in wanted.items() if owner not in OWNERS}
    if bad:
        raise RuntimeError(f"Unknown owners in plan: {bad}")

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
        raise RuntimeError("Unexpected editor world")
    if editor.get_game_world() is not None:
        raise RuntimeError("PIE/SIE is active")


    def dirty_content():
        return sorted(p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())


    show = unreal.load_asset(SHOW_PATH)
    if show is None:
        raise RuntimeError("Show asset did not load")
    cues = list(show.get_editor_property("cues"))
    passages = list(show.get_editor_property("passage_settings"))

    # Every segment that carries an owner, by exact label.
    slots = {}
    for index, settings in enumerate(passages):
        slots.setdefault(str(settings.get_editor_property("label")), []).append(("passage", index))
    for index, cue in enumerate(cues):
        if cue.get_editor_property("type") != unreal.InfinityCueType.WING_PAIR:
            slots.setdefault(str(cue.get_editor_property("label")), []).append(("cue", index))

    missing = [label for label in wanted if label not in slots]
    ambiguous = [label for label in wanted if len(slots.get(label, [])) > 1]
    if missing or ambiguous:
        raise RuntimeError(f"Plan labels must match exactly one segment; missing={missing} ambiguous={ambiguous}")


    def read_owner(kind, index, cue_list, passage_list):
        if kind == "passage":
            return passage_list[index].get_editor_property("camera_owner")
        return cue_list[index].get_editor_property("scene").get_editor_property("camera_owner")


    changes = []
    for label, owner_name in wanted.items():
        kind, index = slots[label][0]
        before = read_owner(kind, index, cues, passages)
        if before != OWNERS[owner_name]:
            source_list = passages if kind == "passage" else cues
            guid_field = "passage_guid" if kind == "passage" else "cue_guid"
            guid = unreal.GuidLibrary.conv_guid_to_string(source_list[index].get_editor_property(guid_field))
            changes.append({"label": label, "guid": guid, "kind": kind, "index": index,
                            "before": str(before), "after": owner_name})

    if not apply or not changes:
        unreal.log(f"PUSS_CAMERA_OWNER_PLAN_DRY_RUN|apply={int(apply)}|changes={json.dumps(changes)}")
    else:
        if dirty_content():
            raise RuntimeError(f"Content is already dirty; refusing to write: {dirty_content()}")
        source = os.path.join(project_dir, "Content", "InfinityStage", "Dev", "DA_InfinityStage_V1Show.uasset")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = os.path.join(project_dir, "Backups", f"PreCameraOwners-{stamp}")
        os.makedirs(backup_dir, exist_ok=False)
        shutil.copy2(source, backup_dir)

        snapshot = {slot: str(read_owner(slot[0], slot[1], cues, passages)) for entries in slots.values() for slot in entries}
        for change in changes:
            target = OWNERS[change["after"]]
            if change["kind"] == "passage":
                settings = passages[change["index"]]
                settings.set_editor_property("camera_owner", target)
                passages[change["index"]] = settings
            else:
                cue = cues[change["index"]]
                scene = cue.get_editor_property("scene")
                scene.set_editor_property("camera_owner", target)
                cue.set_editor_property("scene", scene)
                cues[change["index"]] = cue
        if any(c["kind"] == "passage" for c in changes):
            show.set_editor_property("passage_settings", passages)
        if any(c["kind"] == "cue" for c in changes):
            show.set_editor_property("cues", cues)

        cues_after = list(show.get_editor_property("cues"))
        passages_after = list(show.get_editor_property("passage_settings"))
        if len(cues_after) != len(cues) or len(passages_after) != len(passages):
            raise RuntimeError("Cue or Passage count changed")
        expected = dict(snapshot)
        for change in changes:
            expected[(change["kind"], change["index"])] = str(OWNERS[change["after"]])
        for slot, owner in expected.items():
            after = str(read_owner(slot[0], slot[1], cues_after, passages_after))
            if after != owner:
                raise RuntimeError(f"{slot}: owner is {after}, expected {owner}")
        if dirty_content() != [SHOW_PATH]:
            raise RuntimeError(f"Unexpected dirty content before save: {dirty_content()}")
        if not unreal.EditorAssetLibrary.save_asset(SHOW_PATH, only_if_is_dirty=False):
            raise RuntimeError("Show save failed")
        if dirty_content():
            raise RuntimeError(f"Content still dirty after save: {dirty_content()}")
        unreal.log(
            f"PUSS_CAMERA_OWNER_PLAN_APPLIED|decided_by={decided_by}|changes={json.dumps(changes)}|backup={backup_dir}"
        )


main()
