'use client'

// 선택된 역할들의 role_fields를 GET /api/roles/{id}로 조회해 합치는 훅.
// 계정 발급(Story 8.2)·사용자 상세(Story 8.1)에서 DynamicForm 렌더에 사용한다.
// 같은 field_key가 여러 역할에 있으면 먼저 온 정의를 유지한다.

import { useQuery } from '@tanstack/react-query'
import type { RoleDetail } from '@/types/rbac'
import type { RoleField } from '@/types/role-fields'

export function useRoleFields(roleIds: string[]): {
  fields: RoleField[]
  isLoading: boolean
  isError: boolean
} {
  const sortedIds = [...roleIds].sort()

  const { data, isLoading, isError } = useQuery<RoleField[]>({
    queryKey: ['role-fields', sortedIds],
    enabled: sortedIds.length > 0,
    queryFn: async () => {
      const details = await Promise.all(
        sortedIds.map(async (id) => {
          const res = await fetch(`/api/roles/${id}`)
          if (!res.ok) throw new Error('역할 필드 조회 실패')
          return res.json() as Promise<RoleDetail>
        })
      )
      const byKey = new Map<string, RoleField>()
      for (const detail of details) {
        for (const field of detail.fields ?? []) {
          if (!byKey.has(field.field_key)) byKey.set(field.field_key, field)
        }
      }
      return Array.from(byKey.values())
    },
  })

  if (sortedIds.length === 0) return { fields: [], isLoading: false, isError: false }
  return { fields: data ?? [], isLoading, isError }
}
