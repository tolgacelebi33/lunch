#!/usr/bin/env python3
from urllib.request import Request,urlopen
from html import unescape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/lunch.json"
TZ=ZoneInfo("Europe/Stockholm")
DAYMAP={"måndag":"monday","tisdag":"tuesday","onsdag":"wednesday","torsdag":"thursday","fredag":"friday"}

def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 Chrome/127 Safari/537.36","Accept-Language":"sv-SE,sv;q=0.9"})
    with urlopen(req,timeout=40) as r:return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")

def textify(h):
    h=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",h)
    h=re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>","\n",h)
    h=re.sub(r"(?s)<[^>]+>"," ",h)
    return "\n".join(re.sub(r"\s+"," ",unescape(x).replace("\xa0"," ")).strip() for x in h.splitlines() if re.sub(r"\s+"," ",unescape(x)).strip())

def restaurant(data,name):
    for r in data["restaurants"]:
        if r["name"]==name:return r
    return None

def setday(r,key,dishes,url):
    if dishes:r.setdefault("menu",{})[key]={"verified":True,"dishes":dishes,"source_url":url}

def glasets(data,week):
    url="https://glasetshuslimmared.se/lunch/"
    t=textify(fetch(url))
    if not re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b",t):raise ValueError("wrong week")
    r=restaurant(data,"Glasets Hus")
    if not r:raise ValueError("restaurant missing")
    hits=list(re.finditer(r"(?im)^\s*(måndag|tisdag|onsdag|torsdag|fredag)(?:\s+\d{1,2}/\d{1,2})?\s*:?\s*$",t))
    if not hits:raise ValueError("no weekday headings")
    for i,m in enumerate(hits):
        stop=hits[i+1].start() if i+1<len(hits) else min(len(t),m.end()+1200)
        lines=[x.strip(" -•") for x in t[m.end():stop].splitlines() if x.strip()]
        lines=[x for x in lines if len(x)<220 and not re.search(r"(?i)cookie|instagram|facebook|öppettider|kontakt",x)]
        setday(r,DAYMAP[m.group(1).lower()],lines[:6],url)
    r["source_url"]=url

def sangbergs(data,week):
    url="https://www.sangbergs.se/lunchmeny"
    t=textify(fetch(url))
    # Require current week marker OR dates belonging to current Mon-Fri.
    now=datetime.now(TZ); mon=now.date()
    mon=mon.fromordinal(mon.toordinal()-mon.weekday())
    dates={(mon.fromordinal(mon.toordinal()+i).day,mon.fromordinal(mon.toordinal()+i).month):list(DAYMAP.values())[i] for i in range(5)}
    r=restaurant(data,"Centralen / Sångbergs")
    if not r:raise ValueError("restaurant missing")
    hits=list(re.finditer(r"(?im)^\s*(måndag|tisdag|onsdag|torsdag|fredag)\s+(\d{1,2})/(\d{1,2})\s*$",t))
    accepted=0
    for i,m in enumerate(hits):
        dm=(int(m.group(2)),int(m.group(3)))
        if dm not in dates:continue
        stop=hits[i+1].start() if i+1<len(hits) else min(len(t),m.end()+800)
        lines=[x.strip(" -•") for x in t[m.end():stop].splitlines() if x.strip()]
        lines=[x for x in lines if len(x)<220 and not re.search(r"(?i)^veckans |lunch kostar|måndag till fredag",x)]
        setday(r,dates[dm],lines[:4],url);accepted+=1
    if not accepted:raise ValueError("no current-week dated menu found")
    r["source_url"]=url

def main():
    d=json.loads(DATA.read_text(encoding="utf-8"));now=datetime.now(TZ);log=[]
    for fn in (glasets,sangbergs):
        try:fn(d,now.isocalendar().week);log.append(fn.__name__+": ok")
        except Exception as e:log.append(fn.__name__+": "+str(e))
    d["updated_at"]=now.strftime("%Y-%m-%d %H:%M");d["iso_week"]=now.isocalendar().week;d["update_log"]=log
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n".join(log))
if __name__=="__main__":main()
