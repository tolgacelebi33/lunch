#!/usr/bin/env python3
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
from datetime import datetime, timezone
import json, re, ssl

URLS = [
    "https://glasetshuslimmared.se/lunch/",
    "https://glasetshuslimmared.se/nasta-vecka/",
]
OUT = Path(__file__).resolve().parents[1] / "data" / "glasets-hus-probe.json"

def fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
    }
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        return {
            "ok": True,
            "url": r.geturl(),
            "status": r.status,
            "bytes": len(raw),
            "content_type": r.headers.get("Content-Type", ""),
            "title": (re.search(r"<title[^>]*>(.*?)</title>", text, re.I|re.S).group(1).strip()
                      if re.search(r"<title[^>]*>(.*?)</title>", text, re.I|re.S) else None),
            "mentions_week": sorted(set(re.findall(r"(?:vecka|v\.?)\s*(\d{1,2})", text, re.I))),
            "html_sample": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))[:800],
        }

def main():
    results = []
    for url in URLS:
        try:
            results.append(fetch(url))
        except HTTPError as e:
            results.append({"ok": False, "url": url, "error": f"HTTP {e.code}: {e.reason}"})
        except URLError as e:
            results.append({"ok": False, "url": url, "error": f"URL error: {e.reason}"})
        except Exception as e:
            results.append({"ok": False, "url": url, "error": f"{type(e).__name__}: {e}"})
    payload = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not any(x.get("ok") for x in results):
        raise SystemExit("Neither Glasets Hus URL could be fetched.")

if __name__ == "__main__":
    main()
