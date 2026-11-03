"""Deterministic mock data so the UI and pipeline run with zero network.
Seeds a few realistic events (results, CFO exit, volume spike) so the demo has something to triage."""
import random
from datetime import datetime, timedelta

SUBJECTS = [
    "Outcome of Board Meeting - Unaudited Financial Results for the quarter ended Sep 30, 2026",
    "Resignation of Chief Financial Officer",
    "Appointment of Independent Director",
    "Acquisition of 51% stake in a subsidiary",
    "Intimation of schedule of analyst/investor meet",
    "Transcript of Earnings Call - Q2 FY27",
    "Credit rating reaffirmed by CRISIL",
    "Declaration of interim dividend",
    "Disclosure under Regulation 7(2) - trading by promoter",
    "Allotment of ESOP shares",
    "Newspaper publication of results",
    "Press release: bags large order",
    "Postal ballot notice",
    "Trading window closure",
    "Certificate under Regulation 74(5)",
]


def mock_prices(symbols, days=90, seed=7):
    rnd = random.Random(seed)
    out = {}
    end = datetime.now().date()
    for s in symbols:
        px, base_v = rnd.uniform(200, 4000), rnd.randint(800_000, 8_000_000)
        series = []
        dates = [end - timedelta(days=i) for i in range(days * 7 // 5, -1, -1) if (end - timedelta(days=i)).weekday() < 5][-days:]
        for d in dates:
            px *= 1 + rnd.gauss(0, 0.012)
            series.append({"d": d.isoformat(), "c": round(px, 2), "v": int(base_v * rnd.uniform(0.7, 1.3))})
        out[s] = series
    # seeded events on the last day
    for s, mult, move in [(symbols[0], 2.8, 0.04), (symbols[3], 2.2, -0.036), (symbols[9], 1.4, 0.052)]:
        out[s][-1]["v"] = int(out[s][-1]["v"] * mult)
        out[s][-1]["c"] = round(out[s][-2]["c"] * (1 + move), 2)
    return out


def mock_announcements(symbols, days=7, seed=11):
    rnd = random.Random(seed)
    now = datetime.now()
    items = []
    for s in symbols:
        for _ in range(rnd.randint(1, 4)):
            items.append({
                "symbol": s,
                "ts": (now - timedelta(hours=rnd.randint(1, days * 24))).strftime("%Y-%m-%dT%H:%M:%S"),
                "subject": rnd.choice(SUBJECTS), "body": "", "url": None, "source": "MOCK",
            })
    return items
