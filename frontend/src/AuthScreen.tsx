import { useState } from 'react'
import { HeartPulse, ShieldCheck } from 'lucide-react'
import { api, ApiError } from './api'
import type { User } from './api'

/**
 * Login + registration-request screen.
 *
 * Registration creates an account request that an administrator must approve;
 * the UI says so explicitly. The role shown after login always comes from the
 * server session, never from a client-side selector.
 */
export default function AuthScreen({
  onAuthenticated,
}: {
  onAuthenticated: (user: User) => void
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<'doctor' | 'records_staff' | 'patient'>('doctor')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    setInfo('')
    setBusy(true)
    try {
      if (mode === 'login') {
        const res = await api.login(username.trim(), password)
        onAuthenticated(res.user)
      } else {
        await api.register({
          username: username.trim(),
          email: email.trim(),
          full_name: fullName.trim(),
          password,
          role,
        })
        setMode('login')
        setInfo(
          'Registration received. Your account must be approved by an administrator before you can sign in.',
        )
        setPassword('')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unexpected error. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="brand auth-brand">
          <span className="brand-icon">
            <HeartPulse size={23} />
          </span>
          <span>
            MedCheck <b>AI</b>
          </span>
        </div>

        <div className="auth-tabs">
          <button
            className={`patient-tab ${mode === 'login' ? 'selected' : ''}`}
            onClick={() => {
              setMode('login')
              setError('')
              setInfo('')
            }}
            type="button"
          >
            Sign in
          </button>
          <button
            className={`patient-tab ${mode === 'register' ? 'selected' : ''}`}
            onClick={() => {
              setMode('register')
              setError('')
              setInfo('')
            }}
            type="button"
          >
            Request account
          </button>
        </div>

        <form onSubmit={submit} className="auth-form">
          {mode === 'register' && (
            <label className="form-field">
              Full name
              <input
                className="form-input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                minLength={2}
                placeholder="e.g. Dr. Rahul Sharma"
              />
            </label>
          )}

          <label className="form-field">
            Username
            <input
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              autoComplete="username"
            />
          </label>

          {mode === 'register' && (
            <label className="form-field">
              Email
              <input
                className="form-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
          )}

          <label className="form-field">
            Password
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </label>

          {mode === 'register' && (
            <label className="form-field">
              Requested role
              <select
                className="form-input"
                value={role}
                onChange={(e) =>
                  setRole(e.target.value as 'doctor' | 'records_staff' | 'patient')
                }
              >
                <option value="doctor">Doctor / Healthcare Professional</option>
                <option value="records_staff">Medical Records Staff</option>
                <option value="patient">Patient</option>
              </select>
              <small className="form-hint">
                Administrator accounts cannot be requested. New accounts await admin approval.
              </small>
            </label>
          )}

          {error && <div className="error-box">{error}</div>}
          {info && <div className="notice">{info}</div>}

          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Submit request'}
          </button>
        </form>

        <div className="auth-footer">
          <ShieldCheck size={15} />
          Demo environment · Synthetic data only · Findings require professional verification
        </div>
      </div>
    </div>
  )
}
