#!/usr/bin/env python3
from urllib.request import Request, urlopen
from html import unescape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/commodities.json"
TZ=ZoneInfo("Europe/Stockholm")

SOURCES=[
 ("Stål","https://tradingeconomics.com/commodity/steel","CNY/t","Steel rebar"),
 ("Plåt / HRC","https://tradingeconomics.com/commodity/hrc-steel","USD/t","HRC Steel"),
 ("Trä","https://tradingeconomics.com/commodity/lumber","USD/1000 bf","Lumber"),
 ("Skivmaterial","https://tradingeconomics.com/commodity/kraft-pulp","CNY/t","Kraft pulp-proxy"),
 ("Porslin","https://tradingeconomics.com/commodity/soda-ash","CNY/t","Soda ash-proxy"),
]

def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 Chrome/127 Safari/537.36","Accept-Language":"en-US,en;q=0.9"})
    with urlopen(req,timeout=12) as r:
        return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")

def textify(h):
    h=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",h)
    h=re.sub(r"(?s)<[^>]+>"," ",h)
    return re.sub(r"\s+"," ",unescape(h)).strip()

def num(s):
    if s is None:return None
    try:return float(s.replace(",","").replace("%","").strip())
    except:return None

def embedded(h, keys):
    for k in keys:
        pats=[
          rf'"{re.escape(k)}"\s*:\s*(-?\d+(?:\.\d+)?)',
          rf'{re.escape(k)}\s*[:=]\s*["\']?(-?\d+(?:\.\d+)?)',
        ]
        for p in pats:
            m=re.search(p,h,re.I)
            if m:return num(m.group(1))
    return None

def parse_page(h):
    t=textify(h)
    def grab(label):
        m=re.search(rf'{re.escape(label)}\s+(-?\d+(?:,\d{{3}})*(?:\.\d+)?)%?',t,re.I)
        return num(m.group(1)) if m else None
    actual=None
    m=re.search(r'Actual\s+([0-9][0-9,]*(?:\.\d+)?)',t,re.I)
    if m: actual=m.group(1)
    day=grab("Daily Change")
    month=grab("Monthly")
    yoy=grab("Yearly")
    week=embedded(h,["WeeklyPercentualChange","weeklyPercentualChange","weeklyChangePercent"])
    ytd=embedded(h,["YTDPercentualChange","ytdPercentualChange","YtdPercentualChange"])
    return actual,day,week,month,ytd,yoy

def main():
    old={}
    if OUT.exists():
        try:old={x["name"]:x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except:pass
    items=[]
    for name,url,unit,proxy in SOURCES:
        try:
            h=fetch(url)
            price,day,week,month,ytd,yoy=parse_page(h)
            prev=old.get(name,{})
            item={
              "name":name,"price":price or prev.get("price"),"unit":unit,
              "day":day if day is not None else prev.get("day"),
              "week":week if week is not None else prev.get("week"),
              "month":month if month is not None else prev.get("month"),
              "ytd":ytd if ytd is not None else prev.get("ytd"),
              "yoy":yoy if yoy is not None else prev.get("yoy"),
              "proxy":proxy,"source_url":url
            }
            items.append(item)
        except Exception:
            if name in old:items.append(old[name])
            else:items.append({"name":name,"unit":unit,"proxy":proxy,"source_url":url})
    OUT.write_text(json.dumps({"updated_at":datetime.now(TZ).isoformat(),"items":items},ensure_ascii=False,indent=2),encoding="utf-8")
    print("commodities:",len(items))
if __name__=="__main__":main()
