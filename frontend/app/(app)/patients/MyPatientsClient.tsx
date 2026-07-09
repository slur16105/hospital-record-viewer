'use client'

import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import styles from './MyPatientsClient.module.css'

interface MyPatient {
  id: string
  user_id: string
  name: string
  birth_date: string
  latest_visited_at: string | null
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('ko-KR')
}

export default function MyPatientsClient() {
  const router = useRouter()

  const { data: patients = [], isLoading, error } = useQuery<MyPatient[]>({
    queryKey: ['doctor-my-patients'],
    queryFn: async () => {
      const res = await fetch('/api/doctor/my-patients')
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('담당 환자 목록 조회 실패')
      return res.json()
    },
    retry: false,
  })

  if ((error as (Error & { status?: number }) | null)?.status === 403) {
    return <ForbiddenNotice message="담당 환자 목록을 볼 수 있는 권한이 없습니다." />
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>담당 환자 목록</h1>
      </div>

      {error && <p className={styles.error}>{(error as Error).message}</p>}

      {isLoading ? (
        <p className={styles.loading}>로딩 중...</p>
      ) : patients.length === 0 ? (
        <p className={styles.empty}>아직 담당 환자가 없습니다. 환자 검색으로 신규 진료를 시작하세요.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>이름</th>
              <th className={styles.th}>생년월일</th>
              <th className={styles.th}>최근 진료일</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr
                key={p.id}
                className={styles.tr}
                onClick={() => router.push(`/patients/${p.id}/records`)}
              >
                <td className={styles.td}>{p.name}</td>
                <td className={styles.td}>{p.birth_date}</td>
                <td className={styles.td}>{formatDate(p.latest_visited_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
