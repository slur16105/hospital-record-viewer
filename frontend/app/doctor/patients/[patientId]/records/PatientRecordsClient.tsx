'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './PatientRecordsClient.module.css'

interface DoctorInfo {
  id: string
  name: string
  department: string
}

interface Record {
  id: string
  visited_at: string
  diagnosis: string
  is_corrected: boolean
  room_number: string | null
  doctor: DoctorInfo
}

interface RecordPage {
  data: Record[]
  total: number
  page: number
  page_size: number
}

function formatDatetime(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function PatientRecordsClient({ patientId }: { patientId: string }) {
  const router = useRouter()
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const { data, isLoading, error } = useQuery<RecordPage>({
    queryKey: ['patient-records', patientId, page],
    queryFn: async () => {
      const res = await fetch(
        `/api/doctor/patients/${patientId}/records?page=${page}&page_size=${PAGE_SIZE}`
      )
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('진료기록 조회 실패')
      return res.json()
    },
    retry: false,
  })

  const isForbidden = (error as (Error & { status?: number }) | null)?.status === 403

  const records = data?.data ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  if (isForbidden) {
    return (
      <div className={styles.container}>
        <p className={styles.forbidden}>이 환자의 진료기록에 접근할 권한이 없습니다.</p>
        <div style={{ textAlign: 'center' }}>
          <Link href="/doctor" className={styles.back}>← 담당 환자 목록으로</Link>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Link href="/doctor" className={styles.back}>← 담당 환자 목록</Link>
          <h1 className={styles.title}>진료기록</h1>
        </div>
        <Link
          href={`/doctor/patients/${patientId}/records/new`}
          className={styles.btnNew}
        >
          + 새 진료기록 작성
        </Link>
      </div>

      {error && !isForbidden && (
        <p className={styles.error}>{(error as Error).message}</p>
      )}

      {isLoading ? (
        <p className={styles.loading}>로딩 중...</p>
      ) : records.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyText}>진료기록이 없습니다. 새 진료기록을 작성하세요.</p>
          <Link href={`/doctor/patients/${patientId}/records/new`} className={styles.btnNew}>
            진료기록 작성
          </Link>
        </div>
      ) : (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>진료일시</th>
                <th className={styles.th}>진단명</th>
                <th className={styles.th}>진료실</th>
                <th className={styles.th}>진료과목</th>
                <th className={styles.th}>상태</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr
                  key={r.id}
                  className={styles.tr}
                  onClick={() =>
                    router.push(`/doctor/patients/${patientId}/records/${r.id}`)
                  }
                >
                  <td className={styles.td}>{formatDatetime(r.visited_at)}</td>
                  <td className={styles.td}>{r.diagnosis}</td>
                  <td className={styles.td}>{r.room_number ?? '-'}</td>
                  <td className={styles.td}>{r.doctor.department}</td>
                  <td className={styles.td}>
                    {r.is_corrected && (
                      <span className={styles.corrected}>정정됨</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button
                className={styles.btnPage}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                이전
              </button>
              <span className={styles.pageInfo}>
                {page} / {totalPages} (총 {total}건)
              </span>
              <button
                className={styles.btnPage}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                다음
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
