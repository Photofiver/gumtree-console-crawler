"""Blueprint session transfer: explicit, domain-limited Playwright state only.

Never write state to public issues, logs, screenshots or repository files.
GitHub Actions reads only BLUEPRINT_STORAGE_STATE_ZB64 from Actions Secrets.
"""
import base64
import json
import os
from urllib.parse import urlsplit
import zlib

SECRET_NAME = "BLUEPRINT_STORAGE_STATE_ZB64"
MAX_STATE_BYTES = 800_000


def is_blueprint_host(hostname):
    return bool(hostname) and (hostname == "blueprint.io" or hostname.endswith(".blueprint.io"))


def filter_blueprint_state(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("cookies"), list) or not isinstance(raw.get("origins"), list):
        raise ValueError("Invalid Playwright storage state")
    cookies = []
    for item in raw["cookies"]:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain", "")).lstrip(".").lower()
        if is_blueprint_host(domain):
            cookies.append(item)
    origins = []
    for item in raw["origins"]:
        if not isinstance(item, dict):
            continue
        parsed = urlsplit(str(item.get("origin", "")))
        if parsed.scheme == "https" and is_blueprint_host(parsed.hostname):
            origins.append(item)
    if not cookies and not origins:
        raise ValueError("No Blueprint session state was found")
    return {"cookies": cookies, "origins": origins}


def encode_state(raw):
    state = filter_blueprint_state(raw)
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_STATE_BYTES:
        raise ValueError("Blueprint session state is too large")
    encoded = base64.b64encode(zlib.compress(payload, 9)).decode("ascii")
    if len(encoded) > 48_000:
        raise ValueError("Compressed session exceeds GitHub Secret size limit")
    return encoded


def decode_state(encoded):
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Blueprint session secret is missing")
    if len(encoded) > 48_000:
        raise ValueError("Blueprint session secret is too large")
    try:
        raw = base64.b64decode(encoded, validate=True)
        decompress = zlib.decompressobj()
        payload = decompress.decompress(raw, MAX_STATE_BYTES + 1)
        if not decompress.eof or len(payload) > MAX_STATE_BYTES or decompress.unconsumed_tail:
            raise ValueError("Invalid or oversized session data")
        state = json.loads(payload)
        return filter_blueprint_state(state)
    except (ValueError, TypeError, zlib.error, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Blueprint session secret") from None


def load_state_from_environment():
    return decode_state(os.environ.get(SECRET_NAME, ""))
