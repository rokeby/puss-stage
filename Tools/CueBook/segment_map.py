"""Ordered Cue Book segment-name to Infinity Show-key mapping.

The order matters because the Cue Book currently repeats the literal name
``Transition``.  Those occurrences map to I1, I2, ... in show order.  Exact
JSON overrides (or ``Transition#N`` overrides) always win.  Unknown names stay
unmapped and are returned to the caller for reporting.
"""
from __future__ import annotations

import json
import pathlib
import re


DEFAULT_PATH = pathlib.Path(__file__).with_name("segment_map.json")


def _normalise(value):
    return " ".join(str(value or "").split()).casefold()


def load_segment_map(path=DEFAULT_PATH):
    path = pathlib.Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("CUEBOOK_SEGMENT_MAP_BAD_SCHEMA|%s" % path)
    if not isinstance(data.get("overrides", {}), dict):
        raise ValueError("CUEBOOK_SEGMENT_MAP_BAD_OVERRIDES|%s" % path)
    if not isinstance(data.get("closing_key"), str) or not data["closing_key"].strip():
        raise ValueError("CUEBOOK_SEGMENT_MAP_BAD_CLOSING|%s" % path)
    return data


def map_segment_names(names, config):
    """Return one result per ordered name: name, key (or None), and reason."""
    overrides = {_normalise(k): v for k, v in config.get("overrides", {}).items()}
    closing = str(config["closing_key"]).strip()
    transition_n = 0
    results = []
    for raw in names:
        name = " ".join(str(raw or "").split())
        norm = _normalise(name)
        is_transition = re.match(r"^transition\b", norm) is not None
        if is_transition:
            transition_n += 1
        occurrence = "transition#%d" % transition_n if is_transition else ""
        if occurrence and occurrence in overrides:
            key, reason = overrides[occurrence], "override"
        elif norm in overrides:
            key, reason = overrides[norm], "override"
        else:
            match = re.match(r"^passage\s+(\d+)\b", norm)
            if match:
                key, reason = "P%02d" % int(match.group(1)), "passage_rule"
            else:
                match = re.match(r"^(?:scene\s*|s)(\d+)\b", norm)
                if match:
                    key, reason = "S%d" % int(match.group(1)), "scene_rule"
                elif is_transition:
                    key, reason = "I%d" % transition_n, "transition_rule"
                elif re.match(r"^curtain opening\b", norm):
                    key, reason = "Opening", "opening_rule"
                elif re.match(r"^ending\b", norm):
                    key, reason = closing, "ending_rule"
                else:
                    key, reason = None, "unmapped"
        if key is not None and (not isinstance(key, str) or not key.strip()):
            raise ValueError("CUEBOOK_SEGMENT_MAP_BAD_KEY|%s" % name)
        results.append({"name": name, "key": key.strip() if isinstance(key, str) else None,
                        "reason": reason, "transition_index": transition_n if is_transition else None})
    return results


def unmapped(results):
    return [row["name"] for row in results if row["key"] is None]
