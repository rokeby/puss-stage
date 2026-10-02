"""Pure tolerant full-occurrence comparator for C3 saved read-back."""
import sys as _fv3_sys, os as _fv3_os
if __name__ == "__main__":
    # purge this folder's cached modules: the editor's Python keeps modules across
    # scripts, so a stale verify/common ran (P06, 2 Oct). Entry scripts only.
    _fv3_here = _fv3_os.path.dirname(_fv3_os.path.abspath(__file__))
    for _fv3_name, _fv3_mod in list(_fv3_sys.modules.items()):
        _fv3_file = getattr(_fv3_mod, "__file__", None) or ""
        if (_fv3_name != "__main__" and _fv3_file and
                _fv3_os.path.dirname(_fv3_os.path.abspath(_fv3_file)) == _fv3_here):
            del _fv3_sys.modules[_fv3_name]


def facing_key(value):
    text = str(value).upper()
    for key in ("AUTO_BY_ROLE", "PRESERVE_ASSET", "ROTATE180_AROUND_UP"):
        if key in text:
            return key
    return text


def panel_matches(actual, expected, tolerance=0.001):
    scalar = ("mesh", "material_overrides", "flip_image_horizontally",
              "cast_shadow", "visible_in_main_pass", "collision")
    if any(actual.get(name) != expected.get(name) for name in scalar):
        return False
    if facing_key(actual.get("facing_policy")) != facing_key(expected.get("facing_policy")):
        return False
    for name in ("location", "rotation", "scale"):
        if any(abs(float(left) - float(right)) > float(tolerance)
               for left, right in zip(actual["local_transform"][name],
                                      expected["local_transform"][name])):
            return False
    return True


def occurrence_matches(actual, expected, tolerance=0.001):
    for name in ("cue_index", "cue_guid", "cue_label", "pair_invariants", "cue_invariants"):
        if actual.get(name) != expected.get(name):
            return False
    return all(panel_matches(actual[side], expected[side], tolerance)
               for side in ("left", "right", "top"))
