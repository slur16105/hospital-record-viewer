'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import styles from './RecordDetailClient.module.css'

interface DoctorInfo {
  id: string
  name: string
  department: string
}

interface RecordDetail {
  id: string
  patient_name: string | null
  visited_at: string
  diagnosis: string
  chief_complaint: string | null
  prescription: string | null
  room_number: string | null
  is_corrected: boolean
  correction_note: string | null
  corrected_at: string | null
  created_at: string
  doctor: DoctorInfo
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function RecordDetailClient({
  recordId,
  patientId,
  canEdit,
}: {
  recordId: string
  /** 의사 흐름(/patients/[id]/records)에서 넘어온 경우의 목록 복귀 컨텍스트 */
  patientId: string | null
  /** records:update_own 보유 여부 — 본인 작성 여부 최종 판정은 백엔드(403) */
  canEdit: boolean
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [editDiagnosis, setEditDiagnosis] = useState('')
  const [editChiefComplaint, setEditChiefComplaint] = useState('')
  const [editPrescription, setEditPrescription] = useState('')
  const [editCorrectionNote, setEditCorrectionNote] = useState('')
  const [serverError, setServerError] = useState('')

  const { data: record, isLoading, error } = useQuery<RecordDetail>({
    queryKey: ['record-detail', recordId],
    queryFn: async () => {
      const res = await fetch(`/api/doctor/records/${recordId}`)
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('진료기록 조회 실패')
      return res.json()
    },
    retry: false,
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      const res = await fetch(`/api/doctor/records/${recordId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '수정 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record-detail', recordId] })
      if (patientId) queryClient.invalidateQueries({ queryKey: ['patient-records', patientId] })
      setEditing(false)
      setServerError('')
    },
    onError: (err: Error) => setServerError(err.message),
  })

  function startEdit() {
    if (!record) return
    setEditDiagnosis(record.diagnosis)
    setEditChiefComplaint(record.chief_complaint ?? '')
    setEditPrescription(record.prescription ?? '')
    setEditCorrectionNote(record.correction_note ?? '')
    setServerError('')
    setEditing(true)
  }

  function cancelEdit() {
    setEditing(false)
    setServerError('')
  }

  function handleSave() {
    if (!editDiagnosis.trim()) {
      setServerError('진단명은 필수 항목입니다')
      return
    }
    const payload: Record<string, unknown> = { diagnosis: editDiagnosis.trim() }
    if (editChiefComplaint !== (record?.chief_complaint ?? ''))
      payload.chief_complaint = editChiefComplaint || null
    if (editPrescription !== (record?.prescription ?? ''))
      payload.prescription = editPrescription || null
    if (editCorrectionNote !== (record?.correction_note ?? ''))
      payload.correction_note = editCorrectionNote || null
    updateMutation.mutate(payload)
  }

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>
  if ((error as (Error & { status?: number }) | null)?.status === 403)
    return <ForbiddenNotice message="이 진료기록을 볼 수 있는 권한이 없습니다." />
  if (error || !record) return <p className={styles.notFound}>진료기록을 찾을 수 없습니다.</p>

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Link
            href={patientId ? `/patients/${patientId}/records` : '/patients'}
            className={styles.back}
          >
            ← {patientId ? '진료기록 목록' : '담당 환자 목록'}
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 className={styles.title}>진료기록 상세</h1>
            {record.is_corrected && (
              <span className={styles.correctedBadge}>정정됨</span>
            )}
          </div>
        </div>
        {!editing && canEdit && (
          <button className={styles.btnEdit} onClick={startEdit}>
            수정
          </button>
        )}
      </div>

      {serverError && <p className={styles.error}>{serverError}</p>}

      {!editing ? (
        <div className={styles.card}>
          {record.patient_name && (
            <div className={styles.fieldRow}>
              <span className={styles.fieldLabel}>환자명</span>
              <span className={styles.fieldValue}>{record.patient_name}</span>
            </div>
          )}
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>진료일시</span>
            <span className={styles.fieldValue}>{formatDatetime(record.visited_at)}</span>
          </div>
          <hr className={styles.divider} />
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>담당의</span>
            <span className={styles.fieldValue}>{record.doctor.name}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>진료과목</span>
            <span className={styles.fieldValue}>{record.doctor.department}</span>
          </div>
          {record.room_number && (
            <div className={styles.fieldRow}>
              <span className={styles.fieldLabel}>진료실</span>
              <span className={styles.fieldValue}>{record.room_number}</span>
            </div>
          )}
          <hr className={styles.divider} />
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>주증상</span>
            <span className={styles.fieldValue}>{record.chief_complaint || '-'}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>진단명</span>
            <span className={styles.fieldValue}>{record.diagnosis}</span>
          </div>
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>처방 내용</span>
            <span className={styles.fieldValue}>{record.prescription || '-'}</span>
          </div>
          {record.correction_note && (
            <>
              <hr className={styles.divider} />
              <div className={styles.fieldRow}>
                <span className={styles.fieldLabel}>정정 사유</span>
                <span className={styles.fieldValue}>{record.correction_note}</span>
              </div>
            </>
          )}
          <hr className={styles.divider} />
          <div className={styles.fieldRow}>
            <span className={styles.fieldLabel}>작성일시</span>
            <span className={styles.fieldValue}>{formatDatetime(record.created_at)}</span>
          </div>
        </div>
      ) : (
        <div className={styles.card}>
          <div className={styles.editForm}>
            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>진료일시 (수정 불가)</label>
              <div className={styles.disabledInput}>{formatDatetime(record.visited_at)}</div>
            </div>

            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>담당의 (수정 불가)</label>
              <div className={styles.disabledInput}>{record.doctor.name}</div>
            </div>

            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>진단명 *</label>
              <input
                type="text"
                className={styles.editInput}
                value={editDiagnosis}
                onChange={(e) => setEditDiagnosis(e.target.value)}
              />
            </div>

            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>주증상</label>
              <textarea
                className={styles.editTextarea}
                value={editChiefComplaint}
                onChange={(e) => setEditChiefComplaint(e.target.value)}
              />
            </div>

            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>처방 내용</label>
              <textarea
                className={styles.editTextarea}
                value={editPrescription}
                onChange={(e) => setEditPrescription(e.target.value)}
              />
            </div>

            <div className={styles.editFieldGroup}>
              <label className={styles.editLabel}>정정 사유</label>
              <textarea
                className={styles.editTextarea}
                placeholder="내용 정정 시 사유를 입력하세요"
                value={editCorrectionNote}
                onChange={(e) => setEditCorrectionNote(e.target.value)}
              />
            </div>

            <div className={styles.editActions}>
              <button className={styles.btnCancel} onClick={cancelEdit}>
                취소
              </button>
              <button
                className={styles.btnSave}
                onClick={handleSave}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
