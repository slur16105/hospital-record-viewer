// RBAC 관리 화면(Epic 7·8)이 공유하는 API 응답 타입.
// 백엔드 계약(FastAPI /api/roles, /api/users, /api/permissions, /api/me) 대응.

import type { RoleField } from '@/types/role-fields'

export interface Permission {
  id: string
  code: string
  name: string
  category: string
}

export interface RoleSummary {
  id: string
  name: string
  description: string | null
  is_system: boolean
  is_active: boolean
  user_count: number
}

export interface RoleDetail extends RoleSummary {
  permissions: Permission[]
  fields: RoleField[]
}

export interface UserRoleBadge {
  id: string
  name: string
  is_primary: boolean
}

export interface UserSummary {
  user_id: string
  name: string
  email: string
  is_active: boolean
  roles: UserRoleBadge[]
}

export interface UserDetail {
  profile: {
    user_id: string
    name: string
    is_active: boolean
  }
  email: string
  roles: UserRoleBadge[]
  field_values: Record<string, unknown>
}

export interface MeResponse {
  user: { id: string; email: string }
  profile: { name: string } | null
  roles: UserRoleBadge[]
  primary_role: UserRoleBadge | null
  permissions: string[]
}
