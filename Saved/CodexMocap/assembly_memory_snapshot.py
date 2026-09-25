"""Small read-only memory snapshot for the currently recorded assembly editor."""
import ctypes
import datetime
import json
import subprocess
from launch_empty_assembly import ROOT, MEMORYSTATUSEX, kernel, editors

memory = MEMORYSTATUSEX()
memory.dwLength = ctypes.sizeof(memory)
assert kernel.GlobalMemoryStatusEx(ctypes.byref(memory))
result = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'editors': editors(),
    'physical_free_gib': round(memory.ullAvailPhys / 2**30, 2),
    'commit_free_gib': round(memory.ullAvailPageFile / 2**30, 2),
    'commit_limit_gib': round(memory.ullTotalPageFile / 2**30, 2)}
try:
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'],
        capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
    result['gpu_used_mib_total_mib_percent'] = gpu.stdout.strip()
except Exception as exc:
    result['gpu_probe_error'] = str(exc)
with (ROOT / 'Saved/CodexMocap/assembly_memory_snapshots.jsonl').open('a', encoding='utf-8') as output:
    output.write(json.dumps(result) + '\n')
print(json.dumps(result))
