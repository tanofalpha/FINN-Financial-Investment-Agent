
# """Pull engine: `python research.py TICKER` -> frontend/public/data/research/TICKER.json
 
# Works for any NSE ticker present on screener.in. Primary sources only:
#   screener.in page -> latest annual report + last 4 concall transcripts (PDF links)
#                    -> standardised quarterly table (company-reported numbers)
# Pipeline (cost-aware):
#   1. download + text-extract PDFs, cache by URL hash            (free)
#   2. cheap model, per transcript: extract explicit guidance     (bulk, small model)
#   3. strong model, once: compare guidance vs reported quarters + business/bull/bear  (reasoning)
# Every LLM call is cached by prompt hash, so re-runs cost nothing.
# Env: ANTHROPIC_API_KEY, optional FINN_CHEAP_MODEL / FINN_STRONG_MODEL.
# NOTE: written against screener.in's current markup but not exercised in the build sandbox (no network).
# """
# import hashlib
# import io
# import json
# import os
# import re
# import sys
# import time
# import requests
 
# HERE = os.path.dirname(__file__)
# CACHE = os.path.join(HERE, "cache")
# OUT = os.path.join(HERE, "..", "frontend", "public", "data", "research")
# UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
# CHEAP = os.environ.get("FINN_CHEAP_MODEL", "claude-haiku-5-5")
# STRONG = os.environ.get("FINN_STRONG_MODEL", "claude-sonnet-5-5")
# os.makedirs(CACHE, exist_ok=True)
 
 
# def _h(s):
#     return hashlib.sha1(s.encode()).hexdigest()
 
 
# _GM = {}
 
 
# def gemini_model():
#     """Use FINN_GEMINI_MODEL if set, else ask Google which flash models this key can call."""
#     if os.environ.get("FINN_GEMINI_MODEL"):
#         return os.environ["FINN_GEMINI_MODEL"]
#     if "m" not in _GM:
#         r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
#                          headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=30)
#         r.raise_for_status()
#         names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
#                  if "generateContent" in m.get("supportedGenerationMethods", [])]
#         flash = sorted(n for n in names if "flash" in n and "lite" not in n and "image" not in n and "omni" not in n
#                        and "tts" not in n and "live" not in n and "preview" not in n and "exp" not in n)
#         # the -latest alias always points at a current, general-purpose flash model
#         _GM["m"] = "gemini-flash-latest" if "gemini-flash-latest" in names else (flash[-1] if flash else names[0])
#         print(f"[gemini] using model: {_GM['m']}")
#     return _GM["m"]
 
 
# def llm(model, system, user, max_tokens=1500):
#     key = os.path.join(CACHE, f"llm_{_h(model + system + user)}.json")
#     if os.path.exists(key):
#         return json.load(open(key))["t"]
#     if os.environ.get("GEMINI_API_KEY"):
#         gm = gemini_model()

#         for attempt in range(1, 5):
#             try:
#                 print(f"[gemini] Model: {gm}, attempt {attempt}/4")

#                 r = requests.post(
#                     f"https://generativelanguage.googleapis.com/v1beta/models/{gm}:generateContent",
#                     headers={
#                         "x-goog-api-key": os.environ["GEMINI_API_KEY"],
#                         "content-type": "application/json"
#                     },
#                     json={
#                         "systemInstruction": {
#                             "parts": [{"text": system}]
#                         },
#                         "contents": [{
#                             "role": "user",
#                             "parts": [{"text": user}]
#                         }],
#                         "generationConfig": {
#                             "maxOutputTokens": max_tokens,
#                             "temperature": 0.1
#                         }
#                     },
#                     timeout=(10, 180)
#                 )

#                 if r.status_code in (429, 500, 502, 503, 504):
#                     if attempt == 4:
#                         r.raise_for_status()

#                     delay = 5 * (2 ** (attempt - 1))
#                     print(f"[gemini] HTTP {r.status_code}. Retrying in {delay}s")
#                     time.sleep(delay)
#                     continue

#                 r.raise_for_status()
#                 break

#             except (requests.exceptions.Timeout,
#                     requests.exceptions.ConnectionError) as e:

#                 if attempt == 4:
#                     raise

#                 delay = 5 * (2 ** (attempt - 1))
#                 print(f"[gemini] Network error: {e}")
#                 print(f"[gemini] Retrying in {delay}s")
#                 time.sleep(delay)

