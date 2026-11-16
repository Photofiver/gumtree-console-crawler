#!/usr/bin/env python3
"""Safe account-specific TikTok publishing using Buffer's documented GraphQL API.
Never posts to other accounts. Never simulates TikTok credentials or claims sent
without API evidence. The first account connection must be authorized by owner.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

BASE="https://api.buffer.com"
EXPECTED="photofiver.photof"
REPORT=Path("autopost_tiktok/last-publish-report.json")
CHECK=Path("autopost_tiktok/preflight-status.json")

def write(path, data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def gql(key, query, variables=None):
    payload=json.dumps({"query":query,"variables":variables or {}}).encode()
    req=urllib.request.Request(BASE,data=payload,method="POST",
         headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=35) as response:
            data=json.load(response)
    except urllib.error.HTTPError as ex:
        # No response body printing: third-party error bodies may contain sensitive data.
        raise RuntimeError(f"Buffer API HTTP {ex.code}") from None
    if data.get("errors"):
        raise RuntimeError("Buffer GraphQL error: "+
            "; ".join(str(e.get("message","unknown"))[:240] for e in data["errors"]))
    return data.get("data",{})

def find_account(key):
    data=gql(key,"query GetOrganizations { account { organizations { id name } } }")
    orgs=data.get("account",{}).get("organizations",[])
    if not orgs:
        raise RuntimeError("No Buffer organizations found; account not connected")
    hits=[]
    for org in orgs:
        data=gql(key,"query GetChannels($organizationId:OrganizationId!){ channels(input:{organizationId:$organizationId}){id name displayName service externalLink isDisconnected}}",
                 {"organizationId":org["id"]})
        for ch in data.get("channels",[]):
            if str(ch.get("service","")).lower()!="tiktok":
                continue
            possible=[str(ch.get(k) or "").lower().replace("@","").strip() for k in ("name","displayName")]
            link=str(ch.get("externalLink") or "").lower()
            from urllib.parse import urlparse
            path=urlparse(link).path.rstrip("/").lower()
            exact=EXPECTED in possible or path=="/@"+EXPECTED
            if exact:
                hits.append(ch)
    if len(hits)!=1:
        raise RuntimeError(f"Expected exactly one connected TikTok @{EXPECTED} in Buffer; found {len(hits)}")
    if hits[0].get("isDisconnected"):
        raise RuntimeError("TikTok connection in Buffer has expired")
    return hits[0]

def preflight():
    key=os.environ.get("BUFFER_API_KEY","")
    if not key:
        write(CHECK,{"ready":False,"reason":"BUFFER_API_KEY secret is not configured; TikTok not connected through Buffer"})
        print("BLOCKED: Buffer API key missing; nothing published")
        return False,None
    try:
        account=find_account(key)
    except Exception as exc:
        write(CHECK,{"ready":False,"reason":str(exc)})
        print("BLOCKED:",exc)
        return False,None
    write(CHECK,{"ready":True,"tiktok":"@"+EXPECTED,"channel_id":account["id"]})
    print("VERIFIED connected Buffer TikTok channel: @"+EXPECTED)
    return True,account

if __name__=="__main__":
    mode=sys.argv[1] if len(sys.argv)>1 else "check"
    ready,account=preflight()
    if mode=="check":
        # Do not spend GPU quota until an authenticated channel is verified.
        with open(os.environ.get("GITHUB_OUTPUT","/dev/null"),"a") as f:
            f.write("ready="+("true" if ready else "false")+"\n")
        sys.exit(0)
    if mode!="send":
        raise SystemExit("Unknown mode")
    if not ready:
        raise SystemExit("Refusing to publish: no verified linked TikTok account")
    report=json.loads(Path("autopost_tiktok/last-generation-report.json").read_text())
    if not report.get("generated") or not report.get("speech_verified"):
        raise SystemExit("Refusing to publish: video or Polish speech unverified")
    file=Path(report["file"])
    if not file.is_file():
        raise SystemExit("Generated video missing")
    # Need public git-hosted URL; repo's identity is fixed, no arbitrary third-party content.
    from urllib.parse import quote
    url="https://raw.githubusercontent.com/Photofiver/gumtree-console-crawler/main/"+quote(file.as_posix())
    req=urllib.request.Request(url,method="HEAD")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req,timeout=20) as resp:
                content_type=resp.headers.get("Content-Type","")
                if resp.status==200 and ("video" in content_type or "octet-stream" in content_type):
                    break
        except (urllib.error.URLError,TimeoutError):
            pass
        time.sleep(3)
    else:
        raise SystemExit("Published MP4 URL not yet publicly readable; no TikTok submission made")
    message=(report["caption_line"]+" #kot #zabawnekoty #AI #polskitiktok")
    mutation="""mutation CreatePost($input:CreatePostInput!){
        createPost(input:$input) {
          ... on PostActionSuccess {post {id status externalLink}}
          ... on MutationError {message}
        }
    }"""
    payload={"text":message,"channelId":account["id"],
             "schedulingType":"automatic","mode":"shareNow",
             "assets":[{"video":{"url":url}}],
             "aiAssisted":True,
             "metadata":{"tiktok":{"isAiGenerated":True}}}
    # Single write request, no retry on ambiguous outcomes (avoid double posting).
    out=gql(os.environ["BUFFER_API_KEY"],mutation,{"input":payload})
    result=out.get("createPost") or {}
    if "post" not in result:
        raise RuntimeError("Buffer rejected createPost: "+str(result.get("message","Unknown error"))[:250])
    post=result["post"]
    result_data={"timestamp":datetime.now(timezone.utc).isoformat(),"tiktok":"@"+EXPECTED,
        "slot":report["slot"],"video_url":url,"buffer_post_id":post.get("id"),
        "buffer_status":post.get("status"),"tiktok_post_url":post.get("externalLink"),
        "publication_verified":str(post.get("status","")).lower()=="sent"}
    write(REPORT,result_data)
    print("BUFFER RESPONSE status=",result_data["buffer_status"],
          "id=",result_data["buffer_post_id"],"sent=",result_data["publication_verified"])
    if not result_data["publication_verified"]:
        print("Posting submitted to Buffer; TikTok final publication not yet verified.")
