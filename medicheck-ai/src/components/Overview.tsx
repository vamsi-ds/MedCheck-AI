import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { Finding, patients } from '../data/demoData'
function Count({ to }: { to: number }) {
  const [n, set] = useState(0)
  useEffect(() => { let i = 0; const t = setInterval(() => { i++; set(Math.round(to * Math.min(i / 20, 1))); if (i >= 20) clearInterval(t) }, 30); return () => clearInterval(t) }, [to])
  return <span className="big">{n}</span>
}
export default function Overview({ findings, go }: { findings: Finding[]; go: (p: string) => void }) {
  const cats = ['Allergy', 'Medication', 'Diagnosis'].map(c => ({ name: c, value: findings.filter(f => f.cat === c).length }))
  const pending = findings.filter(f => f.status === 'Needs Review').length
  const stats: [string, number, string][] = [['Synthetic Patients', patients.length, 'patients'], ['Documents (demo)', patients.reduce((a, p) => a + p.docs, 0), 'patients'], ['Potential Findings', findings.length, 'findings'], ['Pending Reviews', pending, 'findings']]
  const status = [{ name: 'Needs Review', value: pending }, { name: 'Reviewed', value: findings.length - pending }]
  return (<>
    <p className="muted">Demo Data — fictional records, illustrative values only.</p>
    <div className="grid">{stats.map(([l, v, p]) => (
      <div key={l} className="glass tilt" style={{ cursor: 'pointer' }} onClick={() => go(p)}><div className="muted">{l}</div><Count to={v} /></div>))}</div>
    <div className="grid" style={{ marginTop: 16 }}>
      <div className="glass"><b>Findings by category</b><ResponsiveContainer width="100%" height={220}><BarChart data={cats}><XAxis dataKey="name" stroke="#8291A8" /><YAxis allowDecimals={false} stroke="#8291A8" /><Tooltip /><Bar dataKey="value" fill="#39D9FF" radius={6} /></BarChart></ResponsiveContainer></div>
      <div className="glass"><b>Findings by status</b><ResponsiveContainer width="100%" height={220}><PieChart><Pie data={status} dataKey="value" nameKey="name" label>{status.map((_, i) => <Cell key={i} fill={['#FFBD59', '#25D6B0'][i]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
    </div>
    <div className="row" style={{ marginTop: 16 }}>
      <button className="btn" onClick={() => go('patients')}>Search Patient</button>
      <button className="btn" onClick={() => go('findings')}>Explore Findings</button>
      <button className="btn" onClick={() => go('chat')}>Ask AI Assistant</button>
      <button className="btn" onClick={() => go('reports')}>Preview Report</button>
    </div></>)
}
