#!/usr/bin/env python3
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from html import unescape
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json, re, io

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "lunch.json"
TZ = ZoneInfo("Europe/Stockholm")
DAY = {"måndag":"monday","tisdag":"tuesday","onsdag":"wednesday","torsdag":"thursday","fredag":"friday"}
DAY_RE = r"(måndag|tisdag|onsdag|torsdag|fredag)"
# lördag/söndag ingår bara som gräns-markörer (se extract_days_from_text), inte som sparade dagar.
# "ö" läses ibland som "é" av tesseract i vissa typsnitt, båda varianterna accepteras.
ALL_DAY_RE = r"(måndag|tisdag|onsdag|torsdag|fredag|l[öeé]rdag|s[öeé]ndag)"

def _norm_day(name):
    n=name.lower()
    if n.startswith("l"): return "lördag"
    if n.startswith("s"): return "söndag"
    return n

def fetch_bytes(url):
    req = Request(url, headers={
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/127 Safari/537.36",
        "Accept-Language":"sv-SE,sv;q=0.9,en;q=0.7",
        "Accept":"text/html,application/xhtml+xml,image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Cache-Control":"no-cache",
    })
    with urlopen(req, timeout=45) as r:
        return r.read(), r.headers.get("Content-Type",""), r.geturl()

def fetch_text(url):
    raw, ctype, final = fetch_bytes(url)
    return raw.decode("utf-8","replace"), final

def visible(h):
    h = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>|</td>|</figcaption>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = unescape(h).replace("\xa0"," ")
    return "\n".join(re.sub(r"\s+"," ",x).strip() for x in h.splitlines() if re.sub(r"\s+"," ",x).strip())

def find_restaurant(d, name):
    return next((r for r in d.get("restaurants",[]) if r.get("name")==name), None)

def clean_lines(chunk):
    out=[]
    for x in chunk.splitlines():
        x=re.sub(r"\s+"," ",x).strip(" -•|:")
        if not x or len(x)>260: continue
        if re.search(r"(?i)cookie|instagram|facebook|kontakt|öppettid|boka bord|integritet|wordpress",x): continue
        out.append(x)
    return out

def extract_days_from_text(text):
    # Kräver att dagnamnet står i radens början (tillåter ledande whitespace).
    # Detta hindrar att ord som "tisdag" mitt i ett citat, eller en felläst
    # rubrikrad, tolkas som en egen dagrubrik och skriver över rätt data.
    # lördag/söndag räknas som gräns (så fredag inte svämmar över i helgen)
    # men sparas inte som egna dagar. OCR läser ofta "ö" som "é" i vissa
    # typsnitt, så båda varianterna accepteras för lördag/söndag.
    pat = re.compile(r"(?im)^\s*"+ALL_DAY_RE+r"\b(?:\s+\d{1,2}\s*[/\.\-]\s*\d{1,2})?\s*:?")
    hits=list(pat.finditer(text))
    out={}
    for i,m in enumerate(hits):
        name=_norm_day(m.group(1))
        stop=hits[i+1].start() if i+1<len(hits) else min(len(text),m.end()+1300)
        if name not in DAY: continue
        key=DAY[name]
        ds=clean_lines(text[m.end():stop])
        ds=[x for x in ds if not re.fullmatch(r"(?i)"+ALL_DAY_RE+r".*",x)]
        if ds and key not in out:   # första träffen vinner, ingen tyst överskrivning
            out[key]=ds[:8]
    return out

def image_candidates(html, base_url, week):
    candidates=[]
    attrs=re.findall(r"(?is)(?:src|data-src|data-lazy-src|href)\s*=\s*[\"']([^\"']+)[\"']", html)
    for u in attrs:
        u=unescape(u)
        if not re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)",u,re.I): continue
        full=urljoin(base_url,u)
        score=0
        low=full.lower()
        if "lunch" in low or "meny" in low: score+=4
        if f"v-{week}" in low or f"v{week}" in low or f"vecka-{week}" in low: score+=5
        if "uploads" in low: score+=1
        candidates.append((score,full))
    for m in re.finditer(r"(?is)<img[^>]+>",html):
        tag=m.group(0)
        meta=" ".join(re.findall(r"(?is)(?:alt|title)=[\"']([^\"']*)[\"']",tag))
        srcm=re.search(r"(?is)(?:src|data-src|data-lazy-src)=[\"']([^\"']+)[\"']",tag)
        if not srcm: continue
        full=urljoin(base_url,unescape(srcm.group(1)))
        score=2 if re.search(r"(?i)lunch|meny|vecka|v\.\s*"+str(week),meta) else 0
        if re.search(rf"(?i)(?:vecka|v\.?)\s*{week}\b",meta): score+=6
        candidates.append((score,full))
    seen=set(); result=[]
    for score,u in sorted(candidates,reverse=True):
        if u not in seen:
            seen.add(u); result.append((score,u))
    return result[:12]

