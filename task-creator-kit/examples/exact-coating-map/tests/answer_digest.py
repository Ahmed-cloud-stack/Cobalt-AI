"""Stable fingerprints of complete JSON answers."""
import hashlib
import json


def answer_digest(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()
