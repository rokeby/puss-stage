"""Call the loopback Unreal MCP endpoint; all Editor execution uses its guarded tools."""
import argparse
import json
import pathlib
import urllib.request

import os

# Each Unreal project serves its own MCP listener on its own port: PussStage 8010,
# MHFat 8000. Override with --url or PUSS_MCP_URL when driving another editor.
DEFAULT_URL = os.environ.get('PUSS_MCP_URL', 'http://127.0.0.1:8010/mcp')


def decode_response(raw):
    text = raw.decode('utf-8')
    if not text.strip():
        return None
    if text.lstrip().startswith('{'):
        return json.loads(text)
    values = []
    for line in text.splitlines():
        if line.startswith('data:'):
            values.append(json.loads(line[5:].strip()))
    return values[-1] if values else {'raw': text}


def send(payload, session=None, timeout=30, url=None):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if session:
        headers['Mcp-Session-Id'] = session
    request = urllib.request.Request(url or DEFAULT_URL, json.dumps(payload).encode(), headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return decode_response(response.read()), response.headers.get('Mcp-Session-Id')


parser = argparse.ArgumentParser()
parser.add_argument('method')
parser.add_argument('--params-file')
parser.add_argument('--output')
parser.add_argument('--timeout', type=int, default=30)
parser.add_argument('--url', default=DEFAULT_URL)
args = parser.parse_args()
initialized, session = send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
    'protocolVersion': '2024-11-05', 'capabilities': {},
    'clientInfo': {'name': 'PussStageMocapBatch', 'version': '1.0'}}}, url=args.url)
if initialized and 'error' in initialized:
    raise RuntimeError(initialized)
send({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session, url=args.url)
params = json.loads(pathlib.Path(args.params_file).read_text(encoding='utf-8')) if args.params_file else {}
result, _ = send({'jsonrpc': '2.0', 'id': 2, 'method': args.method, 'params': params}, session, args.timeout, url=args.url)
rendered = json.dumps(result, indent=2)
if args.output:
    pathlib.Path(args.output).write_text(rendered, encoding='utf-8')
print(rendered)
if result and 'error' in result:
    raise SystemExit(1)
