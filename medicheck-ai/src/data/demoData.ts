// All data is fictional and synthetic. Demo only.
export type Status = 'Needs Review' | 'Reviewed'
export type Category = 'Allergy' | 'Medication' | 'Diagnosis'
export interface Doc { label: string; date: string; text: string }
export interface Finding { id: string; patient: string; cat: Category; summary: string; status: Status; a: Doc; b: Doc }
export interface Patient { id: string; name: string; hospital: string; docs: number; updated: string }

export const patients: Patient[] = [
  { id: 'SYNTH-1001', name: 'Synthetic Patient A', hospital: 'Meridian Care Hospital', docs: 6, updated: '3 Oct 2026' },
  { id: 'SYNTH-1002', name: 'Synthetic Patient B', hospital: 'Bluehaven Medical Centre', docs: 4, updated: '2 Oct 2026' },
  { id: 'SYNTH-2002', name: 'Synthetic Patient C', hospital: 'NovaLife Hospital', docs: 5, updated: '5 Oct 2026' },
]

export const initialFindings: Finding[] = [
  { id: 'F-001', patient: 'SYNTH-1001', cat: 'Allergy', summary: 'Different allergy statements across two records.', status: 'Needs Review',
    a: { label: 'Document A — Admission Note', date: '1 Oct 2026', text: 'Penicillin allergy with hives.' },
    b: { label: 'Document B — Discharge Summary', date: '3 Oct 2026', text: 'No known drug allergies.' } },
  { id: 'F-002', patient: 'SYNTH-1001', cat: 'Medication', summary: 'Metformin dose and frequency differ.', status: 'Needs Review',
    a: { label: 'Document A — Prescription', date: '1 Oct 2026', text: 'Metformin 500 mg twice daily.' },
    b: { label: 'Document B — Discharge Summary', date: '3 Oct 2026', text: 'Metformin 1000 mg once daily.' } },
  { id: 'F-003', patient: 'SYNTH-1002', cat: 'Diagnosis', summary: 'Hypertension listed as both active and resolved.', status: 'Reviewed',
    a: { label: 'Document A — Clinic Letter', date: '28 Sep 2026', text: 'Hypertension, active.' },
    b: { label: 'Document B — Lab Report Note', date: '2 Oct 2026', text: 'Hypertension, resolved.' } },
  { id: 'F-004', patient: 'SYNTH-2002', cat: 'Medication', summary: 'Statin present in one record, absent in another.', status: 'Needs Review',
    a: { label: 'Document A — Medication List', date: '30 Sep 2026', text: 'Atorvastatin 20 mg nightly.' },
    b: { label: 'Document B — Discharge Medications', date: '5 Oct 2026', text: 'No statin listed.' } },
]

export const suggestions = ['Explain the allergy conflict.', 'Compare the medication entries.', "Summarize this patient's findings.", 'What should a reviewer verify?']
export const fallback = 'I can demonstrate explanations for the sample findings available in this frontend prototype. This demo is not connected to a live medical AI service.'
