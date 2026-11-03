"""End-of-day price + volume via yfinance. Returns a compact per-symbol series."""
import pandas as pd

HISTORY_DAYS = 90


def fetch_prices(symbols, period_days=HISTORY_DAYS):
    import yfinance as yf  # imported lazily so mock mode needs no network libs

    tickers = [f"{s}.NS" for s in symbols]
    df = yf.download(
        tickers, period=f"{period_days}d", interval="1d",
        group_by="ticker", auto_adjust=False, progress=False, threads=True,
    )
    out = {}
    for s in symbols:
        t = f"{s}.NS"
        try:
            sub = df[t] if len(symbols) > 1 else df
            sub = sub.dropna(subset=["Close"])
            if sub.empty:
                continue
            out[s] = [
                {"d": idx.strftime("%Y-%m-%d"), "c": round(float(r["Close"]), 2), "v": int(r["Volume"])}
                for idx, r in sub.iterrows()
            ]
        except Exception as e:  # one bad ticker shouldn't sink the run
            print(f"[prices] {s}: {e}")
    return out


def summarize(series):
    """Latest-day stats: pct change, volume vs trailing 20d avg (excluding today)."""
    if len(series) < 3:
        return None
    s = pd.DataFrame(series)
    last, prev = s.iloc[-1], s.iloc[-2]
    base = s["v"].iloc[-21:-1]
    avg = float(base.mean()) if len(base) else 0.0
    return {
        "date": last["d"],
        "close": float(last["c"]),
        "pct": round((last["c"] / prev["c"] - 1) * 100, 2),
        "vol": int(last["v"]),
        "vol_avg20": int(avg),
        "vol_ratio": round(last["v"] / avg, 2) if avg else None,
    }
