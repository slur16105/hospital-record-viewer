'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './RecordCreateClient.module.css'

interface DoctorProfile {
  doctor_id: string
  department_id: string
  department_name: string
  name: string
}

interface Room {
  id: string
  room_number: string
  department_id: string
  is_active: boolean
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

export default function RecordCreateClient({ patientId }: { patientId: string }) {
  const router = useRouter()

  const [visitedAt, setVisitedAt] = useState('')
  const [diagnosis, setDiagnosis] = useState('')
  const [chiefComplaint, setChiefComplaint] = useState('')
  const [prescription, setPrescription] = useState('')
  const [roomId, setRoomId] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [serverError, setServerError] = useState('')

  const { data: profile } = useQuery<DoctorProfile>({
    queryKey: ['doctor-profile'],
    queryFn: async () => {
      const res = await fetch('/api/doctor/profile')
      if (!res.ok) throw new Error('의사 정보 조회 실패')
      return res.json()
    },
  })

  const { data: allRooms = [] } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: async () => {
      const res = await fetch('/api/rooms')
      if (!res.ok) return []
      return res.json()
    },
  })

  const departmentRooms = allRooms.filter(
    (r) => r.department_id === profile?.department_id && r.is_active
  )

  const createMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const res = await fetch('/api/doctor/records', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '저장 실패'))
      return data
    },
    onSuccess: (data) => {
      router.push(`/records/${data.id}?patient=${patientId}`)
    },
    onError: (err: Error) => setServerError(err.message),
  })

  function validate(): boolean {
    const errors: Record<string, string> = {}
    if (!visitedAt) errors.visitedAt = '필수 항목입니다'
    if (!diagnosis.trim()) errors.diagnosis = '필수 항목입니다'
    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setServerError('')
    if (!validate()) return

    const payload: Record<string, unknown> = {
      patient_id: patientId,
      visited_at: new Date(visitedAt).toISOString(),
      diagnosis: diagnosis.trim(),
    }
    if (chiefComplaint.trim()) payload.chief_complaint = chiefComplaint.trim()
    if (prescription.trim()) payload.prescription = prescription.trim()
    if (roomId) payload.room_id = roomId

    createMutation.mutate(payload)
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link href={`/patients/${patientId}/records`} className={styles.back}>
          ← 진료기록 목록
        </Link>
        <h1 className={styles.title}>새 진료기록 작성</h1>
      </div>

      {serverError && <p className={styles.error}>{serverError}</p>}

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.fieldGroup}>
          <label className={styles.label}>
            진료일시 <span className={styles.required}>*</span>
          </label>
          <input
            type="datetime-local"
            className={styles.input}
            value={visitedAt}
            onChange={(e) => setVisitedAt(e.target.value)}
          />
          {fieldErrors.visitedAt && (
            <span className={styles.fieldError}>{fieldErrors.visitedAt}</span>
          )}
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.label}>
            진단명 <span className={styles.required}>*</span>
          </label>
          <input
            type="text"
            className={styles.input}
            placeholder="진단명을 입력하세요"
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
          />
          {fieldErrors.diagnosis && (
            <span className={styles.fieldError}>{fieldErrors.diagnosis}</span>
          )}
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.label}>진료실</label>
          <select
            className={styles.select}
            value={roomId}
            onChange={(e) => setRoomId(e.target.value)}
          >
            <option value="">진료실 선택 (선택사항)</option>
            {departmentRooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.room_number}
              </option>
            ))}
          </select>
          {profile && departmentRooms.length === 0 && (
            <span className={styles.fieldError}>
              {profile.department_name} 진료실이 없습니다.
            </span>
          )}
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.label}>주증상</label>
          <textarea
            className={styles.textarea}
            placeholder="주증상을 입력하세요"
            value={chiefComplaint}
            onChange={(e) => setChiefComplaint(e.target.value)}
          />
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.label}>처방 내용</label>
          <textarea
            className={styles.textarea}
            placeholder="처방 내용을 입력하세요"
            value={prescription}
            onChange={(e) => setPrescription(e.target.value)}
          />
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.btnCancel}
            onClick={() => router.back()}
          >
            취소
          </button>
          <button
            type="submit"
            className={styles.btnSubmit}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? '저장 중...' : '저장'}
          </button>
        </div>
      </form>
    </div>
  )
}
