import { useEffect, useMemo, useState } from 'react'

const WINDOWS = [{ k: 24, l: '24h' }, { k: 72, l: '3 days' }, { k: 168, l: '7 days' }]
const ALL_CATS = ['results', 'M&A', 'management_change', 'fund_raise', 'litigation', 'pledging', 'credit_rating', 'dividend', 'capex', 'press_release']
const LABEL = { management_change: 'Mgmt change', fund_raise: 'Fund raise', credit_rating: 'Credit rating', press_release: 'Press', insider_trading: 'Insider', earnings_call: 'Earnings call', investor_meetings: 'Investor mtg', postal_ballot: 'Postal ballot', agm_egm: 'AGM/EGM', bonus_split: 'Bonus/split' }
const lab = (c) => LABEL[c] || (c[0].toUpperCase() + c.slice(1))

function usePersisted(key, init) {
  const [v, setV] = useState(() => {
    try { return { ...init, ...JSON.parse(localStorage.getItem(key) || '{}') } } catch { return init }
  })
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)) } catch {} }, [key, v])
  return [v, setV]
}

function ago(ts, ref) {
  const h = Math.max(0, (ref - new Date(ts)) / 36e5)
  return h < 1 ? 'just now' : h < 24 ? `${Math.round(h)}h ago` : `${Math.round(h / 24)}d ago`
}

// Same logic as backend/triggers.py, run client-side so thresholds are live-configurable.
function marketAlerts(prices, cfg) {
  const out = []
  for (const [sym, s] of Object.entries(prices || {})) {
    if (s.length < 3) continue
    const last = s[s.length - 1], prev = s[s.length - 2]
    const base = s.slice(-21, -1)
    const avg = base.reduce((a, b) => a + b.v, 0) / (base.length || 1)
    const pct = (last.c / prev.c - 1) * 100
    const ratio = avg ? last.v / avg : 0
    if (ratio >= cfg.volMult) out.push({ sym, kind: 'Volume', main: `${ratio.toFixed(1)}×`, detail: 'vs 20-day avg', dir: 0 })
    if (Math.abs(pct) >= cfg.pricePct) out.push({ sym, kind: 'Price', main: `${pct > 0 ? '+' : ''}${pct.toFixed(1)}%`, detail: 'on the day', dir: pct > 0 ? 1 : -1 })
  }
  return out
}

