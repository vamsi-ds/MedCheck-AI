import { motion } from 'framer-motion'
import { Finding } from '../data/demoData'
export default function EvidenceModal({ f, onClose, onReview, onAsk }: { f: Finding; onClose: () => void; onReview: () => void; onAsk: () => void }) {
  return (<motion.div className="modal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
    <motion.div className="glass" initial={{ y: 30, scale: .96 }} animate={{ y: 0, scale: 1 }} onClick={e => e.stopPropagation()}>
      <h3 style={{ marginTop: 0 }}>{f.id} · {f.cat} · {f.patient}</h3>
      <div className="cmp">{[f.a, f.b].map(d => <div key={d.label} className="glass"><b>{d.label}</b><div className="muted">{d.date}</div><p><mark>{d.text}</mark></p></div>)}</div>
      <p>Potential contradiction: {f.summary} A qualified reviewer should verify the patient’s history. This prototype does not decide which record is correct.</p>
      <p>Status: <span className={'tag ' + (f.status === 'Reviewed' ? 'ok' : 'warn')}>{f.status}</span></p>
      <div className="row"><button className="btn" onClick={onReview} disabled={f.status === 'Reviewed'}>Mark Reviewed</button><button className="btn ghost" onClick={onAsk}>Ask AI About This</button><button className="btn ghost" onClick={onClose}>Close</button></div>
    </motion.div></motion.div>)
}
