#!/usr/bin/env python3
"""Read public TikTok counters for the account's confirmed video URLs.

Does not read or post comments, log into TikTok or change account settings.
A failed or blocked lookup is None, never zero.
"""
import html
import json
import re
import urllib.parse
import urllib.request

HANDLE = "photofiver.photof"
COUNTER_NAMES = {
    "diggCount": "likes",
    "commentCount": "comments",
    "shareCount": "shares",
    "playCount": "views",
    "collectCount": "saves",
}


def safe_int(value):
    if type(value) is int and value >= 0:
        return value
    return None


def _unpack_video(source, video_id):
    # TikTok's JSON may contain other suggested videos; identify *this* item.
    for script_id in ("__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE"):
        m = re.search(
            r'<script[^>]+id=["\']' + re.escape(script_id) +
            r'["\'][^>]*>(.*?)</script>', source, re.S | re.I
        )
        if not m:
            continue
        try:
            data = json.loads(html.unescape(m.group(1)))
        except (ValueError, TypeError):
            continue
        candidates = []
        if script_id == "SIGI_STATE":
            item = (data.get("ItemModule") or {}).get(video_id)
            if isinstance(item, dict):
                candidates.append(item)
        else:
            detail = ((data.get("__DEFAULT_SCOPE__") or {})
                      .get("webapp.video-detail") or {})
            info = detail.get("itemInfo") or {}
            for item in (info.get("itemStruct"), detail.get("itemStruct")):
                if isinstance(item, dict):
                    candidates.append(item)
        for item in candidates:
            if str(item.get("id")) != video_id:
                continue
            author = item.get("author")
            if isinstance(author, dict):
                username = author.get("uniqueId") or author.get("unique_id")
            elif isinstance(author, str):
                username = author
            else:
                continue
            if str(username).lower().lstrip("@") != HANDLE:
                continue
            stats = item.get("stats")
            if not isinstance(stats, dict):
                continue
            result = {key: safe_int(stats.get(old))
                      for old, key in COUNTER_NAMES.items()}
            if any(v is not None for v in result.values()):
                return result
    return None


def public_video_stats(url):
    """Get validated counters; None means unavailable, not 0."""
    try:
        u = urllib.parse.urlparse(url)
        if (u.scheme != "https" or u.hostname not in
                ("www.tiktok.com", "tiktok.com", "m.tiktok.com")):
            return None
        m = re.fullmatch(r"/@" + re.escape(HANDLE) + r"/video/(\d+)",
                         u.path, re.I)
        if not m:
            return None
        video_id = m.group(1)
        req = urllib.request.Request(
            "https://www.tiktok.com/@" + HANDLE + "/video/" + video_id +
            "?lang=en",
            headers={"User-Agent":
                     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                     "Accept-Language": "en-GB,en;q=0.9",
                     "Accept": "text/html,application/xhtml+xml"})
        with urllib.request.urlopen(req, timeout=17) as response:
            page = response.read(3_000_000).decode("utf-8", "replace")
        return _unpack_video(page, video_id)
    except Exception:
        return None
