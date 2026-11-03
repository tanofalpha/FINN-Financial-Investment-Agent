# FINN: Financial Investment Agent (ENAM build challenge)

Mobile-first investor triage: Push (digest + triggers) and Pull (company research), one flow.

## Backend (data layer)

```bash
cd backend
pip install -r requirements.txt
python build_snapshot.py --mock      # zero-network, seeded demo events
python build_snapshot.py --days 7    # live: yfinance + BSE (NSE fallback)
python classifier.py                 # classifier smoke test
```

Output: `frontend/public/data/snapshot.json` (prices, summaries, classified announcements, default triggers).

## Design decisions
- **Snapshot-first**: fetch once, cache JSON, never scrape live during a demo. If a live fetch returns nothing, the previous snapshot is kept.
- **Two-stage classification**: ordered regex rules first (free), cheap LLM only for `unclassified` items, cached by content hash (hook in `classifier.py`, off by default).
- **Priority 1-5** per item drives the digest: 4+ surfaced, 3 glance, 1-2 collapsed.
- **Triggers are pure functions over raw series**, and the snapshot ships the raw series, so the UI can re-run them with user-chosen thresholds.

## Known caveats
- BSE scrip codes in `portfolio.json` are best-effort; verify them.
- BSE/NSE endpoints need browser-like headers and can rate-limit; run live fetch from your own machine.

## Next
Frontend (Vite + React): triage feed, trigger settings, results card, chat bottom sheet.
Pull engine: screener.in links, then transcript chunking, then promised-vs-delivered.
