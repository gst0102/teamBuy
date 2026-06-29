from __future__ import annotations


def strip_unicode_surrogates(value):
    if isinstance(value, str):
        return "".join(ch for ch in value if not 0xD800 <= ord(ch) <= 0xDFFF)
    if isinstance(value, list):
        return [strip_unicode_surrogates(item) for item in value]
    if isinstance(value, tuple):
        return tuple(strip_unicode_surrogates(item) for item in value)
    if isinstance(value, dict):
        return {key: strip_unicode_surrogates(item) for key, item in value.items()}
    return value
