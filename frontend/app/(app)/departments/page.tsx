import DepartmentsTabs from './DepartmentsTabs'

// 진료과목(구 /admin/departments) + 진료실(구 /admin/rooms) 통합 — 탭 구성 (Story 9.3)
export default async function DepartmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>
}) {
  const { tab } = await searchParams
  return <DepartmentsTabs initialTab={tab === 'rooms' ? 'rooms' : 'departments'} />
}
