"""Write new Fuser job folders (SLOTS.md in the house §§ format) from a Python spec. Never overwrites an existing job."""
import datetime
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2] / "DerivedAssets" / "FlatV3" / "FuserQueue"
BG = ("the subject complete and isolated on a plain flat background of colour #D6C8AA, touching no edge, "
      "with a clear gap all round (for cutting)")


def one_line(inp, task, hand, keep, avoid, frame):
    return " §§ ".join([inp, task, hand, keep, avoid, frame])


def pair(job_title, hand, subject_l, subject_r, avoid, aspect="portrait 1:2", style_ref=None):
    """L sub-job a (text or style ref) + R partner b fed with a's output."""
    a_inp = ("the supplied style reference image (an existing wing of this passage)" if style_ref
             else "no input image; an original stage wing is required")
    a = one_line(a_inp, "create one " + subject_l + "; the straight backbone on the image LEFT, the form reaching right",
                 hand, "one coherent vertical mass, final-handed LEFT wing, see-through gaps where natural",
                 avoid, BG + "; " + aspect)
    b = one_line("the final-handed LEFT wing from sub-job a", "create its independently designed RIGHT partner: " + subject_r +
                 "; backbone on the image RIGHT, reaching left", hand,
                 "the same family, palette and light; final-handed RIGHT wing", "a mirror copy; " + avoid, BG + "; " + aspect)
    return [("a: left" + (" (Image node: style reference)" if style_ref else ""), a),
            ("b: right partner (Image node: a's output)", b)]


def write_job(job_id, title, notes, subs, inputs=()):
    d = ROOT / job_id
    overwrite = job_id in os.environ.get("FUSER_OVERWRITE", "").split(",")
    if d.exists() and not overwrite:
        print("SKIP_EXISTS", job_id)
        return False
    if overwrite and (d / "SLOTS.md").exists():
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(d / "SLOTS.md", d / ("SLOTS.md.bak-" + stamp))
    (d / "results").mkdir(parents=True, exist_ok=True)
    lines = ["# %s" % title, "", notes, ""]
    if inputs:
        lines += ["Inputs (Image node, in order):"] + ["- %s" % i for i in inputs] + [""]
    for header, value in subs:
        lines += ["## %s" % header, "ONE-LINE:", value, ""]
    (d / "SLOTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("WROTE", job_id, len(subs))
    return True


def series8(job_id, title, notes, inp, task_stem, variants, hand, keep, avoid, frame):
    """Gary 5 Oct: his Fuser pipe runs 8 prompts per paste, split on '~~'. A series is one job whose prompts share
    every field except the varied subject, so the 8 outputs come back as one family. Writes SLOTS.md as usual plus
    BATCH8.txt (the paste-ready block, prompts joined by a '~~' line) in the job folder."""
    assert 1 <= len(variants) <= 8, "a series block holds at most 8 prompts"
    subs = [("%s: %s" % (chr(97 + i), v[0]), one_line(inp, task_stem + v[1], hand, keep, avoid, frame))
            for i, v in enumerate(variants)]
    assert not any("~~" in s for _, s in subs), "a prompt contains the block delimiter"
    if not write_job(job_id, title, notes, subs):
        return  # BATCH8.txt stays in step with the SLOTS.md it came from
    nl = chr(10)
    (ROOT / job_id / "BATCH8.txt").write_text((nl + "~~" + nl).join(s for _, s in subs) + nl, encoding="utf-8")
    print("BATCH8", job_id, len(subs))

if __name__ == "__main__":
    spec = sys.argv[1]
    exec(pathlib.Path(spec).read_text(encoding="utf-8"))
