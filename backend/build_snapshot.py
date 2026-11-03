"""Build the cached snapshot the frontend reads. Run: python build_snapshot.py [--mock] [--days 7]

Design: fetch once, classify, evaluate default triggers, write JSON. The demo never scrapes live.
If a live fetch returns nothing, the previous snapshot is kept (so a flaky exchange can't blank the app).
"""
import argparse
import json
import os
from datetime import datetime

from classifier import classify
from triggers import DEFAULTS, announcement_triggers, market_triggers

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "frontend", "public", "data", "snapshot.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--llm", action="store_true", help="use cheap-LLM fallback for unclassified")
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(HERE, "portfolio.json")))
    portfolio = cfg["portfolio"]
    symbols = [p["symbol"] for p in portfolio]

    if args.mock:
        from mock import mock_announcements, mock_prices
        prices, anns = mock_prices(symbols), mock_announcements(symbols, args.days)
    else:
        from fetch_announcements import fetch_announcements
        from fetch_prices import fetch_prices
        prices, anns = fetch_prices(symbols), fetch_announcements(portfolio, args.days)
        if not prices and not anns and os.path.exists(OUT):
            print("Live fetch empty; keeping previous snapshot.")
            return

    from fetch_prices import summarize
    anns = [classify(a, use_llm=args.llm) for a in anns]
    anns.sort(key=lambda a: a["ts"], reverse=True)  # newest first; UI handles priority grouping
    if args.mock:  # synthetic extraction so the UI card renders; real runs use enrich.py
        for a in anns:
            if a["category"] == "results":
                a["extracted"] = {"sample": True, "revenue": {"q": 10450, "qoq": 9980, "yoy": 9320},
                                  "ebitda": {"q": 2610, "qoq": 2500, "yoy": 2290}, "pbt": {"q": 1980, "qoq": 1890, "yoy": 1710},
                                  "pat": {"q": 1480, "qoq": 1420, "yoy": 1260}}
    summaries = {s: summarize(prices[s]) for s in prices}

    snapshot = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "mock" if args.mock else "live",
        "defaults": DEFAULTS,
        "portfolio": portfolio,
        "research": cfg["research"],
        "prices": prices,              # raw series so the UI can re-run triggers with user thresholds
        "summaries": summaries,
        "announcements": anns,
        "market_triggers": market_triggers(summaries),
        "announcement_triggers": announcement_triggers(anns),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(snapshot, f, separators=(",", ":"))
    print(f"wrote {OUT}: {len(anns)} announcements, {len(snapshot['market_triggers'])} market triggers, "
          f"{len(snapshot['announcement_triggers'])} announcement triggers ({snapshot['mode']})")


if __name__ == "__main__":
    main()
