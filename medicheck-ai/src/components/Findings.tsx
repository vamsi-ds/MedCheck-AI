import { useState } from 'react'
import { Finding } from '../data/demoData'
const filters = ['All', 'Allergy', 'Medication', 'Diagnosis', 'Needs Review', 'Reviewed']
export default function Findings({ findings, openFinding, ask }: { findings: Finding[]; openFinding: (f: Finding) => void; ask: (f: Finding) => void }) {
  const [f, setF] = useState('All')
  const list = findings.filter(x => f === 'All' || x.cat === f || x.status === f)
  return (<>
    <div className="row">{filters.map(x => <button key={x} className={'btn ' + (f === x ? '' : 'ghost')} onClick={() => setF(x)}>{x}</button>)}</div>
    <div className="glass scroll" style={{ marginTop: 14 }}><table><thead><tr><th>ID</th><th>Patient</th><th>Category</th><th>Explanation</th><th>Status</th><th /></tr></thead><tbody>
      {list.map(x => (<tr key={x.id}>
        <td>{x.id}</td><td>{x.patient}</td><td>{x.cat}</td><td>{x.summary}</td><td><span className={'tag ' + (x.status === 'Reviewed' ? 'ok' : 'warn')}>{x.status}</span></td>
        <td><div className="row"><button className="btn ghost" onClick={() => openFinding(x)}>View Evidence</button><button className="btn ghost" onClick={() => ask(x)}>Ask AI</button></div></td></tr>))}
    </tbody></table>{!list.length && <p className="muted">No findings for this filter.</p>}</div></>)
}
