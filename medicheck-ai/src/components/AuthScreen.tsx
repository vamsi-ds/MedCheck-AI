import { useState } from 'react'
import { ShieldCheck, FileText, Eye, EyeOff } from 'lucide-react'
export default function AuthScreen({ onEnter }: { onEnter: () => void }) {
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [show, setShow] = useState(false); const [err, setErr] = useState('')
  const submit = () => (email.length < 3 || pw.length < 4) ? setErr('Enter a username and a password (4+ characters). Demo only — no real authentication.') : onEnter()
  return (
    <div className="auth">
      <section className="hero">
        <div className="scan" />
        <div className="row"><ShieldCheck color="#39D9FF" size={34} /><b style={{ fontSize: 24 }}>MediCheck AI</b></div>
        <h1>Every Record Tells a Story. We Find the Conflicts.</h1>
        <p className="muted">Explore an intelligent approach to identifying inconsistencies across healthcare records with evidence-led insights.</p>
        <b style={{ color: '#25D6B0' }}>Detect. Explain. Verify. Stay Safer.</b>
        <div className="row">{['Record A', 'Record B', 'Record C'].map(r => (
          <div key={r} className="glass floaty tilt"><FileText color="#8B7CFF" /><div>{r}</div><small className="muted">synthetic</small></div>))}</div>
      </section>
      <section className="authcard"><div className="glass">
        <h2 style={{ margin: 0 }}>Welcome back</h2>
        <input className="input" placeholder="Email or username" value={email} onChange={e => setEmail(e.target.value)} />
        <div style={{ position: 'relative' }}>
          <input className="input" type={show ? 'text' : 'password'} placeholder="Password" value={pw} onChange={e => setPw(e.target.value)} />
          <button aria-label="Toggle password" onClick={() => setShow(!show)} style={{ position: 'absolute', right: 8, top: 8, background: 'none', border: 0, cursor: 'pointer' }}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
        </div>
        <label className="muted"><input type="checkbox" /> Remember me</label>
        {err && <small style={{ color: '#FFBD59' }}>{err}</small>}
        <button className="btn" onClick={submit}>Sign in</button>
        <button className="btn ghost" onClick={onEnter}>Enter Demo Experience</button>
        <small className="muted">Hackathon frontend prototype. Not a clinically validated system.</small>
      </div></section>
    </div>)
}
