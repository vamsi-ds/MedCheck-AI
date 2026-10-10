import { Finding } from '../data/demoData'
export default function Reports({ findings }: { findings: Finding[] }) {
  const csv = () => {
    const rows = [['id', 'patient', 'category', 'status', 'doc_a_date', 'doc_a_text', 'doc_b_date', 'doc_b_text'], ...findings.map(f => [f.id, f.patient, f.cat, f.status, f.a.date, f.a.text, f.b.date, f.b.text])]
    const body = rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\n')
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([body], { type: 'text/csv' })); a.download = 'medicheck-demo-findings.csv'; a.click()
  }
  return (<div className="glass"><h3 style={{ marginTop: 0 }}>Demo Report — synthetic data</h3>
    <p className="muted">Generated from local sample data and current review statuses. Not a clinical document.</p>
    <div className="scroll"><table><thead><tr><th>ID</th><th>Patient</th><th>Category</th><th>Status</th><th>Sources</th></tr></thead><tbody>
      {findings.map(f => <tr key={f.id}><td>{f.id}</td><td>{f.patient}</td><td>{f.cat}</td><td>{f.status}</td><td>{f.a.label} ({f.a.date}) vs {f.b.label} ({f.b.date})</td></tr>)}</tbody></table></div>
    <div className="row" style={{ marginTop: 14 }}><button className="btn" onClick={csv}>Export CSV</button><button className="btn ghost" onClick={() => window.print()}>Print / Save as PDF</button></div></div>)
}