#         parts = r.json()["candidates"][0]["content"]["parts"]
#         t = "\n".join(
#             part["text"] for part in parts if "text" in part
#         ).strip()

#         if not t:
#             raise ValueError("Gemini returned no text")

#     else:
#         r = requests.post(
#             "https://api.anthropic.com/v1/messages",
#             headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
#             json={"model": model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]},
#             timeout=120,
#         )
#         r.raise_for_status()
#         t = r.json()["content"][0]["text"]
#     json.dump({"t": t}, open(key, "w"))
#     return t
 
 
# def jparse(t):
#     m = re.search(r"[\[{].*[\]}]", t, re.S)
#     return json.loads(m.group(0)) if m else None
 
 
# def screener(sym):
#     for v in ("consolidated/", ""):
#         r = requests.get(f"https://www.screener.in/company/{sym}/{v}", headers=UA, timeout=30)
#         if r.ok:
#             return r.text
#     raise SystemExit(f"{sym}: not found on screener.in")
 
 
# def links(html):
#     anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
#     clean = lambda s: re.sub(r"<[^>]+>|\s+", " ", s).strip()
#     calls = [(clean(t), u) for u, t in anchors if "transcript" in clean(t).lower()]
#     ars = [(clean(t), u) for u, t in anchors if re.search(r"financial year \d{4}", clean(t), re.I)]
#     return calls[:4], ars[:1]
 
 
# def quarterly(html):
#     """Rows from screener's quarterly table: Sales, Operating Profit, Profit before tax, Net Profit."""
#     sec = re.search(r'id="quarters".*?</table>', html, re.S)
#     if not sec:
#         return {}
#     rows = {}
#     for tr in re.findall(r"<tr.*?</tr>", sec.group(0), re.S):
#         cells = [re.sub(r"<[^>]+>|&nbsp;|\+|%|,", "", c).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
#         if len(cells) > 2:
#             rows[re.sub(r"\s+", " ", cells[0])] = cells[1:]
#     return rows
 
 
# def pdf_text(url):
#     path = os.path.join(CACHE, f"pdf_{_h(url)}.txt")
#     if os.path.exists(path):
#         return open(path).read()
#     from pypdf import PdfReader
#     b = requests.get(url, headers=UA, timeout=60).content
#     pages = [f"[p.{i + 1}] " + (p.extract_text() or "") for i, p in enumerate(PdfReader(io.BytesIO(b)).pages)]
#     t = "\n".join(pages)
#     open(path, "w").write(t)
#     return t
 
 
# def chunk(t, n=14000):
#     return [t[i:i + n] for i in range(0, len(t), n)]
 
 
# GUIDE_SYS = ("Extract ONLY explicit forward-looking guidance management gave on headline numbers "
#              "(revenue/growth, margins, EBITDA, capex, order book). Use only the text provided. "
#              "Return JSON list: [{metric, statement (verbatim, <25 words), page}]. Return [] if none.")
 
 
# def main(sym):
#     sym = sym.upper()
#     html = screener(sym)
#     calls, ars = links(html)
#     qtr = quarterly(html)
#     guidance = []
#     for title, url in calls:
#         txt = pdf_text(url if url.startswith("http") else "https://www.screener.in" + url)
#         # guidance lives in management's opening remarks: scan first chunks only (cost control)
#         for c in chunk(txt)[:2]:
#             g = jparse(llm(CHEAP, GUIDE_SYS, c)) or []
#             guidance += [{**x, "call": title} for x in g]
 
#     biz_ctx = ""
#     if ars:
#         u = ars[0][1]
#         biz_ctx = chunk(pdf_text(u if u.startswith("http") else "https://www.screener.in" + u))[0][:14000]
 
#     syn_sys = ("You are an equity analyst. Use ONLY the provided guidance quotes, reported quarterly numbers and annual-report "
#                "excerpt. No outside knowledge. Return JSON: {business:{summary,segments:[{name,pct}]}, "
#                "pvd:[{period,metric,promised,delivered,verdict(met|beat|missed|unclear),source}], bull:[..3], bear:[..3]}. "
#                "Cite the call and page in 'source'. If evidence is missing, verdict is 'unclear'.")
#     user = json.dumps({"guidance": guidance, "reported_quarters": qtr, "annual_report_excerpt": biz_ctx})
#     res = jparse(llm(STRONG, syn_sys, user, 3000)) or {}
#     res.update({"symbol": sym, "sample": False, "sources": [u for _, u in calls + ars]})
#     os.makedirs(OUT, exist_ok=True)
#     json.dump(res, open(os.path.join(OUT, f"{sym}.json"), "w"), indent=1)
#     print(f"wrote research/{sym}.json ({len(guidance)} guidance items)")
 
 
# if __name__ == "__main__":
#     main(sys.argv[1])



