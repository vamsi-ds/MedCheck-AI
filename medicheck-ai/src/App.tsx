import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { LayoutDashboard, Users, AlertTriangle, MessageSquare, FileBarChart } from 'lucide-react'
import AuthScreen from './components/AuthScreen'
import Overview from './components/Overview'
import Patients from './components/Patients'
import Findings from './components/Findings'
import Chat from './components/Chat'
import Reports from './components/Reports'
import EvidenceModal from './components/EvidenceModal'
import { Finding, initialFindings } from './data/demoData'

const nav = [['overview', 'Overview', LayoutDashboard], ['patients', 'Patients', Users], ['findings', 'Contradiction Findings', AlertTriangle], ['chat', 'AI Clarification', MessageSquare], ['reports', 'Reports', FileBarChart]] as const

export default function App() {
  const [auth, setAuth] = useState(false); const [page, setPage] = useState('overview')
  const [findings, setFindings] = useState(initialFindings); const [open, setOpen] = useState<Finding | null>(null)
  const [seed, setSeed] = useState(''); const [toast, setToast] = useState('')
  const say = (t: string) => { setToast(t); setTimeout(() => setToast(''), 2200) }
  const cur = open && findings.find(f => f.id === open.id)
  const review = () => { setFindings(fs => fs.map(f => f.id === open!.id ? { ...f, status: 'Reviewed' } : f)); say('Marked reviewed (demo state)') }
  const ask = (f: Finding) => { setOpen(null); setSeed(`Explain the ${f.cat.toLowerCase()} conflict. ${Date.now()}`); setPage('chat') }
  if (!auth) return <AuthScreen onEnter={() => setAuth(true)} />
  return (<div className="app">
    <aside className="side">
      <b style={{ padding: 10, color: '#39D9FF' }}>MediCheck AI</b>
      {nav.map(([k, l, I]) => <button key={k} className={'nav ' + (page === k ? 'on' : '')} onClick={() => setPage(k)}><I size={18} />{l}</button>)}
      <div style={{ marginTop: 'auto' }}><small className="muted">Night Devs · Healthcare Intelligence Prototype</small><br /><span className="tag warn">Demo mode</span></div>
    </aside>
    <main className="main">
      <h2 style={{ marginTop: 0 }}>{nav.find(n => n[0] === page)![1]}</h2>
      <AnimatePresence mode="wait"><motion.div key={page} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
        {page === 'overview' && <Overview findings={findings} go={setPage} />}
        {page === 'patients' && <Patients findings={findings} openFinding={setOpen} />}
        {page === 'findings' && <Findings findings={findings} openFinding={setOpen} ask={ask} />}
        {page === 'chat' && <Chat findings={findings} seed={seed.split('. ')[0] + '.'} />}
        {page === 'reports' && <Reports findings={findings} />}
      </motion.div></AnimatePresence>
    </main>
    <AnimatePresence>{cur && <EvidenceModal f={cur} onClose={() => setOpen(null)} onReview={review} onAsk={() => ask(cur)} />}</AnimatePresence>
    {toast && <div className="toast">{toast}</div>}
  </div>)
}
