"""Access-controlled HTTPS-tunnel gateway for a temporary GitHub Actions browser.

Only the SHA-256 of the secret is placed in the public issue. The actual
secret is passed in the URL fragment (never sent to GitHub or Cloudflare
until the user authorizes an API call). Never save Blueprint credentials.
"""
import asyncio
import hashlib
import json
import os
import re
from aiohttp import ClientSession, ClientTimeout, web
from pathlib import Path

ALLOWED = {"/screen","/status","/click","/type","/key","/scroll","/home"}
FRONTEND = Path(__file__).with_name("live.html")
EXPECTED = os.environ.get("BLUEPRINT_ACCESS_SHA256", "")
if not re.fullmatch(r"[0-9a-f]{64}", EXPECTED):
    raise SystemExit("Invalid bridge SHA-256 verifier")

@web.middleware
async def check(request, handler):
    if request.path in ALLOWED:
        secret = request.headers.get("X-Bridge-Token", "")
        if len(secret) != 64 or not re.fullmatch(r"[0-9a-f]{64}", secret):
            return web.Response(status=403, text="Access denied")
        if not hashlib.sha256(secret.encode("ascii")).hexdigest() == EXPECTED:
            return web.Response(status=403, text="Access denied")
    if request.method == "POST":
        origin,host = request.headers.get("Origin"),request.headers.get("Host")
        if origin not in {f"https://{host}",f"http://{host}"}:
            return web.Response(status=403, text="Invalid origin")
    response = await handler(request)
    response.headers["Cache-Control"]="no-store"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response

async def homepage(request):
    return web.Response(text=FRONTEND.read_text("utf-8"), content_type="text/html")

async def gateway(request):
    if request.path not in ALLOWED:
        raise web.HTTPNotFound()
    payload = await request.read()
    if len(payload)>4096:
        raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=len(payload))
    async with request.app["client"].request(request.method,
        "http://127.0.0.1:8765"+request.path,
        data=payload,headers={"Content-Type":request.content_type},
        allow_redirects=False) as response:
        body = await response.read()
        # Do not forward arbitrary browser-origin or proxy headers.
        return web.Response(status=response.status,body=body,
            content_type=response.content_type)

async def start_session(app):
    app["client"]=ClientSession(timeout=ClientTimeout(total=25))
    yield
    await app["client"].close()

app=web.Application(middlewares=[check],client_max_size=4096)
app.cleanup_ctx.append(start_session)
app.add_routes([web.get("/",homepage),
                web.get("/screen",gateway),web.get("/status",gateway),
                web.post("/click",gateway),web.post("/type",gateway),
                web.post("/key",gateway),web.post("/scroll",gateway),
                web.post("/home",gateway)])
if __name__=="__main__":
    web.run_app(app,host="127.0.0.1",port=8766,access_log=None)