"""Pull engine: `python research.py TICKER` -> frontend/public/data/research/TICKER.json

Works for any NSE ticker present on screener.in. Primary sources only:
  screener.in page -> latest annual report + last 4 concall transcripts (PDF links)
                   -> standardised quarterly table (company-reported numbers)
Pipeline (cost-aware):
  1. download + text-extract PDFs, cache by URL hash            (free)
  2. cheap model, per transcript: extract explicit guidance     (bulk, small model)
  3. strong model, once: compare guidance vs reported quarters + business/bull/bear  (reasoning)
Every LLM call is cached by prompt hash, so re-runs cost nothing.
Env: ANTHROPIC_API_KEY, optional FINN_CHEAP_MODEL / FINN_STRONG_MODEL.
NOTE: written against screener.in's current markup but not exercised in the build sandbox (no network).
"""
import hashlib
import io
import json
import os
import re
import sys

import requests

HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, "cache")
OUT = os.path.join(HERE, "..", "frontend", "public", "data", "research")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}
CHEAP = os.environ.get("FINN_CHEAP_MODEL", "claude-haiku-5-5")
STRONG = os.environ.get("FINN_STRONG_MODEL", "claude-sonnet-5-5")
os.makedirs(CACHE, exist_ok=True)


def _h(s):
    return hashlib.sha1(s.encode()).hexdigest()


_GM = {}


def gemini_model():
    """Use FINN_GEMINI_MODEL if set, else ask Google which flash models this key can call."""
    if os.environ.get("FINN_GEMINI_MODEL"):
        return os.environ["FINN_GEMINI_MODEL"]
    if "m" not in _GM:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                         headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=30)
        r.raise_for_status()
        names = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
        flash = sorted(n for n in names if "flash" in n and "lite" not in n and "image" not in n and "omni" not in n
                       and "tts" not in n and "live" not in n and "preview" not in n and "exp" not in n)
        # the -latest alias always points at a current, general-purpose flash model
        _GM["m"] = "gemini-flash-latest" if "gemini-flash-latest" in names else (flash[-1] if flash else names[0])
        print(f"[gemini] using model: {_GM['m']}")
    return _GM["m"]


def llm(model, system, user, max_tokens=1500):
    key = os.path.join(CACHE, f"llm_{_h(model + system + user)}.json")
    if os.path.exists(key):
        return json.load(open(key))["t"]
    if os.environ.get("GEMINI_API_KEY"):  # free tier via Google AI Studio
        gm = gemini_model()
        for attempt in range(4):  # free tier rate-limits: back off and retry
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gm}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "content-type": "application/json"},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.1}},
                timeout=120,
            )
            if r.status_code in (429, 503):
                import time; time.sleep(8 * (attempt + 1)); continue
            break
        r.raise_for_status()
        t = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]},
            timeout=120,
        )
        r.raise_for_status()
        t = r.json()["content"][0]["text"]
    json.dump({"t": t}, open(key, "w"))
    return t


def jparse(t):
    m = re.search(r"[\[{].*[\]}]", t, re.S)
    return json.loads(m.group(0)) if m else None


def screener(sym):
    for v in ("consolidated/", ""):
        r = requests.get(f"https://www.screener.in/company/{sym}/{v}", headers=UA, timeout=30)
        if r.ok:
            return r.text
    raise SystemExit(f"{sym}: not found on screener.in")


def links(html):
    anchors = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    clean = lambda s: re.sub(r"<[^>]+>|\s+", " ", s).strip()
    def uniq(pairs):
        seen, out = set(), []
        for t, u in pairs:
            if u not in seen:
                seen.add(u)
                out.append((t, u))
        return out
    calls = uniq((clean(t), u) for u, t in anchors if "transcript" in clean(t).lower())
    ars = uniq((clean(t), u) for u, t in anchors
               if re.search(r"financial year \d{4}|annual report", clean(t), re.I) or re.search(r"annual[-_ ]?report", u, re.I))
    print(f"[links] {len(calls)} transcripts, {len(ars)} annual reports found")
    return calls[:4], ars[:1]


