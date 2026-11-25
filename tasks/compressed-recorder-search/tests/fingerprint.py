"""Canonical JSON fingerprints for storage and comparison."""
import hashlib
import json


def fingerprint(answer):
    encoded = json.dumps(answer, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("ascii")).hexdigest()
