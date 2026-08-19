#!/usr/bin/env python3
from urllib.request import Request,urlopen
from html import unescape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/linkedin.json"
TZ=ZoneInfo("Europe/Stockholm")
URL="https://se.linkedin.com/company/svedbergs"

def fetch():
    req=Request(URL,headers={"User-Agent":"Mozilla/5.0 Chrome/127 Safari/537.36","Accept-Language":"sv-SE,sv;q=0.9"})
    with urlopen(req,timeout=15) as r:return r.read().decode(r.headers.get_content_charset() or "utf-8","replace")

def textify(h):
    h=re.sub(r"(?is)<script.*?</script>|<style.*?</style>"," ",h)
    h=re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</article>","\n",h)
    h=re.sub(r"(?s)<[^>]+>"," ",h)
    h=unescape(h).replace("\xa0"," ")
    return "\n".join(re.sub(r"\s+"," ",x).strip() for x in h.splitlines() if re.sub(r"\s+"," ",x).strip())

def main():
    old={}
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding="utf-8"))
        except:pass
    try:
        t=textify(fetch())
        pos=t.lower().find("uppdateringar")
        if pos<0:raise ValueError("updates section not found")
        chunk=t[pos:pos+7000]
        # First relative timestamp after Updates, e.g. 2 v, 1 mån, 3 d.
        m=re.search(r"\b(\d+\s*(?:v|mån|d|h))\b",chunk,re.I)
        if not m:raise ValueError("timestamp not found")
        after=chunk[m.end():]
        lines=[x.strip() for x in after.splitlines() if x.strip()]
        lines=[x for x in lines if not re.fullmatch(r"[\d\s,.]+följare",x,re.I)]
        body=" ".join(lines[:8])
        # Stop before next update marker if visible.
        body=re.split(r"\b\d+\s*(?:v|mån|d|h)\b",body,maxsplit=1)[0].strip()
        if len(body)<80:raise ValueError("post body too short")
        title="Senaste från Svedbergs"
        summary=body[:700].strip()
        data={"updated_at":datetime.now(TZ).isoformat(),"title":title,"summary":summary,"relative_date":m.group(1),"url":URL}
        OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        print("linkedin: ok")
    except Exception as e:
        print("linkedin: fallback -",e)
        if not old:raise
if __name__=="__main__":main()
