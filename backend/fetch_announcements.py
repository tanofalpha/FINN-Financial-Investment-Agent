"""Corporate announcements from BSE (primary: stable JSON) with NSE as secondary.

Both exchanges block naive clients: send browser-like headers, and for NSE prime cookies
by hitting the homepage first. Failures return [] and the pipeline falls back to the last
cached snapshot, so a flaky exchange never breaks the demo.
"""
import json
import time
from datetime import datetime, timedelta

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
BSE_ATT = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{}"
NSE_HOME = "https://www.nseindia.com"
NSE_URL = "https://www.nseindia.com/api/corporate-announcements"


def fetch_bse(scrip: str, symbol: str, days: int = 7):
    to = datetime.now()
    frm = to - timedelta(days=days)
    params = {
        "strCat": "-1", "strPrevDate": frm.strftime("%Y%m%d"), "strScrip": scrip,
        "strSearch": "P", "strToDate": to.strftime("%Y%m%d"), "strType": "C", "pageno": 1,
    }
    headers = {"User-Agent": UA, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"}
    try:
        r = requests.get(BSE_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, str):  # BSE sometimes double-encodes the JSON
            data = json.loads(data)
        rows = (data.get("Table", []) if isinstance(data, dict) else []) or []
    except Exception as e:
        print(f"[bse] {symbol}: {e} (falling back to NSE)")
        return []
    out = []
    for x in rows:
        if not isinstance(x, dict):
            continue
        att = x.get("ATTACHMENTNAME")
        out.append({
            "symbol": symbol,
            "ts": (x.get("NEWS_DT") or x.get("DissemDT") or "")[:19],
            "subject": (x.get("NEWSSUB") or x.get("HEADLINE") or "").strip(),
            "body": (x.get("HEADLINE") or "").strip(),
            "url": BSE_ATT.format(att) if att else None,
            "source": "BSE",
        })
    return out


def fetch_nse(symbol: str, days: int = 7):
    to = datetime.now()
    frm = to - timedelta(days=days)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json", "Referer": NSE_HOME})
    try:
        s.get(NSE_HOME, timeout=10)  # cookie priming
        time.sleep(0.5)
        r = s.get(NSE_URL, params={
            "index": "equities", "symbol": symbol,
            "from_date": frm.strftime("%d-%m-%Y"), "to_date": to.strftime("%d-%m-%Y"),
        }, timeout=15)
        r.raise_for_status()
        rows = r.json()
    except Exception as e:
        print(f"[nse] {symbol}: {e}")
        return []
    return [{
        "symbol": symbol,
        "ts": (x.get("an_dt") or x.get("sort_date") or "")[:19],
        "subject": (x.get("desc") or "").strip(),
        "body": (x.get("attchmntText") or "").strip(),
        "url": x.get("attchmntFile"),
        "source": "NSE",
    } for x in rows]


def fetch_announcements(portfolio, days: int = 7):
    items = []
    for p in portfolio:
        got = fetch_bse(p["bse"], p["symbol"], days) if p.get("bse") else []
        if not got:
            got = fetch_nse(p["symbol"], days)
        items.extend(got)
        time.sleep(0.3)  # be polite
    # de-dupe on (symbol, ts, subject)
    seen, uniq = set(), []
    for it in items:
        k = (it["symbol"], it["ts"], it["subject"])
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq