"""
TOON (Token-Oriented Object Notation) — compact text for tabular data.
Saves ~40% tokens vs JSON for uniform arrays.

Usage:
    from toon_util import json_to_toon
    print(json_to_toon([{"month": "Jan", "amount": 5000}, {"month": "Feb", "amount": 0}]))
    # month|amount
    # Jan|5000
    # Feb|0
"""


def json_to_toon(data: list[dict] | list | dict) -> str:
    if isinstance(data, dict):
        return " | ".join(f"{k}:{v}" for k, v in data.items())

    if not isinstance(data, list) or len(data) == 0:
        return str(data)

    # Uniform dict array → header + data rows
    if all(isinstance(item, dict) for item in data):
        keys = list(data[0].keys())
        if all(list(item.keys()) == keys for item in data):
            header = "|".join(keys)
            rows = ["|".join(str(item.get(k, "")) for k in keys) for item in data]
            return header + "\n" + "\n".join(rows)

    # Primitive array → comma-separated
    if all(isinstance(item, (str, int, float, bool)) for item in data):
        return ",".join(str(item) for item in data)

    # Fallback
    return str(data)
