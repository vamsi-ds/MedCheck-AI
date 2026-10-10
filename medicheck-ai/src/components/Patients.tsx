import { useState } from 'react'
import { Search } from 'lucide-react'
import { Finding, patients } from '../data/demoData'
export default function Patients({ findings, openFinding }: { findings: Finding[]; openFinding: (f: Finding) => void }) {
  const [q, setQ] = useState(''); const [sel, setSel] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [done, setDone] = useState<string[]>([])
  const list = patients.filter(p => (p.id + p.name + p.hospital).toLowerCase().includes(q.toLowerCase()))
  const p = patients.find(x => x.id === sel)
  const mine = p ? findings.filter(f => f.patient === p.id) : []
  const analyze = () => { const id = p!.id; setBusy(true); setTimeout(() => { setBusy(false); setDone(d => [...d, id]) }, 1500) }
  return (<>
    <div className="row"><Search size={18} /><input className="input" style={{ maxWidth: 420 }} placeholder="Search by Patient ID, e.g. SYNTH-1001" value={q} onChange={e => setQ(e.target.value)} />{q && <button className="btn ghost" onClick={() => setQ('')}>Clear</button>}</div>
    <div className="glass scroll" style={{ marginTop: 14 }}><table><thead><tr><th>ID</th><th>Name</th><th>Hospital (fictional)</th><th>Docs</th><th>Findings</th><th>Updated</th></tr></thead><tbody>
      {list.map(x => (<tr key={x.id} onClick={() => setSel(x.id)} style={{ cursor: 'pointer', background: sel === x.id ? '#39d9ff14' : undefined }}>
        <td>{x.id}</td><td>{x.name}</td><td>{x.hospital}</td><td>{x.docs}</td><td>{findings.filter(f => f.patient === x.id).length}</td><td>{x.updated}</td></tr>))}
    </tbody></table>{!list.length && <p className="muted">No patients match “{q}”.</p>}</div>
    {p && <div className="glass" style={{ marginTop: 14 }}>
      <h3 style={{ marginTop: 0 }}>{p.id} · {p.name}</h3><p className="muted">{p.hospital} · {p.docs} documents · last updated {p.updated}</p>
      <button className="btn" onClick={analyze} disabled={busy}>{busy ? 'Scanning (simulated)…' : 'Analyze Records'}</button>
      {done.includes(p.id) && <div style={{ marginTop: 12 }}><small className="muted">Simulated analysis — predefined synthetic findings, no AI model involved.</small>
        {mine.map(f => <div key={f.id} className="row" style={{ marginTop: 8 }}><span className="tag">{f.cat}</span>{f.summary}<button className="btn ghost" onClick={() => openFinding(f)}>View Evidence</button></div>)}
        {!mine.length && <p>No findings for this patient.</p>}</div>}
    </div>}</>)
}