def quarterly(html):
    """Rows from screener's quarterly table: Sales, Operating Profit, Profit before tax, Net Profit."""
    sec = re.search(r'id="quarters".*?</table>', html, re.S)
    if not sec:
        return {}
    rows, N = {}, 8  # screener lists oldest -> newest; keep only the latest N quarters, with period labels
    for tr in re.findall(r"<tr.*?</tr>", sec.group(0), re.S):
        cells = [re.sub(r"<[^>]+>|&nbsp;|\+|%|,", "", c).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
        if len(cells) > 2:
            rows[re.sub(r"\s+", " ", cells[0]) or "Quarter"] = cells[1:][-N:]
    return rows


def pdf_text(url):
    path = os.path.join(CACHE, f"pdf_{_h(url)}.txt")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    from pypdf import PdfReader
    b = requests.get(url, headers=UA, timeout=60).content
    pages = [f"[p.{i + 1}] " + (p.extract_text() or "") for i, p in enumerate(PdfReader(io.BytesIO(b)).pages)]
    t = "\n".join(pages)
    open(path, "w", encoding="utf-8").write(t)
    return t


def chunk(t, n=14000):
    return [t[i:i + n] for i in range(0, len(t), n)]


GUIDE_SYS = ("Extract ONLY explicit forward-looking guidance management gave on headline numbers "
             "(revenue/growth, margins, EBITDA, capex, order book). Use only the text provided. "
             "Return JSON list: [{metric, statement (verbatim, <25 words), page}]. Return [] if none.")


def main(sym):
    sym = sym.upper()
    html = screener(sym)
    calls, ars = links(html)
    qtr = quarterly(html)
    guidance = []
    for title, url in calls:
        txt = pdf_text(url if url.startswith("http") else "https://www.screener.in" + url)
        # guidance appears in opening remarks and in Q&A: scan up to 4 chunks per call
        for c in chunk(txt)[:4]:
            try:
                g = jparse(llm(CHEAP, GUIDE_SYS, c)) or []
            except Exception as e:
                print(f"[guidance] skipped a chunk: {e}")
                g = []
            guidance += [{**x, "call": title} for x in g if isinstance(x, dict)]

    biz_ctx = ""
    if ars:
        u = ars[0][1]
        parts = chunk(pdf_text(u if u.startswith("http") else "https://www.screener.in" + u))
        # prefer chunks that describe segments / revenue mix; fall back to the opening chunks
        hits = [p for p in parts if re.search(r"segment|revenue by|business overview", p, re.I)]
        biz_ctx = "\n---\n".join((hits[:2] or parts[:2]))[:24000]
    else:
        print("[warn] no annual report found: business view will rely on transcripts only")
        biz_ctx = "(none)"

    syn_sys = ("You are an equity analyst. Use ONLY the provided guidance quotes, reported quarterly numbers and annual-report "
               "excerpt. No outside knowledge. Return JSON: {business:{summary,segments:[{name,pct}]}, "
               "pvd:[{period,metric,promised,delivered,verdict(met|beat|missed|unclear),source}], bull:[..3], bear:[..3]}. "
               "Cite the call and page in 'source'. If evidence is missing, verdict is 'unclear'. "
               "reported_quarters lists the LATEST quarters, oldest to newest, with period labels in the first row: compare each "
               "guidance item only against periods it actually covers, and quote the actual figure in 'delivered'. "
               "A guidance item about a period that has not been reported yet gets verdict 'unclear' and delivered 'Not yet reported'. "
               "bull/bear must come only from the guidance, recent quarters and annual report, never from old periods. "
               "Use null for a segment pct that is not stated. Never invent numbers.")
    user = json.dumps({"guidance": guidance, "reported_quarters": qtr, "annual_report_excerpt": biz_ctx})
    res = jparse(llm(STRONG, syn_sys, user, 3000)) or {}
    res.update({"symbol": sym, "sample": False, "sources": list(dict.fromkeys(u for _, u in calls + ars))})
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, f"{sym}.json"), "w"), indent=1)
    print(f"wrote research/{sym}.json ({len(guidance)} guidance items)")


if __name__ == "__main__":
    main(sys.argv[1])