"""Offline-only Content filename/package inventory for P06 dust and slam candidates.

Reads package bytes but never writes under Content.  Embedded PCM SoundWave RIFF
payloads are measured directly; the cue graph itself is only identified by
package strings and is not claimed louder than a measured wave.
"""
from __future__ import annotations

import argparse
import array
import datetime
import hashlib
import json
import math
import re
import sys
import wave
from io import BytesIO
from pathlib import Path


DUST_NAMES = ("P_Ambient_Dust", "P_Smoke", "PS_Debris")
SOUND_NAMES = ("Collapse01", "Collapse02", "Explosion01", "Explosion02")


def game_path(content_root, path):
    return "/Game/" + path.relative_to(content_root).with_suffix("").as_posix()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embedded_wave_metrics(path):
    data = path.read_bytes()
    offset = data.find(b"RIFF")
    if offset < 0:
        return None
    with wave.open(BytesIO(data[offset:]), "rb") as handle:
        width = handle.getsampwidth()
        raw = handle.readframes(handle.getnframes())
        if width != 2:
            return {"riff_offset": offset, "sample_width": width, "unsupported_for_loudness": True}
        samples = array.array("h")
        samples.frombytes(raw)
        if sys.byteorder != "little":
            samples.byteswap()
        count = max(1, len(samples))
        peak = max(abs(x) for x in samples)
        rms = math.sqrt(sum(float(x) * float(x) for x in samples) / count)
        full = 32767.0
        return {
            "riff_offset": offset,
            "channels": handle.getnchannels(),
            "sample_rate": handle.getframerate(),
            "duration_s": round(handle.getnframes() / float(handle.getframerate()), 6),
            "peak_dbfs": round(20.0 * math.log10(max(1.0, peak) / full), 4),
            "rms_dbfs": round(20.0 * math.log10(max(1.0, rms) / full), 4),
        }


def ascii_strings(path):
    return [x.decode("ascii", "ignore") for x in re.findall(rb"[ -~]{4,}", path.read_bytes())]


def build(project):
    project = Path(project).resolve()
    content = project / "Content"
    if not content.is_dir():
        raise RuntimeError("CONTENT_MISSING|%s" % content)
    assets = {p.stem: p for p in content.rglob("*.uasset")}
    dust = []
    for name in DUST_NAMES:
        for path in sorted(p for p in content.rglob(name + ".uasset")):
            strings = ascii_strings(path)
            dust.append({"asset": game_path(content, path), "filename": str(path), "bytes": path.stat().st_size,
                         "sha256": sha256(path),
                         "particle_light_module_strings": sorted(set(x for x in strings if "ParticleModuleLight" in x)),
                         "inventory_basis": "filename+package present+light-module string census"})
    sound = []
    for name in SOUND_NAMES:
        path = assets.get(name)
        if path is None:
            continue
        metrics = embedded_wave_metrics(path)
        sound.append({"asset": game_path(content, path), "filename": str(path), "bytes": path.stat().st_size,
                      "sha256": sha256(path), "embedded_wave": metrics,
                      "inventory_basis": "filename+package present+embedded PCM measured"})
    sound.sort(key=lambda x: x.get("embedded_wave", {}).get("rms_dbfs", -999.0), reverse=True)
    cues = []
    for name in ("Collapse_Cue", "Explosion_Cue"):
        path = assets.get(name)
        if path:
            strings = ascii_strings(path)
            cues.append({"asset": game_path(content, path), "filename": str(path), "bytes": path.stat().st_size,
                         "sha256": sha256(path),
                         "graph_strings": sorted(set(x for x in strings if "SoundNode" in x or x in SOUND_NAMES)),
                         "inventory_basis": "package strings only; cue output loudness not measured"})
    return {
        "schema": 1,
        "made_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "project_read_only": str(project),
        "content_mutated": False,
        "dust_candidates": dust,
        "sound_candidates": sound,
        "sound_cues": cues,
        "default_slam_sound": sound[0]["asset"] if sound else None,
        "default_basis": ("highest measured full-file RMS among embedded PCM candidates" if sound else
                          "no measured candidate"),
        "limits": ["package presence does not prove rendered particle suitability",
                   "offline PCM RMS does not replace Gary's listening choice"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    doc = build(args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("P37_ASSET_INVENTORY|dust=%d|sounds=%d|default=%s|content_mutated=0|out=%s" %
          (len(doc["dust_candidates"]), len(doc["sound_candidates"]), doc["default_slam_sound"], out))


if __name__ == "__main__":
    main()
