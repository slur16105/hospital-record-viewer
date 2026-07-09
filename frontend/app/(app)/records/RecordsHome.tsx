'use client'

// /records 진입 분기 (Story 9.3):
// - records:read_own → 본인 진료기록 목록 (구 /patient 화면)
// - read_own 없이 read_assigned 보유(의사) → 담당 환자 목록(/patients)으로 이동
// - 둘 다 없으면 403 안내

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import { usePermissions } from '@/lib/permissions'
import PatientRecordsListClient from './PatientRecordsListClient'

export default function RecordsHome() {
  const router = useRouter()
  const { has, hasAny, isLoading } = usePermissions()

  const canReadOwn = has('records:read_own')
  const shouldGoPatients = !canReadOwn && hasAny('records:read_assigned', 'records:read_all')

  useEffect(() => {
    if (!isLoading && shouldGoPatients) router.replace('/patients')
  }, [isLoading, shouldGoPatients, router])

  if (isLoading) return <p style={{ textAlign: 'center', marginTop: '4rem' }}>로딩 중...</p>
  if (canReadOwn) return <PatientRecordsListClient />
  if (shouldGoPatients)
    return <p style={{ textAlign: 'center', marginTop: '4rem' }}>이동 중...</p>
  return <ForbiddenNotice />
}
