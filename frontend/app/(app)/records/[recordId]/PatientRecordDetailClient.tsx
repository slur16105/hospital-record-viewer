'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import styles from './PatientRecordDetailClient.module.css'

interface DoctorInfo {
  id: string
  name: string
  department: string
}

interface RecordDetail {
  id: string
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

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function PatientRecordDetailClient({ recordId }: { recordId: string }) {
  const { data: record, isLoading, error } = useQuery<RecordDetail>({
    queryKey: ['patient-record-detail', recordId],
    queryFn: async () => {
      const res = await fetch(`/api/patient/records/${recordId}`)
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('진료기록 조회 실패')
      return res.json()
    },
    retry: false,
  })

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>
  if ((error as (Error & { status?: number }) | null)?.status === 403)
    return <ForbiddenNotice message="이 진료기록을 볼 수 있는 권한이 없습니다." />
  if (error || !record) return <p className={styles.notFound}>진료기록을 찾을 수 없습니다.</p>

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link href="/records" className={styles.back}>
          ← 내 진료기록 목록
        </Link>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>진료기록 상세</h1>
          {record.is_corrected && (
            <span className={styles.correctedBadge}>정정됨</span>
          )}
        </div>
      </div>

      <div className={styles.card}>
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
    </div>
  )
}
