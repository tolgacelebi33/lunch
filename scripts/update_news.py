#!/usr/bin/env python3
from urllib.request import Request,urlopen
from urllib.parse import quote
from xml.etree import ElementTree as ET
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"data/news.json"; TZ=ZoneInfo("Europe/Stockholm")
queries=["framsteg Sverige","forskning genombrott Sverige","positiva nyheter Sverige","innovation Sverige","natur återhämtning Sverige"]
items=[];seen=set()
for q in queries:
    url="https://news.google.com/rss/search?q="+quote(q)+"&hl=sv&gl=SE&ceid=SE:sv"
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0"})
        root=ET.fromstring(urlopen(req,timeout=30).read())
        for x in root.findall(".//item")[:8]:
            title=(x.findtext("title") or "").strip();link=(x.findtext("link") or "").strip()
            if not title or title in seen:continue
            seen.add(title)
            source=(x.findtext("source") or "Nyheter").strip()
            # Filter obvious negative/crime/disaster topics; pool is for light lunch conversation.
            if re.search(r"(?i)\b(död|mord|krig|skjut|olycka|brand|attack|våld|gripen|åtal|katastrof)\w*",title):continue
            items.append({"title":title,"summary":"","category":"Positivt / konstruktivt","source":source,"date":"","talk_about":"Vad tycker du är mest intressant med det här?","url":link})
    except Exception:pass
payload={"updated_at":datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),"items":items[:20]}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print("news:",len(payload["items"]))
