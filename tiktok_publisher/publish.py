"""Isolated TikTok API adapter. Default mode never uploads or publishes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ACCOUNT = "photofiver.photof"
REPO = "Photofiver/gumtree-console-crawler"
API = "https://open.tiktokapis.com/v2/post/publish/"


class Blocked(Exception):
    pass


def api(endpoint, token, payload):
    req = urllib.request.Request(API + endpoint, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    # Do not follow redirects with a bearer token.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        try:
            result = json.load(error)
        except Exception:
            raise Blocked("API_HTTP_" + str(error.code)) from None
    except Exception:
        raise Blocked("API_NETWORK_OR_JSON_ERROR") from None
    code = result.get("error", {}).get("code", "missing_error_code")
    if code != "ok":
        # Never log arbitrary API messages or credential-bearing responses.
        safe = re.sub(r"[^a-zA-Z0-9_]", "", str(code))[:90]
        raise Blocked("TIKTOK_API_" + safe)
    return result.get("data", {})


def source(path, sha):
    root = Path.cwd().resolve()
    candidate = Path(path)
    resolved = candidate.resolve()
    if (candidate.is_absolute() or ".." in candidate.parts or
            not path.startswith("social_videos/") or resolved.suffix.lower() != ".mp4" or
            not resolved.is_relative_to(root / "social_videos") or not resolved.is_file()):
        raise Blocked("INVALID_REPOSITORY_MP4")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise Blocked("IMMUTABLE_COMMIT_REQUIRED")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    try:
        probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format",
            "-show_streams", "-of", "json", str(resolved)], stderr=subprocess.DEVNULL))
        duration = float(probe["format"]["duration"])
        if duration <= 0 or not any(s.get("codec_type") == "video" for s in probe["streams"]):
            raise ValueError()
    except Exception:
        raise Blocked("INVALID_VIDEO_OR_FFPROBE_MISSING") from None
    url = "https://raw.githubusercontent.com/" + REPO + "/" + sha + "/" + urllib.parse.quote(path, safe="/")
    return {"sha256": digest, "duration": duration, "video_url": url}


def validate_post(creator, media, settings, caption):
    if creator.get("creator_username") != ACCOUNT:
        raise Blocked("WRONG_TIKTOK_ACCOUNT")
    privacy = settings.get("privacy_level")
    if privacy not in creator.get("privacy_level_options", []):
        raise Blocked("SELECT_AVAILABLE_PRIVACY_LEVEL")
    if media["duration"] > creator.get("max_video_post_duration_sec", 0):
        raise Blocked("VIDEO_TOO_LONG")
    if len(caption.encode("utf-16-le")) // 2 > 2200:
        raise Blocked("CAPTION_TOO_LONG")
    post = {"title": caption, "privacy_level": privacy, "is_aigc": True}
    for interaction in ("comment", "duet", "stitch"):
        enabled = settings.get("allow_" + interaction, False)
        if type(enabled) is not bool:
            raise Blocked("INTERACTION_MUST_BE_BOOLEAN")
        if enabled and creator.get(interaction + "_disabled", True):
            raise Blocked("INTERACTION_DISABLED_BY_CREATOR")
        post["disable_" + interaction] = not enabled
    for field in ("brand_content_toggle", "brand_organic_toggle"):
        value = settings.get(field, False)
        if type(value) is not bool:
            raise Blocked("BRAND_SETTING_MUST_BE_BOOLEAN")
        post[field] = value
    if post["brand_content_toggle"] and privacy == "SELF_ONLY":
        raise Blocked("BRANDED_CONTENT_CANNOT_BE_PRIVATE")
    return post


def run(report):
    mode = os.getenv("MODE", "preflight")
    if mode not in ("preflight", "publish", "status"):
        raise Blocked("UNKNOWN_MODE")
    token = next((os.getenv(name) for name in ("TIKTOK_ACCESS_TOKEN", "TIKTOK_TOKEN",
        "TIKTOK_OAUTH_ACCESS_TOKEN", "TIKTOK_API_ACCESS_TOKEN") if os.getenv(name)), None)
    if not token:
        report["api_permission_verified"] = False
        raise Blocked("MISSING_TIKTOK_ACCESS_TOKEN")
    creator = api("creator_info/query/", token, {})
    if creator.get("creator_username") != ACCOUNT:
        raise Blocked("WRONG_TIKTOK_ACCOUNT")
    report.update(api_permission_verified=True, account=ACCOUNT,
        privacy_level_options=creator.get("privacy_level_options"),
        max_video_post_duration_sec=creator.get("max_video_post_duration_sec"))
    if mode == "status":
        publish_id = os.getenv("PUBLISH_ID", "")
        if not publish_id:
            raise Blocked("PUBLISH_ID_REQUIRED")
    else:
        media = source(os.getenv("VIDEO_PATH", ""), os.getenv("GITHUB_SHA", ""))
        report.update(sha256=media["sha256"], duration=media["duration"])
        if mode == "preflight":
            report["result"] = "PREFLIGHT_OK_NO_UPLOAD_AUDIT_NOT_VERIFIED"
            return
        if os.getenv("GITHUB_RUN_ATTEMPT", "1") != "1":
            raise Blocked("DO_NOT_RERUN_PUBLICATION_USE_STATUS")
        if os.getenv("APP_READY") != "true":
            raise Blocked("APP_APPROVAL_AND_OAUTH_SETUP_NOT_CONFIRMED")
        if os.getenv("CONSENT") != "PUBLISH @" + ACCOUNT + " " + media["sha256"]:
            raise Blocked("EXPLICIT_APPROVAL_FOR_THIS_VIDEO_REQUIRED")
        try:
            settings = json.loads(os.getenv("POST_SETTINGS", "{}"))
        except ValueError:
            raise Blocked("INVALID_POST_SETTINGS") from None
        if not isinstance(settings, dict) or settings.get("music_usage_confirmed") is not True:
            raise Blocked("MUSIC_USAGE_CONFIRMATION_REQUIRED")
        if settings.get("brand_content_toggle") and settings.get("branded_content_policy_confirmed") is not True:
            raise Blocked("BRANDED_CONTENT_POLICY_CONFIRMATION_REQUIRED")
        caption = os.getenv("CAPTION", "")
        post = validate_post(creator, media, settings, caption)
        # Server-side media requires PULL_FROM_URL and a TikTok-verified URL property.
        prefix = os.getenv("VERIFIED_URL_PREFIX", "")
        expected = "https://raw.githubusercontent.com/" + REPO + "/"
        if prefix != expected:
            raise Blocked("TIKTOK_VERIFIED_REPOSITORY_URL_PREFIX_REQUIRED")
        response = api("video/init/", token, {"post_info": post,
            "source_info": {"source": "PULL_FROM_URL", "video_url": media["video_url"]}})
        publish_id = response.get("publish_id")
        if not publish_id:
            raise Blocked("INIT_OUTCOME_UNKNOWN_DO_NOT_RETRY")
        report["publish_id"] = publish_id
        write_report(report)  # Persist receipt immediately; do not re-init on timeout.
    report["publish_id"] = publish_id
    for _ in range(30 if mode == "publish" else 1):
        data = api("status/fetch/", token, {"publish_id": publish_id})
        status = data.get("status", "UNKNOWN")
        report["publish_status"] = status
        if status == "PUBLISH_COMPLETE":
            ids = data.get("publicaly_available_post_id", [])
            report["public_post_urls"] = ["https://www.tiktok.com/@" + ACCOUNT + "/video/" + str(i)
                for i in ids if re.fullmatch(r"[0-9]+", str(i))]
            report["result"] = "PUBLISH_COMPLETE"
            return
        if status == "FAILED":
            raise Blocked("PUBLISH_FAILED")
        if mode == "publish":
            time.sleep(10)
    raise Blocked("PENDING_CHECK_STATUS_DO_NOT_REPUBLISH")


def write_report(report):
    Path("tiktok-result.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    report = {"mode": os.getenv("MODE", "preflight"), "result": "NOT_COMPLETED"}
    try:
        run(report)
    except Blocked as error:
        report["result"] = str(error)
    except Exception:
        report["result"] = "UNEXPECTED_ERROR_NO_AUTOMATIC_RETRY"
    write_report(report)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["result"] in ("PUBLISH_COMPLETE", "PREFLIGHT_OK_NO_UPLOAD_AUDIT_NOT_VERIFIED") else 1)
