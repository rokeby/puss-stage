"""Offline: turn capture_settle_options.py's stills into what Gary sees on a phone. (30 Sep)

Writes to Captures/Settle/:
  settle_grid.mp4 / settle_grid.gif  the four options side by side, frame-exact, each panel stamped with
                                     its settle length, time to the cut and distance still to go;
  settle_chart.png                   distance-to-go and speed against time: all four curves meet at the
                                     same place at the same moment (the part Gary has not seen), and the
                                     settled options start AHEAD, which is the "slightly quicker
                                     beforehand" the span normalisation pays for.
If any ground check came back UNKNOWN, every file gets an _INTERNAL suffix instead. That output is for
checking the frames by eye, not for Gary. Needs Pillow; ffmpeg only encodes (its drawtext crashes here,
so all text is stamped with PIL).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Captures", "Settle")
CELL = (640, 360)
COLOURS = [(230, 90, 70), (240, 200, 60), (90, 200, 120), (90, 150, 240)]
NOTE = ("Frame-exact renders: silent about smoothness, including any stutter the show may still have. "
        "Lit at the passage's own exposure (EV100 -3). World frozen: only the camera moves." "\n"
        "Bob not shown: in the real settle it fades out across these frames, so the middle of each settle "
        "will be a little less clean than this.")


def label(settle):
    return "as now: no settle" if settle == 0.0 else "settle %.1f s" % settle


def main():
    with open(os.path.join(HERE, "settle_options.json"), encoding="utf-8") as handle:
        run = json.load(handle)
    unknown = [v for v in run["ground"].values() if v.startswith("UNKNOWN")]
    # "--ground-unverified-label" (the conductor, 30 Sep): the frames may go to Gary with the gap stamped on every
    # frame instead of being withheld. Only when passed explicitly, and still only after an eye check.
    stamped = "--ground-unverified-label" in sys.argv[1:]
    suffix = "_INTERNAL" if unknown and not stamped else ""
    note = NOTE
    if run.get("hidden_from_capture"):
        note = note.replace("World frozen: only the camera moves.",
                            "World frozen: only the camera moves. Wings absent (hidden from the capture).")
    if unknown and stamped:
        note = note + "\n" + "Ground unverified: no collision found under the camera on the approach."
    settles = run["settles_s"]
    frames = {}
    for still in run["stills"]:
        frames.setdefault(still["t"], {})[still["settle"]] = still
    times = sorted(frames)

    work = tempfile.mkdtemp()
    grid_paths = []
    for index, t in enumerate(times):
        grid = Image.new("RGB", (CELL[0] * 2, CELL[1] * 2 + 76), (15, 15, 15))
        for slot, settle in enumerate(settles):
            still = frames[t][settle]
            cell = Image.open(os.path.join(HERE, still["name"] + ".png")).convert("RGB").resize(CELL)
            draw = ImageDraw.Draw(cell)
            state = "CUT: Scene 4 Entry camera" if t >= 0 else "%.2f s to the cut | %.0f cm to go" % (-t, still["to_go_cm"])
            draw.rectangle([0, 0, CELL[0], 26], fill=(0, 0, 0))
            draw.text((8, 7), "%s    %s" % (label(settle), state), fill=COLOURS[slot])
            grid.paste(cell, ((slot % 2) * CELL[0], (slot // 2) * CELL[1]))
        ImageDraw.Draw(grid).multiline_text((8, CELL[1] * 2 + 10), note, fill=(200, 200, 200), spacing=6)
        path = os.path.join(work, "grid_%04d.png" % index)
        grid.save(path)
        grid_paths.append(path)
    for extra in range(12):                       # hold the last frame about half a second
        shutil.copy(grid_paths[-1], os.path.join(work, "grid_%04d.png" % (len(grid_paths) + extra)))

    mp4 = os.path.join(HERE, "settle_grid%s.mp4" % suffix)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(run["fps"]),
                    "-i", os.path.join(work, "grid_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", mp4],
                   check=True)
    frames_small = [Image.open(p).resize((CELL[0], CELL[1] + 38)) for p in sorted(
        os.path.join(work, f) for f in os.listdir(work))]
    gif = os.path.join(HERE, "settle_grid%s.gif" % suffix)
    frames_small[0].save(gif, save_all=True, append_images=frames_small[1:], duration=int(1000 / run["fps"]), loop=0)
    shutil.rmtree(work)

    # The chart: distance to go, then speed, against time to the cut.
    width, height, pad = 1200, 760, 70
    chart = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(chart)
    t_min, t_max = min(times), max(times)
    max_to_go = max(s["to_go_cm"] for s in run["stills"])
    panels = [("distance still to go (cm)", 60, 360, max_to_go), ("speed (cm/s)", 420, 720, 260.0)]

    def x_of(t):
        return pad + (t - t_min) / (t_max - t_min) * (width - 2 * pad)

    for title, top, bottom, top_value in panels:
        draw.rectangle([pad, top, width - pad, bottom], outline=(120, 120, 120))
        draw.text((pad, top - 22), title, fill=(30, 30, 30))
        draw.line([(x_of(0.0), top), (x_of(0.0), bottom)], fill=(160, 160, 160))
        draw.text((x_of(0.0) + 4, bottom - 16), "the cut", fill=(90, 90, 90))
        draw.text((pad - 60, top + 4), "%.0f" % top_value, fill=(90, 90, 90))
        draw.text((pad - 20, bottom - 12), "0", fill=(90, 90, 90))
        second = int(t_min)
        while second <= t_max:
            draw.line([(x_of(second), bottom), (x_of(second), bottom + 5)], fill=(90, 90, 90))
            draw.text((x_of(second) - 10, bottom + 8), "%+d s" % second if second else "0 s", fill=(90, 90, 90))
            second += 1
        for slot, settle in enumerate(settles):
            series = sorted((s["t"], s["to_go_cm"]) for s in run["stills"] if s["settle"] == settle)
            if title.startswith("speed"):
                series = [(b[0], max(0.0, (a[1] - b[1]) / (b[0] - a[0]))) for a, b in zip(series, series[1:])]
            points = [(x_of(t), bottom - v / top_value * (bottom - top - 10)) for t, v in series]
            draw.line(points, fill=COLOURS[slot], width=3)
            draw.text((width - pad - 190, top + 10 + slot * 18), label(settle), fill=COLOURS[slot])
    draw.text((pad, 20), "P04 -> Scene 4: every settle arrives at the SAME place at the SAME moment; the settled cat "
              "starts ahead because it walked slightly quicker earlier in the span.", fill=(20, 20, 20))
    chart_path = os.path.join(HERE, "settle_chart%s.png" % suffix)
    chart.save(chart_path)
    print("ground=%s -> %s, %s, %s" % (run["ground"], mp4, gif, chart_path))


main()
