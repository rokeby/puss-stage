"""Pure geometry for opt-in Flat V3 baked-pole clipping (no Blender dependency)."""
from __future__ import annotations


def boolean_runs(values):
    runs, start = [], None
    for index, value in enumerate(values):
        if value and start is None:
            start = index
        elif not value and start is not None:
            runs.append((start, index)); start = None
    if start is not None:
        runs.append((start, len(values)))
    return runs


def art_full_segments(inside, pole_y, height_m, diameter_m, margin_m, step_m=0.005, columns=7):
    """Return covered Z segments for each pole.

    A sample is covered only when every column across the pole diameter is inside the art mask. Runs are shrunk by
    ``margin_m`` at both ends, so base notches and internal holes produce real gaps instead of exposed pole geometry.
    The below-floor extension is intentionally not included; the Blender builder adds it as a separate buried segment.
    """
    if step_m <= 0 or height_m <= 0 or diameter_m <= 0 or margin_m < 0 or columns < 3:
        raise ValueError("invalid art-full sampling arguments")
    offsets = [(-diameter_m * 0.5) + diameter_m * i / float(columns - 1) for i in range(columns)]
    count = int(height_m / step_m + 0.999999)
    zs = [min(height_m, (i + 0.5) * step_m) for i in range(count)]
    all_segments, rows = [], []
    for index, y in enumerate(pole_y, start=1):
        covered = []
        for z in zs:
            covered.append(all(bool(v) for v in inside([(float(y) + dy, z) for dy in offsets])))
        raw = boolean_runs(covered)
        segments = []
        for first, end in raw:
            lo = first * step_m + margin_m
            hi = min(end * step_m, height_m) - margin_m
            if hi - lo >= step_m:
                segments.append([float(lo), float(hi)])
        if not segments:
            raise ValueError("pole %d has no usable art-covered segment" % index)
        all_segments.append(segments)
        rows.append({"socket": "SOCKET_Pole_%d" % index, "y_m": float(y), "segments_m": segments,
                     "raw_run_count": len(raw), "margin_m": float(margin_m), "sample_step_m": float(step_m),
                     "columns": int(columns), "covered_sample_count": sum(covered)})
    return all_segments, rows


def with_buried_feet(segments_per_pole, bottom_m):
    if bottom_m >= 0:
        raise ValueError("buried pole bottom must be below zero")
    return [[[float(bottom_m), 0.0]] + [list(map(float, segment)) for segment in segments]
            for segments in segments_per_pole]
