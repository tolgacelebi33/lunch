#!/usr/bin/env python3
from urllib.request import Request, urlopen
from html import unescape
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data/commodities.json"
HIST=ROOT/"data/commodities_history.json"
TZ=ZoneInfo("Europe/Stockholm")

# (namn, url, källvaluta, enhet, proxy-beskrivning)
SOURCES=[
 ("Stål","https://tradingeconomics.com/commodity/steel","CNY","t","Steel rebar"),
 ("Plåt / HRC","https://tradingeconomics.com/commodity/hrc-steel","USD","t","HRC Steel"),
 ("Trä","https://tradingeconomics.com/commodity/lumber","USD","1000 bf","Lumber"),
]

# Skivmaterial och Porslin har inga handlade råvarupriser. Istället används Eurostats
# producentprisindex för respektive varugrupp (poäng, bas beror på referensår), skrapat
# från samma sajt som ovan. EU-27-aggregatet för träbaserade skivor visade sig vara
# fruset sedan nov 2023 i Eurostats data, så Eurozon-raden används där istället eftersom
# den faktiskt uppdateras månadsvis.
PORSLIN_URL="https://tradingeconomics.com/european-union/producer-prices-in-industry-manufacture-of-other-porcelain-ceramic-products-eurostat-data.html"
SKIVA_URL="https://tradingeconomics.com/european-union/producer-prices-in-industry-manufacture-of-veneer-sheets-wood-based-panels-eurostat-data.html"

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
    return num(actual),day,week,month,ytd,yoy

_FX_CACHE={}
def fx_to_sek(currency):
    """Live SEK-kurs via Frankfurter (ECB-data, gratis, ingen nyckel). Faller tillbaka
    på ett hårdkodat nödvärde om anropet misslyckas, så pipen aldrig kraschar helt."""
    if currency=="SEK": return 1.0
    if currency in _FX_CACHE: return _FX_CACHE[currency]
    fallback={"USD":10.6,"CNY":1.48}
    try:
        url=f"https://api.frankfurter.dev/v1/latest?base={currency}&symbols=SEK"
        raw=fetch(url)
        data=json.loads(raw)
        rate=data["rates"]["SEK"]
        _FX_CACHE[currency]=rate
        return rate
    except Exception:
        return fallback.get(currency,1.0)

def month_num(s):
    for fmt in ("%B","%b"):
        try:return datetime.strptime(s,fmt).month
        except ValueError:pass
    return None

def parse_eu_index_page(h):
    """EU-aggregatets egna 'Actual'-mening, t.ex. '...was 125.90 points in June of 2026'."""
    t=textify(h)
    m=re.search(r'was\s+(-?\d+(?:\.\d+)?)\s+points\s+in\s+([A-Za-z]+)\s+of\s+(\d{4})',t)
    if not m:return None,None,None
    return num(m.group(1)),int(m.group(3)),month_num(m.group(2))

def parse_euroarea_row(h):
    """Eurozon-raden i jämförelsetabellen: 'Euro Area 119.00 118.20 points Jun 2026' (Last, Previous)."""
    t=textify(h)
    m=re.search(r'Euro Area\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+points\s+([A-Za-z]+)\s+(\d{4})',t)
    if not m:return None,None,None,None
    return num(m.group(1)),num(m.group(2)),int(m.group(4)),month_num(m.group(3))

def load_history():
    if HIST.exists():
        try:return json.loads(HIST.read_text(encoding="utf-8"))
        except:return {}
    return {}

def index_change(hist,key,year,month,value):
    """Sparar ny (år,månad,värde)-punkt om det är en ny period; returnerar (månadsförändring,årsförändring)."""
    series=hist.setdefault(key,[])
    if not series or (series[-1]["y"],series[-1]["m"])!=(year,month):
        series.append({"y":year,"m":month,"v":value})
        del series[:-15]
    month_change=None
    if len(series)>=2 and series[-2]["v"]:
        month_change=round((series[-1]["v"]-series[-2]["v"])/series[-2]["v"]*100,2)
    yoy_change=None
    for e in series:
        if (e["y"],e["m"])==(year-1,month) and e["v"]:
            yoy_change=round((value-e["v"])/e["v"]*100,2)
            break
    return month_change,yoy_change

def build_index_item(name,url,label,val,month_change,yoy_change,old):
    prev=old.get(name,{})
    if prev.get("kind")!="index":prev={}  # ignore stale data from the old (unrelated) proxy series
    return {
      "name":name,"kind":"index",
      "price":val if val is not None else prev.get("price"),
      "unit":"poäng",
      "month":month_change if month_change is not None else prev.get("month"),
      "yoy":yoy_change if yoy_change is not None else prev.get("yoy"),
      "proxy":label,"source_url":url
    }

def main():
    old={}
    if OUT.exists():
        try:old={x["name"]:x for x in json.loads(OUT.read_text(encoding="utf-8")).get("items",[])}
        except:pass
    items=[]
    for name,url,ccy,unit_suffix,proxy in SOURCES:
        try:
            h=fetch(url)
            price,day,week,month,ytd,yoy=parse_page(h)
            rate=fx_to_sek(ccy)
            price_sek=round(price*rate,0) if price is not None else None
            prev=old.get(name,{})
            item={
              "name":name,
              "price":price_sek if price_sek is not None else prev.get("price"),
              "unit":f"kr/{unit_suffix}",
              "fx_rate":rate,"fx_from":ccy,
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
            else:items.append({"name":name,"unit":f"kr/{unit_suffix}","proxy":proxy,"source_url":url})

    hist=load_history()

    try:
        h=fetch(SKIVA_URL)
        last,prevv,yr,mon=parse_euroarea_row(h)
        month_change=round((last-prevv)/prevv*100,2) if last is not None and prevv else None
        yoy_change=None
        if last is not None:
            _,yoy_change=index_change(hist,"Skivmaterial",yr,mon,last)
        items.append(build_index_item("Skivmaterial",SKIVA_URL,"Eurostat PPI, Eurozonen",last,month_change,yoy_change,old))
    except Exception:
        items.append(old.get("Skivmaterial") or {"name":"Skivmaterial","kind":"index","unit":"poäng","proxy":"Eurostat PPI, Eurozonen","source_url":SKIVA_URL})

    try:
        h=fetch(PORSLIN_URL)
        val,yr,mon=parse_eu_index_page(h)
        month_change,yoy_change=(None,None)
        if val is not None:
            month_change,yoy_change=index_change(hist,"Porslin",yr,mon,val)
        items.append(build_index_item("Porslin",PORSLIN_URL,"Eurostat PPI, EU",val,month_change,yoy_change,old))
    except Exception:
        items.append(old.get("Porslin") or {"name":"Porslin","kind":"index","unit":"poäng","proxy":"Eurostat PPI, EU","source_url":PORSLIN_URL})

    HIST.write_text(json.dumps(hist,ensure_ascii=False,indent=2),encoding="utf-8")
    OUT.write_text(json.dumps({"updated_at":datetime.now(TZ).isoformat(),"items":items},ensure_ascii=False,indent=2),encoding="utf-8")
    print("commodities:",len(items))
if __name__=="__main__":main()
