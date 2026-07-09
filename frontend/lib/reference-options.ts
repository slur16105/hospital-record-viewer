'use client'

// reference 타입 필드의 선택지를 부모에서 조회해 DynamicForm에 주입하기 위한 훅.
// DynamicForm은 fetch하지 않는다는 계약(AD-12)에 따라 여기서 BFF 경유로 조회한다.
// 현재 조회 가능한 대상 테이블: departments, rooms (기존 BFF 엔드포인트 재사용).

import { useQuery } from '@tanstack/react-query'
import type { ReferenceOption, RoleField } from '@/types/role-fields'

const TABLE_ENDPOINTS: Record<string, string> = {
  departments: '/api/departments',
  rooms: '/api/rooms',
}

type Row = Record<string, unknown>

/** 활성 reference 필드들의 { field_key: 선택지[] } 를 반환한다 */
export function useReferenceOptions(fields: RoleField[]): Record<string, ReferenceOption[]> {
  const refFields = fields.filter(
    (f) =>
      f.is_active &&
      f.field_type === 'reference' &&
      f.options?.table !== undefined &&
      TABLE_ENDPOINTS[f.options.table] !== undefined
  )
  const tables = Array.from(new Set(refFields.map((f) => f.options!.table!))).sort()

  const { data } = useQuery<Record<string, Row[]>>({
    queryKey: ['reference-options', tables],
    enabled: tables.length > 0,
    queryFn: async () => {
      const rowsByTable: Record<string, Row[]> = {}
      await Promise.all(
        tables.map(async (table) => {
          const res = await fetch(TABLE_ENDPOINTS[table])
          const rows = res.ok ? await res.json() : []
          rowsByTable[table] = Array.isArray(rows) ? rows : []
        })
      )
      return rowsByTable
    },
  })

  const rowsByTable = data ?? {}
  const options: Record<string, ReferenceOption[]> = {}
  for (const field of refFields) {
    const rows = rowsByTable[field.options!.table!] ?? []
    const labelColumn = field.options?.label_column ?? 'name'
    options[field.field_key] = rows
      .filter((row) => row.id !== undefined && row.id !== null)
      .map((row) => ({
        value: String(row.id),
        label: String(row[labelColumn] ?? row.id),
      }))
  }
  return options
}
