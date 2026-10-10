"""Record Windows system audio (WASAPI loopback of the default output) to a WAV until a stop file appears.

    python Scripts/loopback_rec.py <out.wav> <stopfile>

Used by Scripts/screenrec.sh (Gary 10 Oct: PIE recordings need the show audio). Needs PyAudioWPatch.
"""
import os
import sys
import time
import wave

import pyaudiowpatch as pa

out, stop = sys.argv[1], sys.argv[2]
p = pa.PyAudio()
dev = p.get_default_wasapi_loopback()
rate, ch = int(dev["defaultSampleRate"]), int(dev["maxInputChannels"])
w = wave.open(out, "wb")
w.setnchannels(ch)
w.setsampwidth(p.get_sample_size(pa.paInt16))
w.setframerate(rate)


# WASAPI loopback delivers NOTHING while the system is silent, so pad with zeros against the wall clock to keep the
# audio in sync with the video.
T0 = [None]
written = [0]
BYTES = ch * 2


def pad_to(now):
    due = int((now - T0[0]) * rate)
    gap = due - written[0]
    if gap > 2048:
        w.writeframes(bytes(gap * BYTES))
        written[0] += gap


CLOSED = [False]


def cb(data, frames, info, status):
    if CLOSED[0]:
        return (None, pa.paComplete)
    pad_to(time.perf_counter() - frames / rate)
    w.writeframes(data)
    written[0] += frames
    return (None, pa.paContinue)


s = p.open(format=pa.paInt16, channels=ch, rate=rate, input=True, input_device_index=dev["index"],
           frames_per_buffer=1024, stream_callback=cb)
T0[0] = time.perf_counter()
s.start_stream()
while not os.path.exists(stop):
    time.sleep(0.2)
# stop_stream() can hang on a silent WASAPI loopback (live 10 Oct): close the WAV first, flag done, then hard-exit.
CLOSED[0] = True
time.sleep(0.1)
pad_to(time.perf_counter())
w.close()
open(stop + ".done", "w").close()
os._exit(0)