export default function App() {
  const [snap, setSnap] = useState(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState('feed')
  const [win, setWin] = useState(24)
  const [cfg, setCfg] = usePersisted('finn.cfg', { volMult: 2, pricePct: 3, minPriority: 4, cats: ['results', 'M&A', 'management_change', 'fund_raise', 'litigation', 'pledging'] })
  const [sheet, setSheet] = useState(null) // symbol
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetch('/data/snapshot.json').then((r) => r.json()).then(setSnap).catch(() => setErr('No snapshot found. Run backend/build_snapshot.py'))
  }, [])

  const ref = useMemo(() => (snap ? new Date(snap.generated_at) : new Date()), [snap])
  const names = useMemo(() => Object.fromEntries((snap?.portfolio || []).map((p) => [p.symbol, p.name])), [snap])

  const items = useMemo(() => (snap?.announcements || []).filter((a) => ref - new Date(a.ts) <= win * 36e5), [snap, win, ref])
  const matters = items.filter((a) => a.priority >= cfg.minPriority)
  const routine = items.filter((a) => a.priority < cfg.minPriority)
  const alerts = useMemo(() => marketAlerts(snap?.prices, cfg), [snap, cfg])
  const catAlerts = matters.filter((a) => cfg.cats.includes(a.category))

  if (err) return <div className="app"><p className="note" style={{ paddingTop: 40 }}>{err}</p></div>
  if (!snap) return <div className="app" />

  return (
    <div className="app">
      <header className="top">
        <div className="brand">FIN<b>N</b></div>
        <div className="stamp">
          {snap.mode === 'mock' && <span className="badge-sample">sample data</span>}
          <span style={{ marginLeft: 6 }}>as of {ref.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
        </div>
      </header>

      {tab === 'feed' && (
        <>
          <div className="seg">{WINDOWS.map((w) => <button key={w.k} className={win === w.k ? 'on' : ''} onClick={() => setWin(w.k)}>{w.l}</button>)}</div>
          <div className="headline">
            <div className="big"><em>{matters.length}</em> {matters.length === 1 ? 'thing matters' : 'things matter'}.<br />{routine.length} routine, tucked away.</div>
            <div className="sub">{alerts.length + catAlerts.length} alerts tripped your thresholds across {snap.portfolio.length} holdings.</div>
          </div>

          {alerts.length > 0 && (
            <>
              <div className="sec"><span>Unusual moves</span><span>vol ≥ {cfg.volMult}× · move ≥ {cfg.pricePct}%</span></div>
              <div className="alerts">
                {alerts.map((a, i) => (
                  <div key={i} className={`alert ${a.dir > 0 ? 'up' : a.dir < 0 ? 'down' : ''}`} onClick={() => { setSheet(a.sym) }}>
                    <div className="k">{a.kind}</div>
                    <div className="s">{a.sym} <span className={a.dir > 0 ? 'up' : a.dir < 0 ? 'down' : ''}>{a.main}</span></div>
                    <div className="d">{a.detail}</div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="sec"><span>Matters first</span><span>priority ≥ {cfg.minPriority}</span></div>
          {matters.length === 0 && <p className="note">Nothing material in this window. That is the point.</p>}
          {matters.map((a, i) => <Card key={i} a={a} name={names[a.symbol]} ref0={ref} onDig={() => setSheet(a.symbol)} />)}

          {routine.length > 0 && (
            <>
              <button className="fold" onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Show'} {routine.length} routine filings</button>
              {open && routine.map((a, i) => (
                <div className="mini" key={i}>
                  <b>{a.symbol}</b><span className="t">{a.subject}</span>
                  {a.url ? <a className="when" style={{ color: 'var(--blue)' }} href={a.url} target="_blank" rel="noreferrer">PDF</a> : <span className="when">{lab(a.category)}</span>}
                </div>
              ))}
            </>
          )}
        </>
      )}

      {tab === 'ask' && <Ask snap={snap} onPick={setSheet} />}
      {tab === 'alerts' && <Settings cfg={cfg} setCfg={setCfg} />}

      <nav className="tabs"><div className="in">
        <button className={tab === 'feed' ? 'on' : ''} onClick={() => setTab('feed')}>Feed</button>
        <button className={tab === 'ask' ? 'on' : ''} onClick={() => setTab('ask')}>Research</button>
        <button className={tab === 'alerts' ? 'on' : ''} onClick={() => setTab('alerts')}>Alerts</button>
      </div></nav>

      {sheet && (
        <>
          <div className="sheet-bg" onClick={() => setSheet(null)} />
          <div className="sheet"><div className="grab" /><Company symbol={sheet} name={names[sheet]} snap={snap} /></div>
        </>
      )}
    </div>
  )
}

function Card({ a, name, ref0, onDig }) {
  return (
    <div className="card">
      <div className="row1">
        <div><span className="sym">{a.symbol}</span><span className="nm">{name}</span></div>
        <span className="when">{ago(a.ts, ref0)}</span>
      </div>
      <div className="subj">{a.subject}</div>
      <span className={`chip p${a.priority}`}>{lab(a.category)}</span>
      {a.extracted && <Results x={a.extracted} />}
      <div className="actions">
        <button className="btn pri" onClick={onDig}>Dig in</button>
        {a.url && <a className="btn" href={a.url} target="_blank" rel="noreferrer">Filing</a>}
      </div>
    </div>
  )
}

const pc = (n, p) => (p ? ((n / p - 1) * 100) : null)
const Delta = ({ v }) => v == null ? <span>–</span> : <span className={v >= 0 ? 'up' : 'down'}>{v >= 0 ? '+' : ''}{v.toFixed(1)}%</span>
function Results({ x }) {
  return (
    <div style={{ marginTop: 10 }}>
      <table className="nums mono">
        <thead><tr><th>₹ Cr</th><th>Q</th><th>QoQ</th><th>YoY</th></tr></thead>
        <tbody>
          {['revenue', 'ebitda', 'pbt', 'pat'].map((k) => (
            <tr key={k}><td>{k.toUpperCase()}</td><td>{x[k].q.toLocaleString('en-IN')}</td><td><Delta v={pc(x[k].q, x[k].qoq)} /></td><td><Delta v={pc(x[k].q, x[k].yoy)} /></td></tr>
          ))}
        </tbody>
      </table>
      {x.sample && <div className="note" style={{ marginTop: 6 }}>Synthetic numbers: shows the extraction schema, not real results.</div>}
    </div>
  )
}

function Ask({ snap, onPick }) {
  const [q, setQ] = useState('')
  const sym = q.trim().toUpperCase().replace(/\.(NS|BO)$/, '')
  return (
    <div style={{ marginTop: 16 }}>
      <div className="headline"><div className="big">Dig into any company.</div><div className="sub">Grounded in annual reports and concall transcripts only.</div></div>
      <input className="input" placeholder="NSE ticker, e.g. TATAELXSI" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sym && onPick(sym)} autoCapitalize="characters" />
      <div className="chips">{['DEMOCO', ...snap.research, ...snap.portfolio.slice(0, 3).map((p) => p.symbol)].map((s) => <button key={s} onClick={() => onPick(s)}>{s}</button>)}</div>
      <p className="note">The research engine is ticker-agnostic: <span className="mono">python backend/research.py TICKER</span> builds the view for any NSE stock with data on screener.in.</p>
    </div>
  )
}

function Company({ symbol, name, snap }) {
  const [r, setR] = useState(undefined)
  const [sec, setSec] = useState('pvd')
  const q = (snap.summaries || {})[symbol]
  useEffect(() => {
    setR(undefined)
    fetch(`/data/research/${symbol}.json`).then((x) => x.json()).then(setR).catch(() => setR(null))
  }, [symbol])
  return (
    <div>
      <div className="row1" style={{ marginBottom: 6 }}>
        <div><span className="sym" style={{ fontSize: 20 }}>{symbol}</span><span className="nm">{name}</span></div>
        {q && <span className="mono">₹{q.close.toLocaleString('en-IN')} <span className={q.pct >= 0 ? 'up' : 'down'}>{q.pct >= 0 ? '+' : ''}{q.pct}%</span></span>}
      </div>
      {r === undefined && <p className="note">Loading…</p>}
      {r === null && <p className="note">No research cached for {symbol}. Run <span className="mono">python backend/research.py {symbol}</span> to build it from the latest annual report and concall transcripts.</p>}
      {r && (
        <>
          {r.sample && <p className="note"><span className="badge-sample" style={{ marginLeft: 0 }}>sample</span> Synthetic company showing the output schema. Real runs cite the source passage for every claim.</p>}
          <div className="seg" style={{ margin: '10px 0' }}>
            {[['pvd', 'Promised vs delivered'], ['biz', 'Business'], ['bb', 'Bull / Bear']].map(([k, l]) => <button key={k} className={sec === k ? 'on' : ''} onClick={() => setSec(k)}>{l}</button>)}
          </div>
          {sec === 'biz' && <div><p style={{ fontSize: 14, lineHeight: 1.45 }}>{r.business.summary}</p>{r.business.segments.map((s) => <div className="mini" key={s.name}><span>{s.name}</span><b className="mono">{s.pct}%</b></div>)}</div>}
          {sec === 'bb' && <div className="cols"><div><span className="chip good">Bull</span><ul>{r.bull.map((b, i) => <li key={i}>{b}</li>)}</ul></div><div><span className="chip bad">Bear</span><ul>{r.bear.map((b, i) => <li key={i}>{b}</li>)}</ul></div></div>}
          {sec === 'pvd' && r.pvd.map((p, i) => (
            <div className="pvd" key={i}>
              <div className="m"><span>{p.metric} <span className="q">· {p.period}</span></span><span className={`chip ${p.verdict === 'missed' ? 'bad' : p.verdict === 'unclear' ? 'meh' : 'good'}`}>{p.verdict}</span></div>
              <div><span className="q">Said:</span> {p.promised}</div>
              <div><span className="q">Did:</span> {p.delivered}</div>
              <div className="src">{p.source}</div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}

function Settings({ cfg, setCfg }) {
  const set = (k, v) => setCfg({ ...cfg, [k]: v })
  const toggle = (c) => set('cats', cfg.cats.includes(c) ? cfg.cats.filter((x) => x !== c) : [...cfg.cats, c])
  return (
    <div style={{ marginTop: 16 }}>
      <div className="headline"><div className="big">You decide what's unusual.</div><div className="sub">Thresholds apply instantly to the feed.</div></div>
      <label className="sl">Volume spike: <b className="mono">{cfg.volMult}×</b> the 20-day average</label>
      <input type="range" min="1.2" max="5" step="0.1" value={cfg.volMult} onChange={(e) => set('volMult', +e.target.value)} />
      <label className="sl">Price move: <b className="mono">±{cfg.pricePct}%</b> in a day</label>
      <input type="range" min="1" max="10" step="0.5" value={cfg.pricePct} onChange={(e) => set('pricePct', +e.target.value)} />
      <label className="sl">Matters when priority ≥ <b className="mono">{cfg.minPriority}</b> (5 = results, M&A)</label>
      <input type="range" min="2" max="5" step="1" value={cfg.minPriority} onChange={(e) => set('minPriority', +e.target.value)} />
      <label className="sl">Announcement types I care about</label>
      <div className="chips">{ALL_CATS.map((c) => <button key={c} className={cfg.cats.includes(c) ? 'on' : ''} onClick={() => toggle(c)}>{lab(c)}</button>)}</div>
      <p className="note">Alerts are evaluated on end-of-day data and the latest exchange filings. Settings are stored on this device.</p>
    </div>
  )
}
