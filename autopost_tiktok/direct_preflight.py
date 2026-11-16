#!/usr/bin/env python3
"""Read-only TikTok Direct Post authorization test; no Buffer, no uploads.

Keeps the four-hour GitHub workflow safely idle until TikTok OAuth app and
creator's video.publish scope are authorized. TikTok requires preview and
express per-video consent before every upload.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TARGET = "photofiver.photof"
API = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
OUTPUT = Path("autopost_tiktok/preflight-status.json")

def save(ready, reason, **extra):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"ready":ready,"reason":reason,**extra},
                                 ensure_ascii=False, indent=2)+"\n",encoding="utf8")
    print("TikTok preflight:",reason)
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target,"a",encoding="utf8") as f:
            f.write("authorized="+("true" if ready else "false")+"\n")

def check():
    token = next((os.environ.get(key) for key in (
       "TIKTOK_ACCESS_TOKEN","TIKTOK_OAUTH_ACCESS_TOKEN",
       "TIKTOK_API_ACCESS_TOKEN","TIKTOK_TOKEN") if os.environ.get(key)), None)
    if not token:
        save(False,"No authorized TikTok access token in supported GitHub Secrets")
        return
    req = urllib.request.Request(API, method="POST", data=b"{}",
        headers={"Authorization":"Bearer "+token,
                 "Content-Type":"application/json; charset=UTF-8"})
    class DoNotRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(DoNotRedirect()).open(req, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        # HTTP error may expose account or credential info; do not print the body.
        save(False,f"TikTok returned HTTP {exc.code}")
        return
    except (urllib.error.URLError,TimeoutError,ValueError):
        save(False,"TikTok unavailable or returned unreadable response")
        return
    code = payload.get("error",{}).get("code")
    if code!="ok":
        safe=str(code or "UNKNOWN").replace("\n","")[:60]
        save(False,"TikTok creator_info authorization rejected: "+safe)
        return
    creator=payload.get("data") or {}
    username=str(creator.get("creator_username","")).lower().lstrip("@")
    if username!=TARGET:
        save(False,"Token authorized for an unexpected TikTok account, not @"+TARGET)
        return
    save(True,"TikTok account and video.publish authorization verified",
         username=TARGET,privacy_options=creator.get("privacy_level_options",[]))
    print("NOTICE: This check does not authorize autonomous public posting.")
    print("TikTok requires a video preview and express consent for each post.")

if __name__=="__main__":
    check()
