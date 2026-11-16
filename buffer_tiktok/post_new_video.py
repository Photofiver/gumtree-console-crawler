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

ROOT = Path(__file__).resolve().parent.parent
RECEIPTS = ROOT / "buffer_tiktok" / "attempts.json"
REPO = "Photofiver/gumtree-console-crawler"
API = "https://api.buffer.com"
MAX_PER_24H = 15

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

def commit_changes(*paths):
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", *paths)
    if not subprocess.call(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"]):
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

def verify_tiktok_channel(key, expected):
    account = gql(key, "query { account { organizations { id name } } }")
    orgs = (account.get("account") or {}).get("organizations") or []
    for org in orgs:
        channels = gql(key, """query ($id: OrganizationId!) {
          channels(input: { organizationId: $id }) { id name service }
        }""", {"id": org["id"]}).get("channels") or []
        for channel in channels:
            if str(channel["id"]) == expected and str(channel["service"]).lower() == "tiktok":
                print("Verified Buffer TikTok channel:", channel.get("name", ""), flush=True)
                return
    raise RuntimeError("Selected Buffer channel ID is not a connected TikTok channel")

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
    if duration < 3.0 or duration > 600:
        raise RuntimeError("Video length outside supported TikTok range")
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
    if not key or not channel_id:
        print("DISABLED: Buffer account/API key or connected TikTok channel ID is missing.")
        return
    verify_tiktok_channel(key, channel_id)
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
        print("SAFETY LIMIT: 15 API attempts in rolling 24 hours.")
        return
    sources = sorted((ROOT / "social_videos").glob("new-*.mp4"))
    candidates = [(src, hashlib.sha256(src.read_bytes()).hexdigest()) for src in sources]
    available = [(src, sha) for src, sha in candidates if sha not in attempts]
    if not available:
        print("NO NEW AI VIDEO: existing clips will never be reposted.")
        return
    source, sha = available[0]
    finished = ready_video(source)
    url = "https://raw.githubusercontent.com/" + REPO + "/main/" + str(finished.relative_to(ROOT))
    caption = "Nowy film wygenerowany przez AI. #AI #AIGenerated #kot #cat"
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
