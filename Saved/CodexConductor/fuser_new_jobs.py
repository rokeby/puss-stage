"""Write new Fuser job folders (SLOTS.md in the house §§ format) from a Python spec. Never overwrites an existing job."""
import json
import pathlib
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
    if d.exists():
        print("SKIP_EXISTS", job_id)
        return
    (d / "results").mkdir(parents=True)
    lines = ["# %s" % title, "", notes, ""]
    if inputs:
        lines += ["Inputs (Image node, in order):"] + ["- %s" % i for i in inputs] + [""]
    for header, value in subs:
        lines += ["## %s" % header, "ONE-LINE:", value, ""]
    (d / "SLOTS.md").write_text("\n".join(lines), encoding="utf-8")
    print("WROTE", job_id, len(subs))


if __name__ == "__main__":
    spec = sys.argv[1]
    exec(pathlib.Path(spec).read_text(encoding="utf-8"))
