import { useEffect, useRef, useState } from 'react'
import { Finding, suggestions, fallback } from '../data/demoData'
interface Msg { who: 'me' | 'ai'; text: string }
function reply(q: string, fs: Finding[]): string {
  const s = q.toLowerCase(); const by = (c: string) => fs.filter(f => f.cat === c)
  const line = (f: Finding) => `${f.id} (${f.patient}): Document A, ${f.a.date}, says “${f.a.text}” while Document B, ${f.b.date}, says “${f.b.text}”`
  if (s.includes('allerg')) return by('Allergy').map(line).join('. ') + '. These statements conflict and should be verified by an authorized healthcare professional.'
  if (s.includes('medic')) return by('Medication').map(line).join('. ') + '. The entries differ; a reviewer should confirm the current regimen.'
  if (s.includes('diagnos')) return by('Diagnosis').map(line).join('. ') + '. Status wording differs and needs clinical review.'
  if (s.includes('summar') || s.includes('documents')) return `${fs.length} potential findings in the sample data: ` + fs.map(f => `${f.id} ${f.cat}`).join(', ') + '.'
  if (s.includes('verify') || s.includes('reviewer')) return 'A reviewer should check the source documents, dates, and authors for each flagged pair, and confirm with the patient or treating clinician. This demo does not choose which record is right.'
  return fallback
}
export default function Chat({ findings, seed }: { findings: Finding[]; seed: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([]); const [text, setText] = useState(''); const [typing, setTyping] = useState(false); const end = useRef<HTMLDivElement>(null)
  const send = (q: string) => { if (!q.trim()) return; setMsgs(m => [...m, { who: 'me', text: q }]); setText(''); setTyping(true); setTimeout(() => { setTyping(false); setMsgs(m => [...m, { who: 'ai', text: reply(q, findings) }]) }, 900) }
  useEffect(() => { if (seed) send(seed) }, [seed]) // eslint-disable-line
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [msgs, typing])
  return (<div className="glass">
    <small className="muted">Rule-based demo assistant using sample findings. Not connected to a live medical AI service.</small>
    <div style={{ minHeight: 260, maxHeight: '50vh', overflow: 'auto' }}>
      {msgs.map((m, i) => <div key={i} className={'bubble ' + m.who}>{m.text}</div>)}{typing && <div className="bubble ai">Typing…</div>}<div ref={end} /></div>
    <div className="row">{suggestions.map(s => <button key={s} className="btn ghost" onClick={() => send(s)}>{s}</button>)}</div>
    <div className="row" style={{ marginTop: 10 }}><input className="input" style={{ flex: 1 }} value={text} placeholder="Ask about a sample finding…" onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send(text)} />
      <button className="btn" onClick={() => send(text)}>Send</button><button className="btn ghost" onClick={() => setMsgs([])}>Clear</button></div></div>)
}
