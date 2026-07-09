'use client'

// /records 진입 분기:
// - records:read_all(관리자) → 전체 진료기록 목록 (환자명 컬럼 포함)
// - records:read_own(환자) → 내 진료기록 목록
// - read_assigned만 보유(의사) → 담당 환자 목록(/patients)으로 이동
// - 전부 없으면 403 안내

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import { usePermissions } from '@/lib/permissions'
import PatientRecordsListClient from './PatientRecordsListClient'

export default function RecordsHome() {
  const router = useRouter()
  const { has, hasAny, isLoading } = usePermissions()

  const canReadAll = has('records:read_all')
  const canReadOwn = !canReadAll && has('records:read_own')
  const shouldGoPatients = !canReadAll && !canReadOwn && hasAny('records:read_assigned')

  useEffect(() => {
    if (!isLoading && shouldGoPatients) router.replace('/patients')
  }, [isLoading, shouldGoPatients, router])

  if (isLoading) return <p style={{ textAlign: 'center', marginTop: '4rem' }}>로딩 중...</p>
  if (canReadAll) return <PatientRecordsListClient scope="all" />
  if (canReadOwn) return <PatientRecordsListClient />
  if (shouldGoPatients)
    return <p style={{ textAlign: 'center', marginTop: '4rem' }}>이동 중...</p>
  return <ForbiddenNotice />
}
