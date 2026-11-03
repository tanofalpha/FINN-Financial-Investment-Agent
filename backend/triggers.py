"""Trigger evaluation. Pure functions over the snapshot so the same logic exists in the
frontend (TypeScript port reads the same defaults) and thresholds stay user-configurable."""

DEFAULTS = {
    "vol_mult": 2.0,          # volume > N x trailing 20d average
    "price_move_pct": 3.0,    # |1-day move| >= X%
    "categories": ["results", "M&A", "management_change", "fund_raise", "litigation", "pledging"],
    "min_priority": 4,
}


def market_triggers(summaries: dict, cfg: dict = None):
    cfg = {**DEFAULTS, **(cfg or {})}
    out = []
    for sym, s in summaries.items():
        if not s:
            continue
        if s.get("vol_ratio") and s["vol_ratio"] >= cfg["vol_mult"]:
            out.append({"type": "volume", "symbol": sym, "date": s["date"],
                        "detail": f"Volume {s['vol_ratio']}x the 20-day average", "value": s["vol_ratio"]})
        if abs(s["pct"]) >= cfg["price_move_pct"]:
            out.append({"type": "price", "symbol": sym, "date": s["date"],
                        "detail": f"{s['pct']:+.2f}% on the day", "value": s["pct"]})
    return out


def announcement_triggers(items: list, cfg: dict = None):
    cfg = {**DEFAULTS, **(cfg or {})}
    return [i for i in items
            if i["category"] in cfg["categories"] and i["priority"] >= cfg["min_priority"]]
