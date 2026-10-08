"""Offline positive/negative harness for the deterministic timing preview."""
import json
import pathlib
import subprocess
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
run = subprocess.run([sys.executable, str(HERE / "make_p06_fx_preview.py")], capture_output=True, text=True)
checks = []


def check(name, condition): checks.append(bool(condition)); print(("PASS " if condition else "FAIL ") + name)


check("preview +: generator exits zero with marker", run.returncode == 0 and "P06FX_PREVIEW_OK" in run.stdout)
doc = json.loads((HERE / "p06_fx_preview_data.json").read_text(encoding="utf-8"))
check("preview +: explicitly not applied", doc["status"] == "not_applied")
check("preview +: domino impact exactly 37 s", any(e["name"] == "domino impact" and e["start"] == 37.0 for e in doc["events"]))
check("preview +: proposed motes/burn/fire present", {e["name"] for e in doc["events"] if e["kind"] == "proposal"} ==
      {"motes", "wing burn", "fire basket"})
check("preview +: applied bee glints represented", [e["start"] for e in doc["events"] if e["name"].startswith("bee")] == [80.0, 100.0, 118.0])
check("preview -control: candle is absent", all(e["name"] != "candle" for e in doc["events"]))
with Image.open(HERE / "p06_fx_preview.png") as im:
    check("preview +: 1800x980 RGB PNG", im.size == (1800, 980) and im.mode == "RGB" and im.format == "PNG")

failed = len(checks) - sum(checks)
print("P06FXPREVIEW_HARNESS|pass=%d|fail=%d" % (sum(checks), failed))
sys.exit(1 if failed else 0)
