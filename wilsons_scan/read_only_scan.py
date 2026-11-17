#!/usr/bin/env python3
"""Read-only scan of Wilsons Belfast lots. Never logs in, bids or modifies auctions."""
import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

AUCTIONS = [
    ("Catering Auction", "https://www.wilsonsauctions.com/auctions/catering-auction-5981"),
    ("Tools & Equipment", "https://www.wilsonsauctions.com/auctions/tools-equipment-auction-6309"),
    ("Unreserved Battery", "https://www.wilsonsauctions.com/auctions/unreserved-battery-auction-6347"),
    ("Seized Vehicle", "https://www.wilsonsauctions.com/auctions/seized-vehicle-auction-6323"),
]
LOT = re.compile(r"(?:^|\n)LOT\s*\n\s*(\d+)\s*\n(.*?)(?=\nLOT\s*\n\s*\d+\s*\n|\n\d+\s+of\s+\d+\s*\n|\Z)", re.S)
def value(pattern, body):
    m = re.search(pattern, body, re.I | re.S)
    return m.group(1).strip() if m else ""

def parse_lots(text, name, url, page_index):
    rows = []
    for m in LOT.finditer(text):
        body = m.group(2)
        lines = [s.strip() for s in body.splitlines() if s.strip()]
        title = lines[0] if lines else ""
        if not title: continue
        location = value(r"Lot location:\s*\n([^\n]+)", body)
        premium = value(r"(\d+)% Buyers Premium",body)
        bid = value(r"Current bid\s*\n£([\d,]+(?:\.\d+)?)",body)
        rows.append(dict(auction=name, auction_url=url, lot=int(m.group(1)), title=title[:220], location=location, premium_pct=int(premium) if premium else None, current_bid_gbp=float(bid.replace(",","")) if bid else None, page=page_index))
    return rows

def main():
    report={"scanned_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"auctions":[],"lots":[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
        context=browser.new_context(viewport={"width":1280,"height":900},accept_downloads=False)
        def safe_requests(route):
            if route.request.method.upper() not in ("GET","HEAD"):
                return route.abort()
            return route.continue_()
        context.route("**/*",safe_requests)
        page=context.new_page()
        page.set_default_timeout(9000)
        for name,url in AUCTIONS:
            record={"name":name,"url":url,"pages":0,"lots_found":0,"errors":[]}
            report["auctions"].append(record)
            try:
                page.goto(url,wait_until="domcontentloaded",timeout=30000)
                try:
                    page.wait_for_function("document.body && /Showing\s+\d+\s+Lots/.test(document.body.innerText)",timeout=18000)
                except Exception:
                    page.reload(wait_until="domcontentloaded",timeout=30000)
                    try: page.wait_for_function("document.body && /Showing\s+\d+\s+Lots/.test(document.body.innerText)",timeout=16000)
                    except Exception: pass
                for index in range(1,35):
                    txt=page.locator("body").inner_text(timeout=10000)
                    num_rows=parse_lots(txt,name,url,index)
                    anchors=page.locator("a[href]").evaluate_all("""els => els.map(a => ({
                      text: (a.innerText || a.getAttribute('title') || '').replace(/\\s+/g, ' ').trim().slice(0, 300),
                      url: a.href
                    })).filter(a => a.url.startsWith('https://www.wilsonsauctions.com/'))""")
                    for row in num_rows:
                        norm=lambda s: re.sub(r"\\s+"," ",s).strip().casefold()
                        matches=[a for a in anchors if norm(row["title"]) in norm(a["text"]) and a["url"] != url]
                        if matches:
                            row["detail_url"]=matches[0]["url"]
                    if not num_rows:
                        record["errors"].append("No lot rows on page "+str(index)+": "+txt[:280])
                        break
                    old_nums={r["lot"] for r in report["lots"] if r["auction"]==name}
                    for row in num_rows:
                        if row["lot"] not in old_nums:
                            report["lots"].append(row)
                    record["pages"]+=1
                    record["lots_found"]=len([r for r in report["lots"] if r["auction"]==name])
                    pg=re.search(r"\n(\d+)\s+of\s+(\d+)\s*\n",txt)
                    total=int(pg.group(2)) if pg else None
                    if total and index>=total: break
                    prev_marker=num_rows[0]["lot"]
                    clicked=False
                    for sel in ("button:has-text('›')","a:has-text('›')","text=›"):
                        try:
                            all_=page.locator(sel)
                            for j in range(all_.count()-1,-1,-1):
                                cand=all_.nth(j)
                                if cand.is_visible() and cand.is_enabled():
                                    cand.click(timeout=4500,force=True)
                                    clicked=True
                                    break
                            if clicked: break
                        except Exception: pass
                    if not clicked:
                        record["errors"].append("Could not find next-page arrow on page "+str(index))
                        break
                    try:
                        page.wait_for_function(r"""n => {
                          const t = document.body.innerText;
                          const m=t.match(/LOT\s*\n\s*(\d+)/);
                          return m && Number(m[1]) !== n;
                        }""",arg=prev_marker,timeout=8500)
                    except Exception:
                        record["errors"].append("Next page did not visibly update after page "+str(index))
                        break
                    page.wait_for_timeout(300)
            except Exception as exc:
                record["errors"].append(type(exc).__name__+": "+str(exc)[:400])
            print(json.dumps(record,ensure_ascii=False),flush=True)
        context.close()
        browser.close()
    report["belfast_lots"]=[x for x in report["lots"] if "belfast" in x["location"].lower() or "newtownabbey" in x["location"].lower()]
    Path("wilsons-belfast-scan.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("TOTAL",len(report["lots"]),"BELFAST",len(report["belfast_lots"]))
if __name__=="__main__":
    main()
