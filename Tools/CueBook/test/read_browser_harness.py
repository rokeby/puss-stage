"""Read the real Cue Book browser harness result through a local Chromium DevTools endpoint."""
import argparse
import base64
import json
import os
import socket
import struct
import time
import urllib.parse
import urllib.request


def websocket(url):
    parsed = urllib.parse.urlparse(url)
    sock = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode('ascii')
    request = (f'GET {parsed.path} HTTP/1.1\r\nHost: {parsed.hostname}:{parsed.port}\r\n'
               f'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
               'Sec-WebSocket-Version: 13\r\n\r\n')
    sock.sendall(request.encode('ascii'))
    response = b''
    while b'\r\n\r\n' not in response:
        response += sock.recv(4096)
    if b' 101 ' not in response.split(b'\r\n', 1)[0]:
        raise RuntimeError('DevTools WebSocket upgrade failed: %r' % response[:200])
    return sock


def send_text(sock, text):
    payload = text.encode('utf-8')
    mask = os.urandom(4)
    size = len(payload)
    header = bytearray([0x81])
    if size < 126:
        header.append(0x80 | size)
    elif size < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack('!H', size))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack('!Q', size))
    header.extend(mask)
    sock.sendall(header + bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload)))


def receive_text(sock):
    def read(n):
        out = b''
        while len(out) < n:
            chunk = sock.recv(n - len(out))
            if not chunk:
                raise EOFError('DevTools WebSocket closed')
            out += chunk
        return out
    first, second = read(2)
    opcode, size = first & 0x0f, second & 0x7f
    if size == 126:
        size = struct.unpack('!H', read(2))[0]
    elif size == 127:
        size = struct.unpack('!Q', read(8))[0]
    mask = read(4) if second & 0x80 else b''
    payload = read(size)
    if mask:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    if opcode == 0x9:
        return receive_text(sock)
    return payload.decode('utf-8')


def evaluate(sock, expression, call_id):
    send_text(sock, json.dumps({'id': call_id, 'method': 'Runtime.evaluate',
                                'params': {'expression': expression, 'returnByValue': True}}))
    while True:
        reply = json.loads(receive_text(sock))
        if reply.get('id') == call_id:
            return reply.get('result', {}).get('result', {}).get('value')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug-url', default='http://127.0.0.1:9223')
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    pages = json.load(urllib.request.urlopen(args.debug_url + '/json', timeout=5))
    page = next(item for item in pages if item.get('type') == 'page' and '127.0.0.1:8765' in item.get('url', ''))
    sock = websocket(page['webSocketDebuggerUrl'])
    deadline, call_id = time.time() + args.timeout, 1
    try:
        while time.time() < deadline:
            result = evaluate(sock, "document.querySelector('#browser-harness-result')?.textContent || ''", call_id)
            call_id += 1
            if result:
                print(result)
                return 0 if result.startswith('CUEBOOK_BROWSER_HARNESS_OK') else 1
            time.sleep(0.1)
        body = evaluate(sock, "document.body?.innerText || ''", call_id)
        print('CUEBOOK_BROWSER_HARNESS_TIMEOUT\n' + str(body))
        return 1
    finally:
        sock.close()


if __name__ == '__main__':
    raise SystemExit(main())
