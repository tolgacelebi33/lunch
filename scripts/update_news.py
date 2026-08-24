#!/usr/bin/env python3
from urllib.request import Request,urlopen
from xml.etree import ElementTree as ET
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/news.json"
TZ=ZoneInfo("Europe/Stockholm")
FEEDS=[
 "https://www.svt.se/nyheter/vetenskap/rss.xml",
 "https://www.svt.se/nyheter/lokalt/vast/rss.xml",
 "https://www.svt.se/nyheter/lokalt/smaland/rss.xml",
 "https://www.svt.se/nyheter/inrikes/rss.xml",
]
BAD=re.compile(r"(?i)\b(mord|död|skjut|krig|olycka|brand|attack|våld|gripen|åtal|katastrof|bedrägeri|hot|misshandel)\w*")
GOOD=re.compile(r"(?i)\b(framsteg|forsk|rekord|ökar|lyckas|räddad|förbättr|innovation|ny teknik|återhämt|öppnar|satsning|pris|upptäckt|genombrott|lösning)\w*")

def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req,timeout=12) as r:return r.read()

def main():
    old=[]
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding="utf-8")).get("items",[])
        except:pass
    all_items=[];seen=set()
    for feed in FEEDS:
        try:
            root=ET.fromstring(fetch(feed))
            for x in root.findall(".//item")[:30]:
                title=(x.findtext("title") or "").strip()
                link=(x.findtext("link") or "").strip()
                desc=re.sub(r"<[^>]+>"," ",x.findtext("description") or "")
                desc=re.sub(r"\s+"," ",desc).strip()
                if not title or title in seen or BAD.search(title+" "+desc):continue
                seen.add(title)
                score=2 if GOOD.search(title+" "+desc) else 0
                all_items.append((score,{
                  "title":title,"summary":desc[:280],"category":"SVT Nyheter",
                  "source":"SVT","date":"","url":link
                }))
        except Exception:
            pass
    all_items.sort(key=lambda x:x[0],reverse=True)
    items=[x[1] for x in all_items[:18]]
    if len(items)<3 and old:items=old
    OUT.write_text(json.dumps({"updated_at":datetime.now(TZ).isoformat(),"items":items},ensure_ascii=False,indent=2),encoding="utf-8")
    print("svt news:",len(items))
if __name__=="__main__":main()
