"""Probe Google AI Mode with Chrome on GitHub-hosted Ubuntu; no Android emulator."""
import json
import os
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options

question = (os.getenv("CHROME_TEST_QUESTION") or "Czy 2+2=4? Odpowiedz krótko po polsku.").strip()[:750]
url = "https://www.google.com/search?udm=50&hl=pl&q=" + quote(question)
result = {"status": "ERROR", "browser": "Chrome headless", "elapsed_seconds": 0, "ready": False, "preview": "", "error": ""}
start = time.monotonic()
browser = None
try:
    options = Options()
    for arg in ("--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu", "--window-size=1280,1024", "--lang=pl-PL"):
        options.add_argument(arg)
    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(22)
    try:
        browser.get(url)
    except TimeoutException:
        pass
    text = ""
    for _ in range(20):
        try:
            text = browser.execute_script("return document.body ? document.body.innerText : '';") or ""
        except Exception:
            text = ""
        if ("Odpowiedź trybu AI jest gotowa" in text or "AI Mode response is ready" in text):
            result["ready"] = True
            break
        if time.monotonic() - start >= 62:
            break
        time.sleep(2)
    result["status"] = "READY" if result["ready"] else "NO_AI_RESPONSE"
    result["preview"] = text[-3800:]
    result["text_length"] = len(text)
    result["page_title"] = browser.title
    result["page_url"] = browser.current_url.split("&sei=")[0][:1100]
except Exception as exc:
    result["error"] = type(exc).__name__ + ": " + str(exc)[:800]
finally:
    result["elapsed_seconds"] = round(time.monotonic() - start, 1)
    if browser is not None:
        browser.quit()
    with open("chrome-ai-test-result.json", "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key not in ("preview", "page_url")}, ensure_ascii=False))
