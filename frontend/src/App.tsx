import { useEffect, useState } from 'react'
import {
  Activity,
  ShieldCheck,
  FileSearch,
  Users,
  LayoutDashboard,
  Bell,
  Search,
  CalendarDays,
  AlertTriangle,
  FileText,
  ChevronRight,
  HeartPulse,
  Upload,
  Settings,
  CheckCircle2,
  RefreshCw,
  LogOut,
} from 'lucide-react'

import type { ReactNode } from 'react'
import { api, ApiError, getToken, setToken } from './api'
import type {
  AnalyticsSummary,
  AuditEvent,
  DocumentItem,
  Finding,
  FindingStatus,
  Patient,
  Role,
  User,
  Visit,
} from './api'
import AuthScreen from './AuthScreen'
import './App.css'

// ---------------------------------------------------------------- constants

const NAV: Record<Role, string[]> = {
  doctor: ['Dashboard', 'Patients', 'Upload Records', 'Findings Review', 'Analytics'],
  records_staff: ['Dashboard', 'Patients', 'Upload Records', 'Findings Review', 'Document Library'],
  patient: ['Dashboard', 'My Records', 'Visit Timeline', 'Findings', 'My Profile'],
  admin: ['Dashboard', 'Users', 'Audit Log', 'System Settings'],
}

const NAV_ICONS = [LayoutDashboard, Users, FileText, FileSearch, Activity, Settings]

const VISIT_COLORS: Record<string, string> = {
  Consultation: '#2878e8',
  Investigation: '#a45be5',
  Medication: '#f59e0b',
  Emergency: '#ef4444',
  'Follow-up': '#10b981',
  'Record review': '#64748b',
}
const visitColor = (type: string) => VISIT_COLORS[type] ?? '#64748b'

const CATEGORY_COLORS: Record<string, string> = {
  allergy: '#ef4444',
  medication: '#f59e0b',
  diagnosis: '#a45be5',
  demographic: '#2878e8',
}
const categoryColor = (cat: string) => CATEGORY_COLORS[cat] ?? '#64748b'

const STATUS_LABELS: Record<FindingStatus, string> = {
  needs_review: 'Needs Review',
  verified: 'Verified',
  dismissed: 'Dismissed',
  escalated: 'Escalated',
}

const EXTRACTION_LABELS: Record<string, string> = {
  pending: 'Extraction pending',
  succeeded: 'Text extracted',
  no_text_found: 'No text found',
  ocr_unavailable: 'OCR unavailable',
  failed: 'Extraction failed',
}

const patientTabs = [
  'Overview',
  'Visit Timeline',
  'Medical Records',
  'Findings',
  'Allergies & Medications',
]

// ------------------------------------------------------------------ helpers

function messageOf(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Unexpected error. Please try again.'
}

function fmtDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function fmtShortDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ageFromDob(dob: string | null): string {
  if (!dob) return '—'
  const years = Math.floor((Date.now() - new Date(`${dob}T00:00:00`).getTime()) / (365.25 * 24 * 3600 * 1000))
  return `${years} years`
}

