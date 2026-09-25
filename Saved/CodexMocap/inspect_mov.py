"""Read QuickTime metadata without decoding or modifying source footage."""
import json
import pathlib
import struct
import sys


def boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    while start + 8 <= end:
        size, kind = struct.unpack_from('>I4s', data, start)
        header = 8
        if size == 1:
            size = struct.unpack_from('>Q', data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            break
        yield kind.decode('ascii', errors='replace'), data[start + header:start + size]
        start += size


def inspect(path):
    with path.open('rb') as source:
        moov = None
        while header := source.read(8):
            size, kind = struct.unpack('>I4s', header)
            header_size = 8
            if size == 1:
                size = struct.unpack('>Q', source.read(8))[0]
                header_size = 16
            if size < header_size:
                raise ValueError('Invalid or unbounded top-level box')
            if kind == b'moov':
                moov = source.read(size - header_size)
                break
            source.seek(size - header_size, 1)
    if moov is None:
        raise ValueError('No moov metadata found')
    tracks = []
    for kind, track in boxes(moov):
        if kind != 'trak':
            continue
        track_boxes = dict(boxes(track))
        media = dict(boxes(track_boxes['mdia']))
        if media['hdlr'][8:12] != b'vide':
            continue
        mdhd = media['mdhd']
        offset = 20 if mdhd[0] == 1 else 12
        timescale = struct.unpack_from('>I', mdhd, offset)[0]
        duration = struct.unpack_from('>Q' if mdhd[0] == 1 else '>I', mdhd, offset + 4)[0]
        sample_table = dict(boxes(dict(boxes(media['minf']))['stbl']))
        description = sample_table['stsd']
        tkhd = track_boxes['tkhd']
        stts = sample_table['stts']
        entry_count = struct.unpack_from('>I', stts, 4)[0]
        timings = [struct.unpack_from('>II', stts, 8 + 8 * i) for i in range(entry_count)]
        frames = sum(count for count, delta in timings)
        ticks = sum(count * delta for count, delta in timings)
        tracks.append({
            'codec': description[12:16].decode('ascii', errors='replace'),
            'encoded_width': struct.unpack_from('>H', description, 40)[0],
            'encoded_height': struct.unpack_from('>H', description, 42)[0],
            'track_width': struct.unpack_from('>I', tkhd, len(tkhd) - 8)[0] / 65536,
            'track_height': struct.unpack_from('>I', tkhd, len(tkhd) - 4)[0] / 65536,
            'seconds': round(duration / timescale, 3),
            'frames': frames,
            'average_fps': round(frames * timescale / ticks, 5),
            'sample_duration_values': sorted(set(delta for count, delta in timings)),
            'timescale': timescale,
        })
    return {'name': path.name, 'bytes': path.stat().st_size, 'video_tracks': tracks}


results = []
for path in sorted(pathlib.Path(sys.argv[1]).glob('*.mov')):
    try:
        results.append(inspect(path))
    except Exception as error:
        results.append({'name': path.name, 'error': str(error)})
print(json.dumps(results, indent=2))
