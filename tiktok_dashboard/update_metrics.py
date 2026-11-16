#!/usr/bin/env python3
"""Read-only Buffer + public TikTok stats; writes verified dashboard JSON locally.
Runs in social-only repo. Never changes TikTok, Buffer, or trading bot settings.
"""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "tiktok_dashboard" / "metrics.json"
ATTEMPTS = ROOT / "buffer_tiktok" / "attempts.json"
HANDLE = "photofiver.photof"
BUFFER = "https://api.buffer.com"

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def parse_date(text):
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

def request_follower_count():
    req = urllib.request.Request(
        "https://www.tiktok.com/@" + HANDLE + "?lang=en",
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        })
    with urllib.request.urlopen(req, timeout=22) as response:
        source = response.read(2_500_000).decode("utf-8", "replace")
    def walk(x):
        if isinstance(x, dict):
            if str(x.get("uniqueId", "")).lower() == HANDLE:
                stats = x.get("stats") or {}
                if isinstance(stats, dict) and type(stats.get("followerCount")) is int:
                    return stats["followerCount"]
                if type(x.get("followerCount")) is int:
                    return x["followerCount"]
            info = x.get("userInfo")
            if isinstance(info, dict):
                u = info.get("user") or {}
                s = info.get("stats") or {}
                if (u.get("uniqueId", "").lower() == HANDLE and
                    type(s.get("followerCount")) is int):
                    return s["followerCount"]
            for v in x.values():
                n = walk(v)
                if n is not None:
                    return n
        elif isinstance(x, list):
            for v in x:
                n = walk(v)
                if n is not None:
                    return n
        return None
    for script_id in ("SIGI_STATE", "__UNIVERSAL_DATA_FOR_REHYDRATION__"):
        match = re.search(
            r'<script[^>]*id=["\']' + re.escape(script_id) +
            r'["\'][^>]*>(.*?)</script>', source, re.S)
        if match:
            try:
                number = walk(json.loads(html.unescape(match.group(1))))
                if type(number) is int and number >= 0:
                    return number
            except (ValueError, TypeError):
                pass
    match = re.search(
        r'"uniqueId"\s*:\s*"' + re.escape(HANDLE) +
        r'".{0,2500}?"followerCount"\s*:\s*(\d+)', source, re.S)
    if match:
        return int(match.group(1))
    raise RuntimeError("Public TikTok follower number not exposed on profile")

def lookup_buffer_post(key, post_id):
    query = ("query($input: PostInput!) { post(input: $input) "
             "{ id status externalLink sentAt dueAt schedulingType "
             "channelService channel { name service } error { message } } }")
    payload = {"query": query, "variables": {"input": {"id": post_id}}}
    req = urllib.request.Request(
        BUFFER, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        body = json.load(response)
    if body.get("errors"):
        raise RuntimeError("Buffer GraphQL post lookup failed")
    post = (body.get("data") or {}).get("post") or {}
    channel = post.get("channel") or {}
    if (channel.get("name", "").lower().lstrip("@") != HANDLE or
        str(post.get("channelService", "")).lower() != "tiktok"):
        raise ValueError("Buffer post belongs to another account; ignored")
    return post

def read_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return fallback

def build():
    prior = read_json(STATS, {})
    receipts = read_json(ATTEMPTS, {}).get("attempts", {})
    now = utcnow()
    stamp = now.isoformat().replace("+00:00", "Z")
    data = dict(prior)
    data.update({
        "schema_version": 1, "generated_at_utc": stamp,
        "portfolio": "@" + HANDLE,
        "planned_slots_per_day": 15, "slot_minutes": 96,
        "earnings_gbp": None, "views_30d": None,
        "followers_source": "public_tiktok_profile",
    })
    try:
        count = request_follower_count()
        data["followers"] = count
        data["followers_checked_at_utc"] = stamp
        history = list(prior.get("follower_history") or [])
        if not history or (history[-1].get("followers") != count or
           (parse_date(history[-1].get("utc")) and
            (now - parse_date(history[-1]["utc"])).total_seconds() >= 21600)):
            history.append({"utc": stamp, "followers": count})
        data["follower_history"] = history[-1440:]
        print("TIKTOK_FOLLOWERS_CONFIRMED", count)
    except Exception as exc:
        data["followers"] = prior.get("followers")
        print("PUBLIC_FOLLOWERS_UNAVAILABLE:", type(exc).__name__, str(exc)[:130])

    old = {str(p.get("id")): p for p in prior.get("videos", [])}
    key = os.environ.get("BUFFER_API_KEY", "").strip()
    videos = []
    lookup_success = 0
    lookup_errors = 0
    for item in receipts.values():
        post_id = str(item.get("buffer_post_id") or "")
        if not post_id:
            continue
        pre = old.get(post_id, {})
        record = {
            "id": post_id, "status": pre.get("status") or "unconfirmed",
            "url": pre.get("url"), "sent_at_utc": pre.get("sent_at_utc"),
            "concept": item.get("source", "").split("/")[-1].replace(".mp4", "").replace("-", " "),
        }
        if key and pre.get("status") != "sent":
            try:
                raw = lookup_buffer_post(key, post_id)
                status = str(raw.get("status") or "unconfirmed").lower()
                record.update({
                    "status": status,
                    "url": raw.get("externalLink") if status == "sent" else None,
                    "sent_at_utc": raw.get("sentAt") if status == "sent" else None,
                })
                lookup_success += 1
            except Exception as exc:
                lookup_errors += 1
                print("BUFFER_STATUS_UNAVAILABLE", post_id, type(exc).__name__)
        if pre.get("status") == "sent":
            record["concept"] = pre.get("concept") or record["concept"]
        videos.append(record)

    # Include any confirmed older links from previous metrics not present in
    # current attempts (e.g. historical records or ledger migrations).
    ids = {p["id"] for p in videos}
    videos.extend(p for p in old.values() if p.get("id") not in ids
                  and p.get("status") == "sent")
    videos.sort(key=lambda p: p.get("sent_at_utc") or "", reverse=True)
    sent = [p for p in videos if p["status"] == "sent" and p.get("url")]
    cutoff = now - dt.timedelta(hours=24)
    posts24 = sum(1 for p in sent if
                  (parse_date(p.get("sent_at_utc")) or dt.datetime.min.replace(
                    tzinfo=dt.timezone.utc)) >= cutoff)
    pending = sum(1 for p in videos if p["status"] in
                  ("sending", "scheduled", "draft", "unconfirmed"))
    failures = sum(1 for p in videos if p["status"] in ("error", "failed"))
    data.update({
        "videos": videos[:500],
        "posted_confirmed": len(sent),
        "posted_24h": posts24,
        "pending": pending,
        "failed": failures,
        "posting_status_checked_at_utc": stamp if lookup_success else
            prior.get("posting_status_checked_at_utc"),
        "platform_data_quality": ("partially_verified" if lookup_errors or
                                  not data.get("followers_checked_at_utc")
                                  else "verified_latest_available"),
        "notes": "Only actual Buffer status=sent counts as published. "
                 "Follower numbers are public-profile snapshots; missing "
                 "data is shown as stale, not invented.",
    })
    print("DASHBOARD_SUMMARY", json.dumps({
        "followers": data.get("followers"), "sent": len(sent),
        "posts24": posts24, "pending": pending, "failures": failures,
        "buffer_queries_ok": lookup_success, "buffer_errors": lookup_errors}))
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    return data

if __name__ == "__main__":
    build()
