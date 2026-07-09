'use client'

// 진료기록 상세 분기 (Story 9.3, AD-6).
// 조회 API(의사용/환자용)는 백엔드 계약이 아직 분리돼 있으므로
// permissions로 어느 화면(=어느 BFF 경로)을 쓸지 결정한다.
// 실제 접근 인가(담당의/본인 여부)는 백엔드가 판정하며, 403 시 안내 화면을 띄운다.

import ForbiddenNotice from '@/components/ForbiddenNotice'
import { usePermissions } from '@/lib/permissions'
import PatientRecordDetailClient from './PatientRecordDetailClient'
import RecordDetailClient from './RecordDetailClient'

export default function RecordDetailSwitch({
  recordId,
  patientId,
}: {
  recordId: string
  patientId: string | null
}) {
  const { has, hasAny, isLoading } = usePermissions()

  if (isLoading) return <p style={{ textAlign: 'center', marginTop: '4rem' }}>로딩 중...</p>

  // 의사 계열: 담당/전체 열람 권한 → 의사용 상세 (수정 UI는 records:update_own 보유 시에만)
  if (hasAny('records:read_assigned', 'records:read_all')) {
    return (
      <RecordDetailClient
        recordId={recordId}
        patientId={patientId}
        canEdit={has('records:update_own')}
      />
    )
  }

  // 환자 계열: 본인 기록 열람
  if (has('records:read_own')) {
    return <PatientRecordDetailClient recordId={recordId} />
  }

  return <ForbiddenNotice />
}
