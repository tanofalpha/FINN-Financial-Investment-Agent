"""Two-stage announcement classifier.

Stage 1 (free): ordered regex rules on subject/headline. Covers the bulk.
Stage 2 (cheap LLM, optional): only for items that fall through to 'unclassified'
and whose text looks non-trivial. Results cached by content hash in cache/llm_class.json.

Priority 1-5 drives the digest: >=4 is shown, 3 is 'worth a glance', <=2 is collapsed.
"""
import hashlib
import json
import os
import re

CATEGORIES = [
    "results", "M&A", "fund_raise", "management_change", "litigation", "insider_trading",
    "earnings_call", "investor_meetings", "credit_rating", "dividend", "bonus_split",
    "capex", "press_release", "postal_ballot", "agm_egm", "pledging", "unclassified",
]

# Order matters: first match wins. Specific before generic.
RULES = [
    ("pledging", r"pledg|invocation|encumbrance"),
    ("insider_trading", r"regulation 7\(2\)|insider|sast|regulation 29|trading window|disposal of shares by promoter"),
    ("earnings_call", r"concall|conference call|earnings call|analyst.*meet.*(audio|transcript)|transcript of"),
    ("results", r"financial results|unaudited|audited.*results|quarterly results|results for the (quarter|year|half)|outcome of board meeting.*result|investor presentation|earnings (presentation|release)"),
    ("dividend", r"dividend|record date.*dividend"),
    ("bonus_split", r"bonus (issue|shares)|sub-?division|stock split"),
    ("management_change", r"resign|appoint(ment)? of (ceo|cfo|md|managing director|chief|director|whole.?time|independent director)|cessation|re-?appoint|change in (director|management|key managerial)|retire|senior management"),
    ("M&A", r"acqui(re|sition)|merger|amalgamat|demerger|scheme of arrangement|joint venture|\bjv\b|stake (in|sale)|subsidiary|divest|slump sale"),
    ("fund_raise", r"rights issue|qip|preferential (issue|allot)|buy-?back|commercial paper|ncd|non-convertible|fund ?raising|raising of funds|warrants"),
    ("litigation", r"litigation|court|tribunal|nclt|penalty|fine\b|show.?cause|order (from|by|of)|sebi order|income tax (demand|order)|gst (demand|order)|insolvency|notice from"),
    ("credit_rating", r"credit rating|crisil|icra|care ratings|india ratings|\brating\b"),
    ("capex", r"capex|capital expenditure|new (plant|facility|unit)|capacity expansion|commission(ing)? of"),
    ("postal_ballot", r"postal ballot"),
    ("agm_egm", r"\bagm\b|\begm\b|annual general meeting|extra-?ordinary general"),
    ("investor_meetings", r"analyst|investor (meet|conference|day)|schedule of (meeting|analyst)|one-on-one|institutional investor"),
    ("press_release", r"press release|order win|bagged|awarded|new product|launch|partnership|clarification|collaborat|mou\b"),
]
_COMPILED = [(c, re.compile(p, re.I)) for c, p in RULES]

# Base attention priority per category (1 = noise, 5 = drop everything).
PRIORITY = {
    "results": 5, "M&A": 5, "management_change": 4, "fund_raise": 4, "litigation": 4,
    "pledging": 4, "credit_rating": 3, "dividend": 3, "bonus_split": 3, "capex": 3,
    "insider_trading": 3, "press_release": 3, "earnings_call": 2, "investor_meetings": 1,
    "postal_ballot": 1, "agm_egm": 1, "unclassified": 1,
}

# Words that bump priority up or down within a category.
BUMP_UP = re.compile(r"ceo|cfo|managing director|\bmd\b|downgrade|default|fraud|resign|search and seizure|raid|going concern", re.I)
BUMP_DOWN = re.compile(r"intimation of (schedule|date)|prior intimation|newspaper (publication|advertisement)|loss of share certificate|duplicate|reg(ulation)? 74\(5\)|trading window closure", re.I)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "cache", "llm_class.json")


def classify_rules(subject: str):
    for cat, rx in _COMPILED:
        if rx.search(subject or ""):
            return cat
    return "unclassified"


def priority_for(category: str, subject: str) -> int:
    p = PRIORITY.get(category, 1)
    s = subject or ""
    if BUMP_DOWN.search(s):
        p = max(1, p - 2)
    elif BUMP_UP.search(s):
        p = min(5, p + 1)
    return p


def _load_cache():
    try:
        with open(CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _llm_classify(subject: str, body: str, cache: dict):
    """Optional cheap-model fallback. Wire your provider here; returns a category or None.
    Cached by content hash so re-runs cost nothing."""
    key = hashlib.sha1((subject + "|" + body[:500]).encode()).hexdigest()
    if key in cache:
        return cache[key]
    if not os.environ.get("FINN_LLM_CLASSIFY"):
        return None
    # TODO: call Gemini Flash / Haiku with a strict JSON schema over CATEGORIES.
    return None


def classify(item: dict, use_llm: bool = False) -> dict:
    subject = item.get("subject", "")
    cat = classify_rules(subject)
    method = "rules"
    if cat == "unclassified" and use_llm:
        cache = _load_cache()
        llm_cat = _llm_classify(subject, item.get("body", ""), cache)
        if llm_cat in CATEGORIES:
            cat, method = llm_cat, "llm"
    item["category"] = cat
    item["priority"] = priority_for(cat, subject)
    item["class_method"] = method
    return item


if __name__ == "__main__":
    tests = [
        "Outcome of Board Meeting - Unaudited Financial Results for quarter ended Sep 30, 2026",
        "Resignation of Chief Financial Officer",
        "Intimation of schedule of analyst/investor meet",
        "Disclosure under Regulation 7(2) - trading by promoter",
        "Acquisition of 51% stake in XYZ Pvt Ltd",
        "Credit rating reaffirmed by CRISIL",
        "Allotment of ESOP shares",
    ]
    for t in tests:
        r = classify({"subject": t})
        print(f"{r['priority']} {r['category']:<18} {t}")
