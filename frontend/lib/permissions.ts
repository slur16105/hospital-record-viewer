'use client'

// 권한 훅 (Epic 9 권한 메뉴의 기반).
// /api/me(BFF → FastAPI GET /api/me)를 TanStack Query로 조회해
// 권한 코드 보유 여부를 판정하는 헬퍼를 제공한다.
// 역할·권한 변경 시 queryClient.invalidateQueries({ queryKey: ['me'] })로 갱신한다.

import { useQuery } from '@tanstack/react-query'
import type { MeResponse } from '@/types/rbac'

export const ME_QUERY_KEY = ['me'] as const

export function usePermissions() {
  const { data, isLoading, isError } = useQuery<MeResponse>({
    queryKey: ME_QUERY_KEY,
    queryFn: async () => {
      const res = await fetch('/api/me')
      if (!res.ok) throw new Error('내 정보 조회 실패')
      return res.json()
    },
    staleTime: 60_000, // 역할 변경 60초 내 반영 (Story 8.3)
  })

  const permissions = data?.permissions ?? []

  return {
    me: data ?? null,
    permissions,
    isLoading,
    isError,
    /** 권한 코드 보유 여부 */
    has: (code: string) => permissions.includes(code),
    /** 나열한 권한 중 하나라도 보유하면 true */
    hasAny: (...codes: string[]) => codes.some((code) => permissions.includes(code)),
  }
}
