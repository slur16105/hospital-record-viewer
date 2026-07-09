import PatientsTabs from './PatientsTabs'

// 담당 환자(구 /doctor) + 환자 검색(구 /doctor/search) 통합 — 탭 구성 (Story 9.3)
export default async function PatientsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>
}) {
  const { tab } = await searchParams
  return <PatientsTabs initialTab={tab === 'search' ? 'search' : 'my'} />
}
