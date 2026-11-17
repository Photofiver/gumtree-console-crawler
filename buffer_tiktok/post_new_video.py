#!/usr/bin/env python3
"""Post at most one NEW AI-generated video per run to the designated Buffer TikTok channel.

Safety: missing credentials -> no upload; only files named social_videos/new-*.mp4;
post receipts are committed *before* API invocation to avoid duplicate retries.
TikTok and Buffer may apply stricter creator-specific limits.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

if __package__:
    from .captions import make_caption
else:
    from captions import make_caption

ROOT = Path(__file__).resolve().parent.parent
RECEIPTS = ROOT / "buffer_tiktok" / "attempts.json"
REPO = "Photofiver/gumtree-console-crawler"
API = "https://api.buffer.com"
MAX_PER_24H = 3  # Temporary reach-recovery cap; restore only after real TikTok reach is verified
MIN_PUBLISH_SECONDS = 8.0
TARGET_HANDLE = "photofiver.photof"

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

def commit_changes(*paths):
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", *paths)
    if subprocess.call(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]) == 0:
        return
    git("commit", "-m", "Track isolated Buffer/TikTok AI-video staging")
    for _ in range(3):
        try:
            git("push", "origin", "HEAD:main")
            return
        except subprocess.CalledProcessError:
            git("pull", "--rebase", "origin", "main")
    raise RuntimeError("Could not persist GitHub safety ledger; no post made")

def load_receipts():
    if RECEIPTS.exists():
        return json.loads(RECEIPTS.read_text(encoding="utf-8"))
    return {"attempts": {}}

def save_receipts(data):
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    RECEIPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    commit_changes(str(RECEIPTS.relative_to(ROOT)))

def gql(key, query, variables=None):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Buffer API HTTP " + str(exc.code)) from None
    if body.get("errors"):
        raise RuntimeError("Buffer GraphQL request rejected") from None
    return body.get("data") or {}

def verify_tiktok_channel(key, expected=""):
    """Only select the TikTok profile explicitly requested by the user."""
    account = gql(key, "query { account { organizations { id name } } }")
    orgs = (account.get("account") or {}).get("organizations") or []
    matches = []
    for org in orgs:
        channels = gql(key, """query ($id: OrganizationId!) {
          channels(input: { organizationId: $id }) {
            id name displayName externalLink service isDisconnected isLocked
          }
        }""", {"id": org["id"]}).get("channels") or []
        for channel in channels:
            if str(channel.get("service", "")).lower() != "tiktok":
                continue
            handle = str(channel.get("name") or "").lower().strip().lstrip("@")
            url = str(channel.get("externalLink") or "").lower()
            # Buffer Channel.name is the username/handle per its official schema.
            if handle != TARGET_HANDLE and not url.rstrip("/").endswith("/@" + TARGET_HANDLE):
                continue
            if expected and str(channel["id"]) != expected:
                continue
            if channel.get("isDisconnected") or channel.get("isLocked"):
                raise RuntimeError("Target TikTok profile is disconnected or locked in Buffer")
            matches.append(channel)
    if len(matches) != 1:
        raise RuntimeError("Cannot uniquely verify TikTok account @"+TARGET_HANDLE+" in Buffer")
    verified = matches[0]
    print("Verified Buffer account: @"+TARGET_HANDLE+" (TikTok channel confirmed)", flush=True)
    return str(verified["id"])

def ffprobe(path):
    return json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        text=True))

def ready_video(source):
    info = ffprobe(source)
    stream = next(s for s in info["streams"] if s.get("codec_type") == "video")
    duration = float(info["format"]["duration"])
    fps_parts = stream.get("avg_frame_rate", "0/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1])
    if duration < MIN_PUBLISH_SECONDS or duration > 600:
        raise RuntimeError("Recovery mode: reject short clips below 8 seconds")
    if fps >= 23 and fps <= 60 and stream.get("codec_name") == "h264":
        return source
    target = ROOT / "social_videos" / "buffer-ready" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
      "-i", str(source), "-r", "25", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
      "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(target)],
      check=True, timeout=120)
    check = ffprobe(target)
    vs = next(s for s in check["streams"] if s.get("codec_type") == "video")
    assert vs["codec_name"] == "h264"
    commit_changes(str(target.relative_to(ROOT)))
    return target

def main():
    key = os.getenv("BUFFER_API_KEY", "").strip()
    channel_id = os.getenv("BUFFER_TIKTOK_CHANNEL_ID", "").strip()
    if not key:
        print("DISABLED: No BUFFER_API_KEY GitHub Secret. Connect @"+TARGET_HANDLE+" in Buffer and save an API key.")
        return
    state = load_receipts()
    attempts = state.setdefault("attempts", {})
    now = dt.datetime.now(dt.timezone.utc)
    recent = 0
    for a in attempts.values():
        try:
            age = (now - dt.datetime.fromisoformat(a["attempted_at"])).total_seconds()
            if 0 <= age < 86400:
                recent += 1
        except (ValueError, KeyError):
            pass
    if recent >= MAX_PER_24H:
        print("RECOVERY LIMIT: 3 API attempts in rolling 24 hours. Avoids high-volume zero-view uploads.")
        return
    # Old 3-second clips stay on disk as an audit trail but must NEVER be
    # uploaded during reach recovery. Use only validated new multi-shot films.
    sources = sorted((ROOT / "social_videos").glob("new-ai-cat-*.mp4"))
    available = []
    for src in sources:
        sidecar = src.with_suffix(".json")
        if not sidecar.exists():
            continue
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            seconds = float(meta.get("validation", {}).get("seconds", 0))
            unique_shots = int(meta.get("unique_original_shots", 0))
            if seconds < MIN_PUBLISH_SECONDS or unique_shots < 3:
                print("RECOVERY_SKIP_SHORT_OR_SINGLE_SHOT", src.name, seconds)
                continue
        except (ValueError, TypeError, OSError):
            continue
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        if sha not in attempts:
            available.append((src, sha))
    if not available:
        print("NO NEW AI VIDEO: existing clips will never be reposted.")
        return
    last = state.get("buffer_channel_last_verified_utc")
    try:
        verification_age = (now - dt.datetime.fromisoformat(last)).total_seconds()
    except (TypeError, ValueError):
        verification_age = 9999999
    cached_id = state.get("buffer_channel_id")
    # Verify exact handle before first publish and at least once daily.
    # This also avoids asking the non-technical user to find a channel ID.
    if not cached_id or not 0 <= verification_age < 86400 or (channel_id and channel_id != cached_id):
        cached_id = verify_tiktok_channel(key, channel_id)
        state["buffer_channel_id"] = cached_id
        state["buffer_channel_last_verified_utc"] = now.isoformat()
    channel_id = cached_id
    source, sha = available[0]
    finished = ready_video(source)
    url = "https://raw.githubusercontent.com/" + REPO + "/main/" + str(finished.relative_to(ROOT))
    caption = make_caption(source)
    print("New video-specific caption:", caption, flush=True)
    attempts[sha] = {
        "source": str(source.relative_to(ROOT)),
        "ready_url": url,
        "attempted_at": now.isoformat(),
        "status": "attempt_reserved_before_network_call"
    }
    save_receipts(state)
    print("Reserved one new AI video for TikTok, without duplicate retry.", flush=True)
    query = """mutation($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess { post { id text dueAt } }
        ... on MutationError { message }
      }
    }"""
    variables = {"input": {
        "text": caption,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "shareNow",
        "assets": [{"video": {"url": url}}],
        "metadata": {"tiktok": {"isAiGenerated": True}},
        "aiAssisted": True
    }}
    try:
        data = gql(key, query, variables)
        result = data.get("createPost") or {}
        item = result.get("post")
        if not item or not item.get("id"):
            attempts[sha]["status"] = "buffer_rejected_or_unconfirmed"
            save_receipts(state)
            print("Buffer did not confirm a post; automatic retry disabled.", flush=True)
            return
        attempts[sha]["status"] = "submitted_to_buffer"
        attempts[sha]["buffer_post_id"] = str(item["id"])
        save_receipts(state)
        print("SUBMITTED_TO_BUFFER post_id:", item["id"],
              "Verify actual TikTok delivery in Buffer; submission is not final publication.", flush=True)
    except Exception:
        # The provider may have accepted the post even when our connection failed.
        # Do not automatically retry, or a double posting could occur.
        attempts[sha]["status"] = "ambiguous_or_failed_no_retry"
        save_receipts(state)
        raise

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Publishing run stopped:", str(exc)[:220], file=sys.stderr)
        raise SystemExit(1)
