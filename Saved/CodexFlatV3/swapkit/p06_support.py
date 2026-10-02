"""P06-only mapping adapter for the unchanged shared Flat V3 swapkit."""
import json
import os

import unreal


P02_ROOT = "/Game/Scenes/Wings/FlatV3/Passage02"


def _asset_exists(path):
    return isinstance(unreal.EditorAssetLibrary.load_asset(path), unreal.StaticMesh)


def _mesh_name(panel):
    return (panel.get("mesh") or "").rsplit("/", 1)[-1]


def _validate_family(name, family):
    if family is None:
        raise RuntimeError("P06_FAMILY_MISSING|" + str(name))
    if family.get("pair_status") != "true_pair":
        raise RuntimeError("P06_FAMILY_NOT_TRUE_PAIR|family=%s|status=%s" %
                           (name, family.get("pair_status")))
    if not family.get("left_asset") or not family.get("right_asset"):
        raise RuntimeError("P06_PAIR_ASSET_MISSING|family=" + str(name))
    if family["left_asset"] == family["right_asset"]:
        raise RuntimeError("P06_PAIR_COLLAPSED|family=" + str(name))


def load_mapping(common, config):
    with open(config["mapping_file"], encoding="utf-8") as handle:
        doc = json.load(handle)
    if config.get("mapping_kind") != "p06_layout" or config.get("passage") != "P06":
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|wrong_config")
    rows = doc.get("occurrences", [])
    families = doc.get("family_catalog", {})
    if len(rows) != 55:
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|occurrences=%d" % len(rows))
    if [int(row.get("ordinal", 0)) for row in rows] != list(range(1, 56)):
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|ordinal_sequence")
    if [int(row.get("row_index", -1)) for row in rows] != list(range(217, 272)):
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|row_index_sequence")
    expected_labels = ["P06 Wing %03d" % value for value in range(1, 56)]
    labels = [str(row.get("label")) for row in rows]
    if labels != expected_labels or len(labels) != len(set(labels)):
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|label_sequence_or_duplicate")
    swap_rows = [row for row in rows if row.get("action") == "swap"]
    keep_rows = [row for row in rows if row.get("action") == "keep"]
    if ([row["ordinal"] for row in swap_rows] != list(range(1, 33)) or
            [row["ordinal"] for row in keep_rows] != list(range(33, 56))):
        raise RuntimeError("P06_LAYOUT_CONTRACT_FAIL|swap_keep_boundary")
    for row in rows:
        if row.get("top") != "keep":
            raise RuntimeError("P06_TOP_MUST_KEEP|ordinal=%s" % row.get("ordinal"))
        if row.get("action") == "keep":
            if row.get("left_family") is not None or row.get("right_family") is not None:
                raise RuntimeError("P06_KEEP_HAS_FAMILY|ordinal=%s" % row.get("ordinal"))
            continue
        left_family = row.get("left_family")
        right_family = row.get("right_family")
        if left_family != right_family:
            raise RuntimeError("P06_MIXED_FAMILY_POSITION|ordinal=%s|left=%s|right=%s" %
                               (row.get("ordinal"), left_family, right_family))
        _validate_family(left_family, families.get(left_family))
    return {"kind": "p06_layout", "families": families, "occurrences": rows,
            "swap_count": len(swap_rows), "keep_count": len(keep_rows),
            "rules": doc.get("rules", {})}


def _industrial_root(common, config, mapping):
    names = sorted({family[side]
                    for family in mapping["families"].values()
                    if family.get("kind") == "p02_industrial" and
                    family.get("pair_status") == "true_pair"
                    for side in ("left_asset", "right_asset")})
    p02_paths = [P02_ROOT + "/StaticMeshes/" + name for name in names]
    p06_paths = [common.destination_mesh(config, name) for name in names]
    p02_state = [_asset_exists(path) for path in p02_paths]
    p06_state = [_asset_exists(path) for path in p06_paths]
    if names and all(p02_state):
        if any(p06_state):
            raise RuntimeError("P06_INDUSTRIAL_DUPLICATE_ROOTS")
        return P02_ROOT
    if any(p02_state):
        raise RuntimeError("P06_INDUSTRIAL_PARTIAL_P02_STATE")
    if names and all(p06_state):
        return config["destination_root"].rstrip("/")
    if any(p06_state):
        raise RuntimeError("P06_INDUSTRIAL_PARTIAL_P06_STATE")
    raise RuntimeError("P06_INDUSTRIAL_SET_MISSING")


def desired_meshes(common, config, mapping, label, ordinal, originals):
    if mapping.get("kind") != "p06_layout":
        raise RuntimeError("P06_MAPPING_KIND_FAIL|" + str(mapping.get("kind")))
    if ordinal >= len(mapping["occurrences"]):
        raise RuntimeError("P06_MAPPING_OCCURRENCE_MISSING|ordinal=" + str(ordinal))
    row = mapping["occurrences"][ordinal]
    if (int(row["ordinal"]) != ordinal + 1 or
            int(row["row_index"]) != int(originals["cue_index"]) or
            str(row["label"]) != label):
        raise RuntimeError("P06_MAPPING_IDENTITY_FAIL|ordinal=%d|index=%s|label=%s" %
                           (ordinal, originals["cue_index"], label))
    for short, side in (("L", "left"), ("R", "right")):
        expected = str(row["existing"][short])
        actual = _mesh_name(originals[side])
        if actual != expected:
            raise RuntimeError("P06_EXISTING_IDENTITY_FAIL|label=%s|side=%s|expected=%s|actual=%s" %
                               (label, side, expected, actual))
    result = {side: originals[side]["mesh"] for side in ("left", "right", "top")}
    if row["action"] == "keep":
        return result, [], []
    left_family = row["left_family"]
    right_family = row["right_family"]
    if left_family != right_family:
        raise RuntimeError("P06_MIXED_FAMILY_POSITION|ordinal=%d" % (ordinal + 1))
    family = mapping["families"].get(left_family)
    _validate_family(left_family, family)
    if family["kind"] == "p02_industrial":
        root = _industrial_root(common, config, mapping)
        result["left"] = root + "/StaticMeshes/" + family["left_asset"]
        result["right"] = root + "/StaticMeshes/" + family["right_asset"]
    elif family["kind"] == "p06_flat":
        result["left"] = common.destination_mesh(config, family["left_asset"])
        result["right"] = common.destination_mesh(config, family["right_asset"])
    else:
        raise RuntimeError("P06_FAMILY_KIND_NOT_IMPORTABLE|family=%s|kind=%s" %
                           (left_family, family.get("kind")))
    return result, ["left", "right"], []


def install(common):
    """Patch one already-loaded shared common module for the P06 binding only."""
    common.load_mapping = lambda config: load_mapping(common, config)
    common.desired_meshes = lambda config, mapping, label, ordinal, originals: desired_meshes(
        common, config, mapping, label, ordinal, originals)
    return common

