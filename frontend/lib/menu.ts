// 권한 기반 메뉴 정의 (Epic 9 — AD-7 기능 URL).
// AppLayout(내비게이션 노출)과 루트 페이지(로그인 후 첫 허용 메뉴 랜딩)가 공유한다.
// 순서가 곧 랜딩 우선순위다.

export interface MenuItem {
  href: string
  label: string
  /** 나열한 권한 중 하나라도 보유하면 노출 */
  permissions: string[]
}

export const MENU_ITEMS: MenuItem[] = [
  {
    href: '/records',
    label: '진료기록',
    // read_own(환자) = 내 진료기록, read_all(관리자) = 전체 진료기록.
    // 의사(read_assigned)는 담당 환자 → 환자별 기록 경로를 쓴다
    // (/records 직접 진입 시 RecordsHome이 /patients로 보정).
    permissions: ['records:read_own', 'records:read_all'],
  },
  { href: '/patients', label: '담당 환자', permissions: ['records:read_assigned'] },
  { href: '/users', label: '사용자', permissions: ['users:read'] },
  { href: '/roles', label: '역할 관리', permissions: ['roles:read'] },
  { href: '/departments', label: '진료과목·진료실', permissions: ['departments:manage'] },
  { href: '/access-logs', label: '접근로그', permissions: ['logs:read'] },
]
