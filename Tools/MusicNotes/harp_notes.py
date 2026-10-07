"""Note-level analysis of a passage walk track: onsets with pitch, salience, repeated-note runs and melodic peaks.
Offline only. Usage: python harp_notes.py <wav> <out.json> [show_offset_s]"""
import json, sys
import numpy as np
import librosa

wav, out = sys.argv[1], sys.argv[2]
offset = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
y, sr = librosa.load(wav, sr=44100, mono=True)
hop = 256
env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop, aggregate=np.median)
frames = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, backtrack=False, delta=0.07, wait=3)
times = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
C = np.abs(librosa.cqt(y, sr=sr, hop_length=hop, fmin=librosa.note_to_hz("C2"), n_bins=72, bins_per_octave=12))
Cdb = librosa.amplitude_to_db(C, ref=np.max)
notes = []
for f, t in zip(frames, times):
    a, b = f + 2, min(f + 10, C.shape[1])           # just after the attack
    if b <= a:
        continue
    spec = C[:, a:b].mean(axis=1)
    prev = C[:, max(f - 6, 0):max(f - 1, 1)].mean(axis=1)
    rise = np.maximum(spec - prev, 0)                # what is NEW at this onset
    k = int(np.argmax(rise))
    midi = int(36 + k)
    loud = float(Cdb[k, a:b].max())
    notes.append({"song_s": round(float(t), 3), "show_s": round(float(t) + offset, 3), "midi": midi,
                  "note": librosa.midi_to_note(midi), "env": float(env[f]), "loud_db": round(loud, 1)})
envs = np.array([n["env"] for n in notes])
for i, n in enumerate(notes):
    lo, hi = max(0, i - 8), min(len(notes), i + 9)
    loc = np.median(envs[lo:hi])
    n["salience"] = round(float(n["env"] / (loc + 1e-9)), 2)
# repeated-note runs: >=3 consecutive onsets, same pitch (+-1 semitone), IOI < 0.6 s
runs, i = [], 0
while i < len(notes):
    j = i
    while j + 1 < len(notes) and abs(notes[j + 1]["midi"] - notes[i]["midi"]) <= 1 and notes[j + 1]["song_s"] - notes[j]["song_s"] < 0.6:
        j += 1
    if j - i + 1 >= 3:
        runs.append({"start_show_s": notes[i]["show_s"], "end_show_s": notes[j]["show_s"], "count": int(j - i + 1),
                     "note": notes[i]["note"], "idx": [int(i), int(j)]})
        for k in range(i, j + 1):
            notes[k]["run"] = len(runs) - 1
        i = j + 1
    else:
        i += 1
# melodic peaks: pitch local maximum among neighbours within 1.5 s, and above the passage's 75th pitch percentile
mid = np.array([n["midi"] for n in notes])
p75 = np.percentile(mid, 75)
for i, n in enumerate(notes):
    nb = [m for m in notes if abs(m["song_s"] - n["song_s"]) <= 1.5 and m is not n]
    n["melodic_peak"] = bool(bool(nb) and n["midi"] >= max(m["midi"] for m in nb) and n["midi"] >= float(p75))
# notable = run starts/accents, melodic peaks, or salient (>=1.6x local)
for n in notes:
    n["notable"] = bool(n.get("melodic_peak") or n["salience"] >= 1.6 or
                        ("run" in n and (n["song_s"] == runs[n["run"]]["start_show_s"] - offset)))
json.dump({"wav": wav, "show_offset_s": offset, "duration_s": len(y) / sr, "notes": notes, "runs": runs,
           "counts": {"onsets": len(notes), "runs": len(runs), "notable": sum(n["notable"] for n in notes),
                      "melodic_peaks": sum(n["melodic_peak"] for n in notes)}}, open(out, "w"), indent=1)
print("HARP_NOTES_OK", json.dumps({"onsets": len(notes), "runs": len(runs), "notable": sum(n["notable"] for n in notes)}))
