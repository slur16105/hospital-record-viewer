import RecordDetailSwitch from './RecordDetailSwitch'

// 진료기록 상세 통합 URL (Story 9.3).
// ?patient=<id>는 의사 흐름(/patients/[id]/records)에서 넘어온 목록 복귀 컨텍스트.
export default async function RecordDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ recordId: string }>
  searchParams: Promise<{ patient?: string }>
}) {
  const { recordId } = await params
  const { patient } = await searchParams
  return <RecordDetailSwitch recordId={recordId} patientId={patient ?? null} />
}