def ocr_image(url):
    from PIL import Image
    import pytesseract
    raw, ctype, final=fetch_bytes(url)
    im=Image.open(io.BytesIO(raw))
    if im.width < 1400:
        scale=min(2.5,1400/max(1,im.width))
        im=im.resize((int(im.width*scale),int(im.height*scale)))
    return pytesseract.image_to_string(im,lang="swe+eng")

def pdf_to_text(raw_bytes):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # äldre PyMuPDF-versioner
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def pdf_to_ocr_text(raw_bytes):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    from PIL import Image
    import pytesseract
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    out=[]
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5))
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        out.append(pytesseract.image_to_string(im, lang="swe+eng"))
    return "\n".join(out)

def text_or_ocr_menu(url, week):
    """Delad logik: försök läsa dagar direkt ur sidans text, annars
    leta upp en menybild och kör OCR på den. Används av restauranger
    som publicerar veckomenyn som en bild snarare än text."""
    html, final = fetch_text(url)
    text = visible(html)
    if not re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b", text):
        raise ValueError(f"current week {week} not found")
    parsed = extract_days_from_text(text)
    method = "html"
    if len(parsed) < 3:
        for score, img in image_candidates(html, final, week):
            try:
                ocr = ocr_image(img)
                candidate = extract_days_from_text(ocr)
                week_ok = bool(re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b", ocr))
                if len(candidate) >= 4 or (week_ok and len(candidate) >= 2):
                    parsed = candidate
                    method = f"ocr:{img}"
                    break
            except Exception:
                continue
    if not parsed:
        raise ValueError("menu found for current week but no weekdays could be parsed from HTML or menu images")
    return parsed, method

def glasets(d, week):
    url="https://glasetshuslimmared.se/lunch/"
    parsed, method = text_or_ocr_menu(url, week)
    r=find_restaurant(d,"Glasets Hus")
    if not r: raise ValueError("restaurant missing")
    for key,ds in parsed.items():
        r.setdefault("menu",{})[key]={"verified":True,"dishes":ds,"source_url":url}
    r["source_url"]=url
    return len(parsed),method

def kabyssen(d, week):
    # Menyn ligger som PDF (inbäddad via Google Docs-viewer), inte som text eller
    # bild på själva sidan. Vi hittar PDF-URL:en dynamiskt i sidans HTML (istället
    # för att hårdkoda filnamnet, ifall restaurangen döper om filen framöver),
    # laddar ner PDF:en direkt och läser av text/OCR från den.
    page_url = "https://kabyssen-dalstorp.se/rezepte"
    html, _ = fetch_text(page_url)
    pdf_urls = []
    for m in re.finditer(r'docs\.google\.com/viewer\?url=([^&"\'<>]+)', html, re.I):
        from urllib.parse import unquote
        pdf_urls.append(unquote(m.group(1)))
    if not pdf_urls:
        # fallback: leta efter en direkt .pdf-lank pa sidan om Google Docs-viewern skulle bytas ut
        pdf_urls = [urljoin(page_url, u) for u in re.findall(r'(?is)(?:src|href)=["\']([^"\']+\.pdf)["\']', html)]
    if not pdf_urls:
        raise ValueError("no menu PDF found on page")
    # Prioritera en fil som inte ser ut som pizzamenyn, annars ta forsta traffen
    pdf_url = next((u for u in pdf_urls if "pizza" not in u.lower()), pdf_urls[0])

    raw, ctype, _ = fetch_bytes(pdf_url)
    text = pdf_to_text(raw)
    method = "pdf-text"
    if not re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b", text) or len(extract_days_from_text(text)) < 3:
        ocr_text = pdf_to_ocr_text(raw)
        if re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b", ocr_text):
            text = ocr_text
            method = "pdf-ocr"

    if not re.search(rf"(?i)\b(?:vecka|v\.?)\s*{week}\b", text):
        raise ValueError(f"current week {week} not found in menu PDF")
    parsed = extract_days_from_text(text)
    if not parsed:
        raise ValueError("menu PDF found for current week but no weekdays could be parsed")
    r=find_restaurant(d,"Kabyssen")
    if not r: raise ValueError("restaurant missing")
    for key,ds in parsed.items():
        r.setdefault("menu",{})[key]={"verified":True,"dishes":ds,"source_url":page_url}
    r["source_url"]=page_url
    return len(parsed), method

def sangbergs(d,week):
    url="https://www.sangbergs.se/lunchmeny"
    html,_=fetch_text(url); t=visible(html)
    now=datetime.now(TZ); monday=now.date()-timedelta(days=now.weekday())
    r=find_restaurant(d,"Centralen / Sångbergs")
    if not r: raise ValueError("restaurant missing")
    parsed=0
    for i,(sv,key) in enumerate(DAY.items()):
        date=monday+timedelta(days=i)
        pat=rf"(?i)\b{sv}\b\s*{date.day}\s*[/\.\-]\s*{date.month}\b"
        m=re.search(pat,t)
        if not m: continue
        tail=t[m.end():m.end()+1100]
        nxt=re.search(r"(?i)\b"+DAY_RE+r"\b\s*\d{1,2}\s*[/\.\-]\s*\d{1,2}",tail)
        if nxt: tail=tail[:nxt.start()]
        ds=clean_lines(tail)
        ds=[x for x in ds if not re.search(r"(?i)^veckans |lunchmeny|boka bord|lunch kostar",x)]
        if ds:
            r.setdefault("menu",{})[key]={"verified":True,"dishes":ds[:5],"source_url":url}
            parsed+=1
    if not parsed: raise ValueError("no current-week menu parsed")
    r["source_url"]=url
    return parsed

def limmared(d,week):
    url="https://limmaredsvardshus.se/"
    html,_=fetch_text(url); t=visible(html)
    hits=list(re.finditer(r"(?i)\bvecka\s*(\d{1,2})\b",t))
    week_hits=[m for m in hits if m.group(1)==str(week)]
    if not week_hits:
        raise ValueError(f"vecka {week} not found")
    start=week_hits[0].end()
    later=[m for m in hits if m.start()>start]
    stop=later[0].start() if later else min(len(t),start+3500)
    chunk=t[start:stop]
    parsed=extract_days_from_text(chunk)
    if not parsed: raise ValueError("no weekdays parsed for current week")
    standing=[]
    for m in re.finditer(r"(?i)veckans\s+(vego|pasta|sallad)\s*:?\s*([^\n]{1,120})",chunk):
        line=f"Veckans {m.group(1).capitalize()}: {m.group(2).strip()}"
        if line not in standing: standing.append(line)
    r=find_restaurant(d,"Limmareds Wärdshus")
    if not r: raise ValueError("restaurant missing")
    for key,ds in parsed.items():
        dishes=list(ds[:6])
        for s in standing:
            if s not in dishes: dishes.append(s)
        r.setdefault("menu",{})[key]={"verified":True,"dishes":dishes[:8],"source_url":url}
    r["source_url"]=url
    return len(parsed)

def main():
    d=json.loads(DATA.read_text(encoding="utf-8"))
    now=datetime.now(TZ); week=now.isocalendar().week; log=[]
    try:
        n,method=glasets(d,week)
        log.append(f"glasets: ok ({n} days, {method})")
    except Exception as e:
        log.append(f"glasets: {e}")
    try:
        n,method=kabyssen(d,week)
        log.append(f"kabyssen: ok ({n} days, {method})")
    except Exception as e:
        log.append(f"kabyssen: {e}")
    try:
        n=sangbergs(d,week)
        log.append(f"sangbergs: ok ({n} days)")
    except Exception as e:
        log.append(f"sangbergs: {e}")
    try:
        n=limmared(d,week)
        log.append(f"limmared: ok ({n} days)")
    except Exception as e:
        log.append(f"limmared: {e}")
    d["updated_at"]=now.strftime("%Y-%m-%d %H:%M")
    d["iso_week"]=week
    d["update_log"]=log
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
    print("\n".join(log))

if __name__=="__main__":
    main()