// --------------------------------------------------------------------- app

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)

  const [page, setPage] = useState('Dashboard')
  const [search, setSearch] = useState('')

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
  const [patients, setPatients] = useState<Patient[]>([])
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null)
  const [visits, setVisits] = useState<Visit[]>([])
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [patientFindings, setPatientFindings] = useState<Finding[]>([])
  const [allFindings, setAllFindings] = useState<Finding[] | null>(null)
  const [users, setUsers] = useState<User[] | null>(null)
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [auditPage, setAuditPage] = useState(1)

  const [selectedVisit, setSelectedVisit] = useState(0)
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [reviewReason, setReviewReason] = useState('')

  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadType, setUploadType] = useState('consultation')
  const [uploadDate, setUploadDate] = useState('')
  const [uploading, setUploading] = useState(false)

  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const role: Role = user?.role ?? 'doctor'
  const canUpload = role === 'doctor' || role === 'records_staff'
  const canReview = role === 'doctor'

  const recordsPage = role === 'patient' ? 'My Records' : 'Document Library'
  const findingsPage = role === 'patient' ? 'Findings' : 'Findings Review'

  const currentPatient =
    patients.find((p) => p.id === selectedPatientId) ?? null

  const filteredPatients = patients.filter((patient) =>
    `${patient.full_name} ${patient.mrn}`.toLowerCase().includes(search.toLowerCase()),
  )

  function go(next: string) {
    setPage(next)
    setError('')
    setNotice('')
  }

  function fail(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      setToken(null)
      setUser(null)
    }
    setError(messageOf(err))
  }

  function signOut() {
    api.logout()
    setUser(null)
    setPage('Dashboard')
    setSummary(null)
    setPatients([])
    setVisits([])
    setDocuments([])
    setPatientFindings([])
    setAllFindings(null)
    setUsers(null)
    setAuditEvents([])
    setError('')
    setNotice('')
  }

  // ---- restore session from a stored token -----------------------------
  useEffect(() => {
    if (!getToken()) {
      setBooting(false)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setBooting(false))
  }, [])

  // ---- load workspace data for the signed-in user ----------------------
  useEffect(() => {
    if (!user) return
    setPage('Dashboard')
    setSearch('')
    setNotice('')
    setError('')
    let cancelled = false
    ;(async () => {
      try {
        const s = await api.analyticsSummary()
        if (cancelled) return
        setSummary(s)
        if (user.role === 'admin') {
          setUsers(await api.adminListUsers())
          return
        }
        const list = await api.listPatients({ page_size: 100 })
        if (cancelled) return
        setPatients(list.items)
        setSelectedPatientId(user.patient_id ?? list.items[0]?.id ?? null)
      } catch (err) {
        if (!cancelled) fail(err)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  // ---- load visits / documents / findings for the selected patient -----
  useEffect(() => {
    if (!selectedPatientId) return
    let cancelled = false
    setSelectedVisit(0)
    ;(async () => {
      try {
        const [v, d, f] = await Promise.all([
          api.listVisits(selectedPatientId),
          api.listDocuments(selectedPatientId),
          api.listFindings(selectedPatientId),
        ])
        if (cancelled) return
        setVisits(v)
        setDocuments(d)
        setPatientFindings(f)
      } catch (err) {
        if (!cancelled) fail(err)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPatientId])

  // ---- findings across every visible patient (lazy) --------------------
  useEffect(() => {
    if (!user || user.role === 'admin') return
    if (page !== findingsPage && page !== 'Findings Review' && page !== 'Findings') return
    if (allFindings !== null) return
    let cancelled = false
    ;(async () => {
      try {
        const perPatient = await Promise.all(
          patients.map((p) => api.listFindings(p.id).catch(() => [] as Finding[])),
        )
        if (!cancelled) setAllFindings(perPatient.flat())
      } catch (err) {
        if (!cancelled) fail(err)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, patients, allFindings, user, findingsPage])

  // ---- audit log (admin) ------------------------------------------------
  useEffect(() => {
    if (user?.role !== 'admin' || page !== 'Audit Log') return
    let cancelled = false
    api
      .adminListAudit(auditPage)
      .then((events) => {
        if (cancelled) return
        setAuditEvents((prev) => (auditPage === 1 ? events : [...prev, ...events]))
      })
      .catch(fail)
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, page, auditPage])

  // ---- actions ----------------------------------------------------------

  function openPatient(patientId: number) {
    setSelectedPatientId(patientId)
    setSelectedVisit(0)
    go('Visit Timeline')
  }

  function openPatientTab(tab: string) {
    if (tab === 'Overview') go('Dashboard')
    else if (tab === 'Visit Timeline') go('Visit Timeline')
    else if (tab === 'Medical Records') go(recordsPage)
    else go(findingsPage)
  }

  async function refreshSummary() {
    try {
      setSummary(await api.analyticsSummary())
    } catch (err) {
      fail(err)
    }
  }

  async function submitReview(findingId: number, decision: 'verified' | 'dismissed' | 'escalated') {
    const reason = reviewReason.trim()
    if (reason.length < 5) {
      setError('A review reason of at least 5 characters is required.')
      return
    }
    try {
      const updated = await api.reviewFinding(findingId, decision, reason)
      setAllFindings((prev) => prev?.map((f) => (f.id === updated.id ? updated : f)) ?? prev)
      setPatientFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)))
      setReviewingId(null)
      setReviewReason('')
      setError('')
      setNotice(`Finding ${STATUS_LABELS[decision].toLowerCase()} — recorded in the audit log.`)
      refreshSummary()
    } catch (err) {
      fail(err)
    }
  }

  async function runAnalysis() {
    if (!selectedPatientId) return
    try {
      const found = await api.analyzePatient(selectedPatientId)
      setPatientFindings(found)
      setAllFindings(null) // force a reload of the cross-patient list
      setError('')
      setNotice(`Analysis complete — ${found.length} potential finding(s) for this patient.`)
      refreshSummary()
    } catch (err) {
      fail(err)
    }
  }

  async function uploadDocument() {
    if (!selectedPatientId || !uploadFile) return
    setUploading(true)
    try {
      const doc = await api.uploadDocument(
        selectedPatientId,
        uploadFile,
        uploadType,
        uploadDate || null,
      )
      const extraction = EXTRACTION_LABELS[doc.extraction_status] ?? doc.extraction_status
      setError('')
      setNotice(
        doc.processing_status === 'completed'
          ? `Uploaded “${doc.original_filename}” — ${extraction}.`
          : `Uploaded “${doc.original_filename}” — ${extraction}: ${doc.extraction_error ?? 'manual review needed'}.`,
      )
      setUploadFile(null)
      setUploadDate('')
      setDocuments(await api.listDocuments(selectedPatientId))
      setPatientFindings(await api.listFindings(selectedPatientId))
      setAllFindings(null)
      refreshSummary()
    } catch (err) {
      fail(err)
    } finally {
      setUploading(false)
    }
  }

  async function toggleUserStatus(target: User) {
    try {
      const updated = await api.adminUpdateUser(target.id, {
        status: target.status === 'active' ? 'inactive' : 'active',
      })
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev)
      setNotice(`Account “${updated.username}” is now ${updated.status}.`)
      setError('')
    } catch (err) {
      fail(err)
    }
  }

  async function changeUserRole(target: User, nextRole: Role) {
    try {
      const updated = await api.adminUpdateUser(target.id, { role: nextRole })
      setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev)
      setNotice(`Role of “${updated.username}” changed to ${updated.role}.`)
      setError('')
    } catch (err) {
      fail(err)
    }
  }

  // ---- gate -------------------------------------------------------------

  if (booting) {
    return <div className="loading-block">Restoring your session…</div>
  }
  if (!user) {
    return <AuthScreen onAuthenticated={setUser} />
  }

  const nav = NAV[role]
  const today = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })

  // stats -----------------------------------------------------------------
  const stats: { icon: ReactNode; value: string; label: string; color: string }[] =
    role === 'patient'
      ? [
          { icon: <Users />, value: String(currentPatient?.visit_count ?? '…'), label: 'Total Visits', color: 'blue' },
          { icon: <FileSearch />, value: String(currentPatient?.document_count ?? '…'), label: 'Documents', color: 'red' },
          { icon: <AlertTriangle />, value: String(currentPatient?.open_findings ?? '…'), label: 'Potential Findings', color: 'orange' },
          { icon: <CheckCircle2 />, value: String(patientFindings.filter((f) => f.status !== 'needs_review').length), label: 'Reviewed Findings', color: 'green' },
        ]
      : role === 'admin'
        ? [
            { icon: <Users />, value: String(summary?.patient_count ?? '…'), label: 'Total Patients', color: 'blue' },
            { icon: <Users />, value: String(summary?.user_count ?? '…'), label: 'User Accounts', color: 'green' },
            { icon: <Bell />, value: String(summary?.pending_users ?? '…'), label: 'Pending Users', color: 'orange' },
            { icon: <AlertTriangle />, value: String(summary?.finding_count ?? '…'), label: 'Potential Findings', color: 'red' },
          ]
        : [
            { icon: <Users />, value: String(summary?.patient_count ?? '…'), label: 'Total Patients', color: 'blue' },
            { icon: <FileSearch />, value: String(summary?.findings_needs_review ?? '…'), label: 'Pending Reviews', color: 'red' },
            { icon: <AlertTriangle />, value: String(summary?.finding_count ?? '…'), label: 'Potential Findings', color: 'orange' },
            { icon: <FileText />, value: String(summary?.document_count ?? '…'), label: 'Documents', color: 'green' },
          ]

  const categoryCounts: Record<string, number> =
    role === 'patient'
      ? patientFindings.reduce<Record<string, number>>((acc, f) => {
          acc[f.category] = (acc[f.category] ?? 0) + 1
          return acc
        }, {})
      : (summary?.findings_by_category ?? {})
  const categories = ['allergy', 'medication', 'diagnosis', 'demographic']
  const maxCategory = Math.max(1, ...categories.map((c) => categoryCounts[c] ?? 0))

  const findingsShown = allFindings ?? []

  const visit = visits.length ? visits[Math.min(selectedVisit, visits.length - 1)] : null

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">
            <HeartPulse size={23} />
          </span>
          <span>
            MedCheck <b>AI</b>
          </span>
        </div>

        <div className="nav-label">WORKSPACE</div>

        {nav.map((item, index) => {
          const Icon = NAV_ICONS[index % NAV_ICONS.length]
          return (
            <button
              key={item}
              className={`nav-item ${page === item ? 'active' : ''}`}
              onClick={() => go(item)}
            >
              <Icon size={17} />
              {item}
            </button>
          )
        })}

        <div className="sidebar-bottom">
          <div className="nav-label">SIGNED IN</div>

          <div className="profile-mini">
            <div className="avatar">{user.full_name[0] ?? 'U'}</div>
            <div>
              <b>{user.full_name}</b>
              <small>
                {user.username} · {role.replace('_', ' ')}
              </small>
            </div>
          </div>

          <button className="signout-button" onClick={signOut}>
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} /> <b>{page}</b>
          </div>

          <div className="top-actions">
            {(role === 'doctor' || role === 'records_staff' || role === 'patient') && (
              <div className="search-box">
                <Search size={16} />
                <input
                  aria-label="Search patients"
                  placeholder="Search patients..."
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
            )}
            <button className="icon-button" aria-label="Notifications">
              <Bell size={19} />
            </button>
            <div className="avatar blue">{user.full_name[0] ?? 'U'}</div>
          </div>
        </header>

        <div className="content">
          {error && <div className="error-box">{error}</div>}
          {notice && (
            <div className="notice">
              <CheckCircle2 size={17} />
              {notice}
            </div>
          )}

          <div className="welcome-row">
            <div>
              <div className="eyebrow">MEDICAL INTELLIGENCE PLATFORM</div>
              <h1>
                {role === 'patient'
                  ? `Welcome, ${user.full_name}`
                  : role === 'admin'
                    ? 'System overview'
                    : role === 'records_staff'
                      ? 'Records workspace'
                      : `Welcome, ${user.full_name}`}
              </h1>
              <p>
                {role === 'patient'
                  ? 'View your medical history and records.'
                  : 'Here is your overview for today.'}
              </p>
            </div>
            <div className="date-pill">
              <CalendarDays size={16} /> {today}
            </div>
          </div>

          {/* ---------------------------------------------------- dashboard */}
          {page === 'Dashboard' && (
            <>
              <section className="stats-grid">
                {stats.map((stat) => (
                  <Stat key={stat.label} {...stat} />
                ))}
              </section>

              <section className="dashboard-grid">
                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>{role === 'patient' ? 'Your Recent Visits' : 'Recent Patients'}</h2>
                      <p>Latest activity in your workspace</p>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => go(role === 'patient' ? 'Visit Timeline' : 'Patients')}
                    >
                      View all <ChevronRight size={14} />
                    </button>
                  </div>

                  {role === 'admin'
                    ? (users ?? []).slice(0, 5).map((u) => (
                        <div className="patient-row" key={u.id}>
                          <span className="patient-avatar">{u.full_name[0]}</span>
                          <span className="patient-info">
                            <b>{u.full_name}</b>
                            <small>
                              {u.username} · {u.role.replace('_', ' ')}
                            </small>
                          </span>
                          <span
                            className={`finding-count ${u.status === 'active' ? 'ok' : u.status === 'pending' ? 'warn' : 'bad'}`}
                          >
                            {u.status}
                          </span>
                        </div>
                      ))
                    : role === 'patient'
                      ? visits
                          .slice()
                          .reverse()
                          .slice(0, 4)
                          .map((v) => (
                            <button
                              className="patient-row patient-click"
                              key={v.id}
                              onClick={() => go('Visit Timeline')}
                            >
                              <span
                                className="patient-avatar"
                                style={{
                                  background: `${visitColor(v.visit_type)}20`,
                                  color: visitColor(v.visit_type),
                                }}
                              >
                                <CalendarDays size={16} />
                              </span>
                              <span className="patient-info">
                                <b>{v.visit_type}</b>
                                <small>
                                  {fmtShortDate(v.visit_date)} · {v.department}
                                </small>
                              </span>
                              <ChevronRight size={16} className="muted" />
                            </button>
                          ))
                      : filteredPatients.slice(0, 5).map((patient) => (
                          <button
                            className="patient-row patient-click"
                            key={patient.id}
                            onClick={() => openPatient(patient.id)}
                          >
                            <span className="patient-avatar">{patient.full_name[0]}</span>
                            <span className="patient-info">
                              <b>{patient.full_name}</b>
                              <small>
                                {patient.mrn} · {ageFromDob(patient.date_of_birth)}
                              </small>
                            </span>
                            <span
                              className={`finding-count ${patient.open_findings ? 'has-findings' : ''}`}
                            >
                              {patient.open_findings} findings
                            </span>
                            <ChevronRight size={16} className="muted" />
                          </button>
                        ))}
                </div>

                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Findings by category</h2>
                      <p>Potential inconsistencies to review</p>
                    </div>
                  </div>

                  <div className="finding-bars">
                    {categories.map((cat) => {
                      const count = categoryCounts[cat] ?? 0
                      const color = categoryColor(cat)
                      return (
                        <div className="finding-bar-row" key={cat}>
                          <span className="dot" style={{ background: color }} />
                          <span style={{ textTransform: 'capitalize' }}>{cat}</span>
                          <div className="bar-track">
                            <div
                              className="bar-fill"
                              style={{ width: `${(count / maxCategory) * 100}%`, background: color }}
                            />
                          </div>
                          <b>{count}</b>
                        </div>
                      )
                    })}
                  </div>

                  <div className="notice">
                    <ShieldCheck size={17} />
                    All findings require professional verification.
                  </div>
                </div>
              </section>
            </>
          )}

          {/* ----------------------------------------------------- patients */}
          {page === 'Patients' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Patient Directory</h2>
                  <p>Select a patient to explore their medical history.</p>
                </div>
                <span className="status-badge">{filteredPatients.length} patients</span>
              </div>

              {filteredPatients.map((patient) => (
                <div className="patient-row" key={patient.id}>
                  <span className="patient-avatar">{patient.full_name[0]}</span>
                  <span className="patient-info">
                    <b>{patient.full_name}</b>
                    <small>
                      {patient.mrn} · {ageFromDob(patient.date_of_birth)} ·{' '}
                      {patient.sex ?? 'Unspecified'} · {patient.document_count} documents
                    </small>
                  </span>
                  <span
                    className={`finding-count ${patient.open_findings ? 'has-findings' : ''}`}
                  >
                    {patient.open_findings} findings
                  </span>
                  <button className="outline-button" onClick={() => openPatient(patient.id)}>
                    View history
                  </button>
                </div>
              ))}
              {filteredPatients.length === 0 && <p>No patients match your search.</p>}
            </section>
          )}

          {/* ------------------------------------------------ visit timeline */}
          {page === 'Visit Timeline' && (
            <>
              <section className="panel patient-header">
                {currentPatient ? (
                  <>
                    <div className="patient-header-main">
                      <div className="large-avatar">{currentPatient.full_name[0]}</div>
                      <div>
                        <div className="patient-name-line">
                          <h2>{currentPatient.full_name}</h2>
                          <span className="patient-code">{currentPatient.mrn}</span>
                        </div>
                        <p>
                          {ageFromDob(currentPatient.date_of_birth)} ·{' '}
                          {currentPatient.sex ?? 'Unspecified'} ·{' '}
                          {currentPatient.is_synthetic ? 'Synthetic demo patient' : 'Patient record'}
                        </p>
                      </div>
                    </div>

                    <div className="patient-tabs">
                      {patientTabs.map((tab) => (
                        <button
                          key={tab}
                          className={`patient-tab ${tab === 'Visit Timeline' ? 'selected' : ''}`}
                          onClick={() => openPatientTab(tab)}
                        >
                          {tab}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="patient-header-main">
                    <p>No patient selected. Choose one from the Patients page.</p>
                  </div>
                )}
              </section>

              <section className="panel timeline-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Patient Visit Timeline</h2>
                    <p>Chronological overview of recorded hospital visits</p>
                  </div>
                  <span className="status-badge">{visits.length} visits</span>
                </div>

                {visits.length === 0 && <p>No visits recorded for this patient.</p>}

                {visit && (
                  <>
                    <div className="legend">
                      {Array.from(new Set(visits.map((v) => v.visit_type))).map((type) => (
                        <span key={type}>
                          <i style={{ background: visitColor(type) }} />
                          {type}
                        </span>
                      ))}
                    </div>

                    <div className="timeline">
                      {visits.map((v, index) => (
                        <button
                          key={v.id}
                          onClick={() => setSelectedVisit(index)}
                          className={`timeline-point ${selectedVisit === index ? 'chosen' : ''}`}
                        >
                          <span className="point" style={{ background: visitColor(v.visit_type) }} />
                          <b>{fmtShortDate(v.visit_date)}</b>
                          <small>{v.visit_type}</small>
                        </button>
                      ))}
                    </div>

                    <div className="visit-detail">
                      <div className="visit-title">
                        <span
                          className="point"
                          style={{ background: visitColor(visit.visit_type) }}
                        />
                        <div>
                          <h3>{fmtDate(visit.visit_date)}</h3>
                          <p>{visit.department}</p>
                        </div>
                        <span className="status-badge">{visit.visit_type}</span>
                      </div>

                      <div className="detail-grid">
                        <Detail label="Reason for visit" value={visit.reason} />
                        <Detail label="Purpose" value={visit.purpose ?? 'Not recorded'} />
                        <Detail label="Recorded outcome" value={visit.outcome ?? 'Not recorded'} />
                      </div>
                    </div>
                  </>
                )}

                <div className="timeline-disclaimer">
                  <ShieldCheck size={17} />
                  Clinical findings require verification against source documents.
                </div>
              </section>
            </>
          )}

          {/* ------------------------------------------------------- upload */}
          {page === 'Upload Records' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Upload Medical Document</h2>
                  <p>
                    Text extraction and contradiction analysis run automatically after upload.
                  </p>
                </div>
                <Upload size={22} />
              </div>

              <div className="upload-form">
                <label className="form-field">
                  Patient
                  <select
                    className="form-input"
                    value={selectedPatientId ?? ''}
                    onChange={(event) => setSelectedPatientId(Number(event.target.value))}
                  >
                    {patients.map((patient) => (
                      <option key={patient.id} value={patient.id}>
                        {patient.full_name} · {patient.mrn}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="form-field">
                  Document type
                  <select
                    className="form-input"
                    value={uploadType}
                    onChange={(event) => setUploadType(event.target.value)}
                  >
                    <option value="consultation">Consultation</option>
                    <option value="investigation">Investigation</option>
                    <option value="medication">Medication</option>
                    <option value="emergency">Emergency</option>
                    <option value="discharge">Discharge</option>
                    <option value="other">Other</option>
                  </select>
                </label>

                <label className="form-field">
                  Document date
                  <input
                    className="form-input"
                    type="date"
                    value={uploadDate}
                    onChange={(event) => setUploadDate(event.target.value)}
                  />
                </label>
              </div>

              <label className="upload-zone">
                <FileText size={36} />
                <b>{uploadFile ? uploadFile.name : 'Choose a medical document'}</b>
                <span>PDF, PNG, or JPG · max 10 MB</span>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                />
              </label>

              {uploadFile && (
                <button
                  className="btn-primary upload-submit"
                  onClick={uploadDocument}
                  disabled={uploading || !selectedPatientId}
                >
                  {uploading ? 'Uploading and analyzing…' : 'Upload and analyze'}
                </button>
              )}

              <div className="notice">
                <ShieldCheck size={17} />
                Do not upload real patient information to this demo.
              </div>
            </section>
          )}

          {/* ---------------------------------------------------- findings */}
          {(page === 'Findings Review' || page === 'Findings') && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Potential Contradictions</h2>
                  <p>
                    Possible inconsistencies that must be checked against original evidence.
                  </p>
                </div>
                <div className="heading-actions">
                  {canUpload && currentPatient && (
                    <button className="outline-button" onClick={runAnalysis}>
                      <RefreshCw size={13} /> Re-run analysis
                    </button>
                  )}
                  <span className="status-badge">{findingsShown.length} findings</span>
                </div>
              </div>

              {allFindings === null && <p>Loading findings…</p>}

              {allFindings !== null && findingsShown.length === 0 && (
                <p>No potential contradictions recorded. Upload documents or run analysis.</p>
              )}

              {findingsShown.map((finding) => {
                const color = categoryColor(finding.category)
                const patientName =
                  patients.find((p) => p.id === finding.patient_id)?.full_name ??
                  `Patient #${finding.patient_id}`
                return (
                  <div className="finding-card" key={finding.id}>
                    <span
                      className="finding-icon"
                      style={{ color, background: `${color}18` }}
                    >
                      <AlertTriangle size={20} />
                    </span>

                    <div className="finding-body">
                      <span className="category-tag" style={{ color }}>
                        {finding.category.toUpperCase()} · {finding.severity} severity
                      </span>
                      <h3>{finding.title}</h3>
                      <p>{finding.description}</p>

                      <div className="finding-sources">
                        {finding.sources.map((source) => (
                          <div className="source-line" key={source.id}>
                            <b>{source.document_filename ?? `Document #${source.document_id}`}</b>
                            {source.document_date ? <span> · {fmtDate(source.document_date)}</span> : null}
                            <q>{source.excerpt}</q>
                          </div>
                        ))}
                      </div>

                      <small>
                        Patient: {patientName} · Status: {STATUS_LABELS[finding.status]} · Verify
                        original evidence
                      </small>
                    </div>

                    {canReview && (
                      <button
                        className="outline-button"
                        onClick={() => {
                          setReviewingId(reviewingId === finding.id ? null : finding.id)
                          setReviewReason('')
                          setError('')
                        }}
                      >
                        {reviewingId === finding.id ? 'Cancel' : 'Record review'}
                      </button>
                    )}

                    {reviewingId === finding.id && (
                      <div className="review-panel">
                        <label className="form-field">
                          Review reason (required, stored in the audit log)
                          <textarea
                            className="form-input"
                            rows={2}
                            value={reviewReason}
                            onChange={(event) => setReviewReason(event.target.value)}
                            placeholder="e.g. Checked against the discharge summary — discrepancy confirmed."
                          />
                        </label>
                        <div className="review-actions">
                          <button
                            className="outline-button good"
                            onClick={() => submitReview(finding.id, 'verified')}
                          >
                            Verify
                          </button>
                          <button
                            className="outline-button"
                            onClick={() => submitReview(finding.id, 'dismissed')}
                          >
                            Dismiss
                          </button>
                          <button
                            className="outline-button warn"
                            onClick={() => submitReview(finding.id, 'escalated')}
                          >
                            Escalate
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}

              <div className="notice">
                <ShieldCheck size={17} />
                A review records a decision only — source medical documents are never modified.
              </div>
            </section>
          )}

          {/* -------------------------------------------------- documents */}
          {(page === 'Document Library' || page === 'My Records') && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>{page}</h2>
                  <p>
                    {currentPatient
                      ? `Documents on file for ${currentPatient.full_name} (${currentPatient.mrn}).`
                      : 'Medical record library.'}
                  </p>
                </div>
                {canUpload && (
                  <button className="outline-button" onClick={() => go('Upload Records')}>
                    <Upload size={14} /> Upload record
                  </button>
                )}
              </div>

              {documents.map((doc) => {
                const extraction = EXTRACTION_LABELS[doc.extraction_status] ?? doc.extraction_status
                const badgeClass =
                  doc.processing_status === 'completed'
                    ? 'ok'
                    : doc.processing_status === 'failed'
                      ? 'bad'
                      : 'warn'
                return (
                  <div className="patient-row" key={doc.id}>
                    <span className="patient-avatar">
                      <FileText size={17} />
                    </span>
                    <span className="patient-info">
                      <b>{doc.original_filename}</b>
                      <small>
                        {doc.document_type} · {fmtDate(doc.document_date ?? doc.uploaded_at)} ·{' '}
                        {extraction}
                        {doc.uploaded_by_username ? ` · uploaded by ${doc.uploaded_by_username}` : ''}
                      </small>
                    </span>
                    <span className={`finding-count ${badgeClass}`}>
                      {doc.processing_status}
                    </span>
                  </div>
                )
              })}
              {documents.length === 0 && <p>No documents on file for this patient yet.</p>}
            </section>
          )}

          {/* -------------------------------------------------- analytics */}
          {page === 'Analytics' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Analytics overview</h2>
                  <p>Aggregates computed live from the MedCheck database.</p>
                </div>
                <span className="status-badge">Live data</span>
              </div>

              <div className="stats-grid">
                <Stat icon={<FileSearch />} value={String(summary?.finding_count ?? '…')} label="Total findings" color="blue" />
                <Stat icon={<Users />} value={String(summary?.patient_count ?? '…')} label="Total patients" color="green" />
                <Stat icon={<AlertTriangle />} value={String(summary?.findings_needs_review ?? '…')} label="Needs review" color="orange" />
                <Stat icon={<CheckCircle2 />} value={String(summary?.findings_verified ?? '…')} label="Verified" color="red" />
              </div>

              <div className="finding-bars">
                {categories.map((cat) => {
                  const count = categoryCounts[cat] ?? 0
                  const color = categoryColor(cat)
                  return (
                    <div className="finding-bar-row" key={cat}>
                      <span className="dot" style={{ background: color }} />
                      <span style={{ textTransform: 'capitalize' }}>{cat}</span>
                      <div className="bar-track">
                        <div
                          className="bar-fill"
                          style={{ width: `${(count / maxCategory) * 100}%`, background: color }}
                        />
                      </div>
                      <b>{count}</b>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {/* ------------------------------------------------------ users */}
          {page === 'Users' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>User management</h2>
                  <p>Activate, suspend, or change the role of platform accounts.</p>
                </div>
                <span className="status-badge">{users?.length ?? 0} accounts</span>
              </div>

              {(users ?? []).map((u) => (
                <div className="patient-row" key={u.id}>
                  <span className="patient-avatar">{u.full_name[0]}</span>
                  <span className="patient-info">
                    <b>{u.full_name}</b>
                    <small>
                      {u.username} · {u.email}
                    </small>
                  </span>
                  <select
                    className="form-input role-select"
                    aria-label={`Role of ${u.username}`}
                    value={u.role}
                    onChange={(event) => changeUserRole(u, event.target.value as Role)}
                  >
                    <option value="doctor">doctor</option>
                    <option value="records_staff">records_staff</option>
                    <option value="patient">patient</option>
                    <option value="admin">admin</option>
                  </select>
                  <span
                    className={`finding-count ${u.status === 'active' ? 'ok' : u.status === 'pending' ? 'warn' : 'bad'}`}
                  >
                    {u.status}
                  </span>
                  <button className="outline-button" onClick={() => toggleUserStatus(u)}>
                    {u.status === 'active' ? 'Suspend' : 'Activate'}
                  </button>
                </div>
              ))}
              {users === null && <p>Loading accounts…</p>}
            </section>
          )}

          {/* --------------------------------------------------- audit log */}
          {page === 'Audit Log' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Audit log</h2>
                  <p>Every authentication, review, upload, and admin action is recorded.</p>
                </div>
                <span className="status-badge">{auditEvents.length} events</span>
              </div>

              {auditEvents.map((event) => (
                <div className="patient-row" key={event.id}>
                  <span className="patient-avatar">
                    <ShieldCheck size={16} />
                  </span>
                  <span className="patient-info">
                    <b>{event.action}</b>
                    <small>
                      {event.actor_username ?? 'system'} · {fmtDateTime(event.created_at)}
                      {event.detail ? ` · ${event.detail}` : ''}
                    </small>
                  </span>
                </div>
              ))}
              {auditEvents.length === 0 && <p>No audit events recorded yet.</p>}

              <button
                className="outline-button load-more"
                onClick={() => setAuditPage((p) => p + 1)}
              >
                Load older events
              </button>
            </section>
          )}

          {/* -------------------------------------------------- settings */}
          {page === 'System Settings' && (
            <section className="panel">
              <h2>System settings</h2>
              <p>
                Configuration controls are intentionally minimal in this demo build. All clinical
                data is synthetic.
              </p>
              <div className="notice">
                <ShieldCheck size={17} />
                Backend version:{' '}
                {summary
                  ? `${summary.user_count} users · ${summary.document_count} documents · ${summary.failed_documents} failed extractions`
                  : 'loading…'}
              </div>
            </section>
          )}

          {/* --------------------------------------------------- profile */}
          {page === 'My Profile' && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>My profile</h2>
                  <p>Your account as registered with MedCheck AI.</p>
                </div>
                <span className="status-badge">{user.status}</span>
              </div>

              <div className="detail-grid">
                <Detail label="Full name" value={user.full_name} />
                <Detail label="Username" value={user.username} />
                <Detail label="Email" value={user.email} />
                <Detail label="Role" value={user.role.replace('_', ' ')} />
                <Detail label="Account created" value={fmtDate(user.created_at)} />
                <Detail
                  label="Linked record"
                  value={currentPatient ? `${currentPatient.full_name} · ${currentPatient.mrn}` : 'None'}
                />
              </div>

              <button className="outline-button" onClick={signOut}>
                <LogOut size={14} /> Sign out
              </button>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}

function Stat({
  icon,
  value,
  label,
  color,
}: {
  icon: ReactNode
  value: string
  label: string
  color: string
}) {
  return (
    <div className="stat-card">
      <span className={`stat-icon ${color}`}>{icon}</span>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-item">
      <span>{label}</span>
      <b>{value}</b>
    </div>
  )
}
