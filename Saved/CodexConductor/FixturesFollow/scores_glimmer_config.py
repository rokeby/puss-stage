"""Offline: remove the PRACTICAL_GLIMMER instrument from lighting_scores.json so a future lighting-scores re-APPLY
does not re-create the glimmer lights + GLIMMER_BODY rows that FixturesFollow RELOCATE turns into bare bulbs.

  python scores_glimmer_config.py            DRY: prints the diff + validates the new config with the scores tool's own
                                            validate_scores (offline, as test_lighting_scores_apply.py does)
  python scores_glimmer_config.py APPLY      writes lighting_scores.json (backup lighting_scores.json.bak-<stamp>-
                                            preGlimmerRemoval first, read back + re-validated); refuses if already applied

Proof tiers:
* declaration-proven: the only PRACTICAL_GLIMMER instrument is in local_looks.GAP (lighting_scores.json:46-49 at 7 Oct);
  every look must keep >= 1 PRACTICAL (lighting_scores_apply.py:385, GAP keeps PRACTICAL_DEAD); a scores APPLY refuses
  while any "P0N SCORE" row exists (SCORE_ALREADY_PRESENT, lighting_scores_apply.py:1799-1802), so a re-apply always
  follows a REVERT, which restores the pre-score rows -- i.e. a re-apply ALSO discards the Meshy swap and every
  FixturesFollow change on score rows; they must be re-run afterwards regardless of this edit.
* measured: run DRY -> the validator passes on the edited config (printed below as SCORES_VALIDATE_OK).
"""
import copy
import datetime
import json
import os
import runpy
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONDUCTOR = os.path.dirname(HERE)
SCORES_PATH = os.path.join(CONDUCTOR, "lighting_scores.json")


def validate(new):
    sys.path.insert(0, CONDUCTOR)
    try:
        import lighting_scores_apply as L  # noqa: E402 - unreal is None offline -> its main() does not run
    finally:
        sys.path.pop(0)
    tool = L.load_p04_tool()
    base, unused = L.load_base_looks(new)
    looks = L.resolve_looks(new, base)
    return sorted(L.validate_scores(new, looks, tool))


def main(argv):
    F = types.SimpleNamespace(**runpy.run_path(os.path.join(HERE, "fixtures_common.py"), run_name="_fc"))
    mode = (argv[0] if argv else "DRY").upper()
    with open(SCORES_PATH, encoding="utf-8") as handle:
        raw = handle.read()
    scores = json.loads(raw)
    new, removed = F.scores_without_glimmer(scores)
    if not removed:
        print("SCORESGLIMMER_NOOP|already removed (no PRACTICAL_GLIMMER instrument in any local look)")
        return 0
    passages = validate(new)
    print("SCORESGLIMMER_DIFF|removed=%s|validated_passages=%s" % (json.dumps(removed), passages))
    print("SCORES_VALIDATE_OK")
    if mode != "APPLY":
        print("SCORESGLIMMER_DRY_OK|nothing written")
        return 0
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = SCORES_PATH + ".bak-%s-preGlimmerRemoval" % stamp
    with open(backup, "x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
    with open(SCORES_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(new, handle, indent=2)
        handle.write("\n")
    with open(SCORES_PATH, encoding="utf-8") as handle:
        back = json.load(handle)
    if back != new or F.scores_without_glimmer(back)[1]:
        raise SystemExit("SCORESGLIMMER_STOPPED|READBACK_MISMATCH|backup=%s" % backup)
    validate(back)
    print("SCORESGLIMMER_APPLY_OK|written=%s|backup=%s" % (SCORES_PATH, backup))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
