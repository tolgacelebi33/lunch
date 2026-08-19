#!/usr/bin/env python3
from urllib.request import Request,urlopen
from html import unescape
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import json,re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/lunch.json"
TZ=ZoneInfo("Europe/Stockholm")
DAY={"måndag":"monday","tisdag":"tuesday","onsdag":"wednesday","torsdag":"thursday","fredag":"friday"}
DAY_RE=r"(måndag|tisdag|onsdag|torsdag|fredag)"

def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36","Accept-Language":"sv-SE,sv;q=0.9"})
    with urlopen(req,timeout=45) as r:return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")

def visible(h):
    h=re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->"," ",h)
    h=re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>|</td>","\n",h)
    h=re.sub(r"(?s)<[^>]+>"," ",h)
    h=unescape(h).replace("\xa0"," ")
    return re.sub(r"[ \t]+"," ",h)

def find_restaurant(d,name):
    return next((r for r in d.get("restaurants",[]) if r.get("name")==name),None)

def dishes_between(text, start, stop):
    chunk=text[start:stop]
    lines=[]
    for x in chunk.splitlines():
        x=re.sub(r"\s+"," ",x).strip(" -•|")
        if not x or len(x)>260: continue
        if re.search(r"(?i)cookie|instagram|facebook|kontakt|öppettid|boka bord|integritet",x): continue
        if re.fullmatch(r"(?i)"+DAY_RE+r".*",x): continue
        lines.append(x)
    return lines[:8]

def glasets(d,week):
    url="https://glasetshuslimmared.se/lunch/"
    t=visible(fetch(url))
    if not re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b",t): raise ValueError(f"current week {week} not found")
    # Weekday may be in a heading, paragraph, table cell or same line as first dish.
    hits=list(re.finditer(r"(?i)\b"+DAY_RE+r"\b(?:\s+\d{1,2}[./-]\d{1,2})?\s*:?",t))
    # de-duplicate nearby repeated navigation/menu occurrences; retain candidates followed by useful text
    candidates=[]
    for m in hits:
        nxt=t[m.end():m.end()+500]
        if len(re.sub(r"\s+"," ",nxt).strip())>15:
            if not candidates or m.start()-candidates[-1].start()>20:candidates.append(m)
    if not candidates: raise ValueError("weekday tokens not found")
    r=find_restaurant(d,"Glasets Hus")
    if not r: raise ValueError("restaurant missing")
    parsed=0
    for i,m in enumerate(candidates):
        key=DAY[m.group(1).lower()]
        stop=candidates[i+1].start() if i+1<len(candidates) else min(len(t),m.end()+1400)
        ds=dishes_between(t,m.end(),stop)
        if ds:
            r.setdefault("menu",{})[key]={"verified":True,"dishes":ds,"source_url":url}
            parsed+=1
    if not parsed: raise ValueError("weekday tokens found but dishes not parsed")
    r["source_url"]=url
    return parsed

def sangbergs(d,week):
    url="https://www.sangbergs.se/lunchmeny"
    t=visible(fetch(url)); now=datetime.now(TZ); monday=now.date()-timedelta(days=now.weekday())
    valid={(monday+timedelta(days=i)).strftime("%-d/%-m"):list(DAY.values())[i] for i in range(5)}
    r=find_restaurant(d,"Centralen / Sångbergs")
    if not r: raise ValueError("restaurant missing")
    parsed=0
    for sv,key in DAY.items():
        # Accept weekday + current week's date with /, . or -
        date=(monday+timedelta(days=list(DAY.keys()).index(sv)))
        pat=rf"(?i)\b{sv}\b\s*{date.day}\s*[/.\-]\s*{date.month}\b"
        m=re.search(pat,t)
        if not m: continue
        following=[x for x in re.split(r"[\r\n]+",t[m.end():m.end()+1000]) if x.strip()]
        ds=[]
        for x in following:
            x=re.sub(r"\s+"," ",x).strip(" -•|")
            if re.search(r"(?i)\b"+DAY_RE+r"\b",x): break
            if x and len(x)<240 and not re.search(r"(?i)veckans|lunch kostar|öppettid|kontakt",x): ds.append(x)
        if ds:
            r.setdefault("menu",{})[key]={"verified":True,"dishes":ds[:5],"source_url":url};parsed+=1
    if not parsed: raise ValueError("no current-week menu parsed")
    r["source_url"]=url
    return parsed

def main():
    d=json.loads(DATA.read_text(encoding="utf-8")); now=datetime.now(TZ); week=now.isocalendar().week; log=[]
    for name,fn in [("glasets",glasets),("sangbergs",sangbergs)]:
        try: log.append(f"{name}: ok ({fn(d,week)} days)")
        except Exception as e: log.append(f"{name}: {e}")
    d["updated_at"]=now.strftime("%Y-%m-%d %H:%M"); d["iso_week"]=week; d["update_log"]=log
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n".join(log))
if __name__=="__main__":main()
