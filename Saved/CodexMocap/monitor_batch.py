"""Read the running batch's checkpoint and new relevant Unreal log lines."""
import json
import pathlib
import re

folder=pathlib.Path('E:/PussStage/Saved/CodexMocap')
status=json.loads((folder/'batch_status.json').read_text(encoding='utf-8'))
print(json.dumps({k:status[k] for k in ['updated_utc','running','current','completed','failed']},indent=2))
for job in status['jobs']:
    if job['state'] == 'failed':
        print(json.dumps({k:job[k] for k in ['stem','state','coverage','animation','error','verification_error'] if k in job}))
log=pathlib.Path('E:/PussStage/Saved/Logs/PussStage_2.log')
cursor_file=folder/'monitor_cursor.json'
offset=json.loads(cursor_file.read_text()).get('offset',0) if cursor_file.exists() else max(0,log.stat().st_size-3000)
with log.open('rb') as stream:
    stream.seek(offset)
    tail=stream.read()
    offset=stream.tell()
cursor_file.write_text(json.dumps({'offset':offset}))
for line in tail.decode('utf-8',errors='replace').splitlines():
    if re.search(r'MOCAP_|Finished Pipeline|LogMetaHuman.*(?:Error|Warning)|Fatal error|Ran out of memory',line):
        print(line)
