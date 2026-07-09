'use client'

// Story 8.1·8.3: 사용자 상세 — 프로필+필드값 수정(DynamicForm), 역할 변경(마지막 관리자 보호 오류 표시),
// 비활성화/활성화, 비밀번호 초기화(1회 표시).
// 각 섹션은 데이터 로드 후에만 마운트되어 폼 상태를 props 초기값으로 가진다
// (effect 내 setState 금지 — react-hooks/set-state-in-effect).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import DynamicForm from '@/components/DynamicForm/DynamicForm'
import { extractErrorMessage, extractFieldErrors } from '@/lib/api-error'
import { validateFieldValues } from '@/lib/field-validation'
import { ME_QUERY_KEY } from '@/lib/permissions'
import { useReferenceOptions } from '@/lib/reference-options'
import { useRoleFields } from '@/lib/use-role-fields'
import type { RoleSummary, UserDetail } from '@/types/rbac'
import type { RoleField } from '@/types/role-fields'
import PasswordModal from '../PasswordModal'
import styles from './UserDetailClient.module.css'

export default function UserDetailClient({ userId }: { userId: string }) {
  const { data: user, isLoading } = useQuery<UserDetail>({
    queryKey: ['users', userId],
    queryFn: async () => {
      const res = await fetch(`/api/users/${userId}`)
      if (!res.ok) throw new Error('사용자 조회 실패')
      return res.json()
    },
  })

  const { data: roles = [] } = useQuery<RoleSummary[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const res = await fetch('/api/roles')
      if (!res.ok) throw new Error('역할 목록 조회 실패')
      return res.json()
    },
  })

  // 저장된 역할 기준의 필드 정의 (훅은 조건 없이 호출)
  const savedRoleIds = user?.roles.map((r) => r.id) ?? []
  const { fields } = useRoleFields(savedRoleIds)

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>
  if (!user) return <p className={styles.loading}>사용자를 찾을 수 없습니다.</p>

  return (
    <div className={styles.container}>
      <div className={styles.breadcrumb}>
        <Link href="/users" className={styles.backLink}>
          ← 사용자 목록
        </Link>
      </div>

      <h1 className={styles.title}>
        {user.profile.name}
        <span className={user.profile.is_active ? styles.active : styles.inactive}>
          {user.profile.is_active ? '활성' : '비활성'}
        </span>
      </h1>

      <ProfileSection userId={userId} user={user} fields={fields} />
      <RolesSection userId={userId} user={user} roles={roles} />
      <ActionsSection userId={userId} user={user} />
    </div>
  )
}

// ── 프로필 + 필드값 (DynamicForm) ──────────────────────────

function ProfileSection({
  userId,
  user,
  fields,
}: {
  userId: string
  user: UserDetail
  fields: RoleField[]
}) {
  const queryClient = useQueryClient()
  const [userName, setUserName] = useState(user.profile.name)
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>(
    () => user.field_values ?? {}
  )
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const referenceOptions = useReferenceOptions(fields)

  const updateProfileMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: userName.trim(), field_values: fieldValues }),
      })
      const data = await res.json()
      if (!res.ok) {
        if (res.status === 400) {
          const serverFieldErrors = extractFieldErrors(data)
          if (serverFieldErrors) {
            setFieldErrors(serverFieldErrors)
            throw new Error('입력값을 확인해 주세요.')
          }
        }
        throw new Error(extractErrorMessage(data, '프로필 저장 실패'))
      }
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setError('')
      setFieldErrors({})
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!userName.trim()) return setError('이름을 입력해 주세요.')
    const errors = validateFieldValues(fields, fieldValues)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return setError('입력값을 확인해 주세요.')
    }
    setFieldErrors({})
    setError('')
    updateProfileMutation.mutate()
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>프로필</h2>
      <form onSubmit={handleSave} className={styles.profileForm}>
        <label className={styles.fieldLabel}>
          이메일 (수정 불가)
          <input className={styles.input} value={user.email} disabled />
        </label>
        <label className={styles.fieldLabel}>
          이름
          <input
            className={styles.input}
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            maxLength={50}
            disabled={updateProfileMutation.isPending}
          />
        </label>

        {fields.filter((f) => f.is_active).length > 0 && (
          <DynamicForm
            fields={fields}
            values={fieldValues}
            onChange={(key, value) => setFieldValues((prev) => ({ ...prev, [key]: value }))}
            errors={fieldErrors}
            disabled={updateProfileMutation.isPending}
            referenceOptions={referenceOptions}
          />
        )}

        {error && <p className={styles.error}>{error}</p>}
        <div>
          <button
            type="submit"
            className={styles.btnPrimary}
            disabled={updateProfileMutation.isPending}
          >
            {updateProfileMutation.isPending ? '저장 중...' : '프로필 저장'}
          </button>
        </div>
      </form>
    </section>
  )
}

// ── 역할 변경 (Story 8.3) ──────────────────────────────────

function RolesSection({
  userId,
  user,
  roles,
}: {
  userId: string
  user: UserDetail
  roles: RoleSummary[]
}) {
  const queryClient = useQueryClient()
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>(() =>
    user.roles.map((r) => r.id)
  )
  const [primaryRoleId, setPrimaryRoleId] = useState(
    () => user.roles.find((r) => r.is_primary)?.id ?? user.roles[0]?.id ?? ''
  )
  const [error, setError] = useState('')

  const updateRolesMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/users/${userId}/roles`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_ids: selectedRoleIds, primary_role_id: primaryRoleId }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(extractErrorMessage(data, '역할 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      queryClient.invalidateQueries({ queryKey: ['role-fields'] })
      queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY }) // 60초 내 권한 반영
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function toggleRole(roleId: string, checked: boolean) {
    setSelectedRoleIds((prev) => {
      const next = checked ? [...prev, roleId] : prev.filter((id) => id !== roleId)
      if (!next.includes(primaryRoleId)) setPrimaryRoleId(next[0] ?? '')
      if (checked && next.length === 1) setPrimaryRoleId(roleId)
      return next
    })
  }

  function handleSave() {
    if (selectedRoleIds.length === 0) return setError('역할을 1개 이상 선택해 주세요.')
    if (!primaryRoleId) return setError('기본 역할을 지정해 주세요.')
    setError('')
    updateRolesMutation.mutate()
  }

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>역할</h2>
      <p className={styles.hint}>체크로 역할을 부여하고, 라디오로 기본 역할을 지정합니다.</p>
      <div className={styles.roleList}>
        {roles
          .filter((role) => role.is_active || selectedRoleIds.includes(role.id))
          .map((role) => {
            const checked = selectedRoleIds.includes(role.id)
            return (
              <div key={role.id} className={styles.roleRow}>
                <label className={styles.roleCheck}>
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => toggleRole(role.id, e.target.checked)}
                    disabled={updateRolesMutation.isPending}
                  />
                  <span className={styles.roleName}>{role.name}</span>
                </label>
                <label className={styles.primaryRadio}>
                  <input
                    type="radio"
                    name="primary-role"
                    checked={primaryRoleId === role.id}
                    onChange={() => setPrimaryRoleId(role.id)}
                    disabled={!checked || updateRolesMutation.isPending}
                  />
                  기본
                </label>
              </div>
            )
          })}
      </div>
      {error && <p className={styles.error}>{error}</p>}
      <button
        className={styles.btnPrimary}
        onClick={handleSave}
        disabled={updateRolesMutation.isPending}
      >
        {updateRolesMutation.isPending ? '저장 중...' : '역할 저장'}
      </button>
    </section>
  )
}

// ── 계정 작업 (비활성화/활성화 · 비밀번호 초기화) ──────────

function ActionsSection({ userId, user }: { userId: string; user: UserDetail }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const [resetPassword, setResetPassword] = useState<string | null>(null)

  const activationMutation = useMutation({
    mutationFn: async (action: 'activate' | 'deactivate') => {
      const res = await fetch(`/api/users/${userId}/${action}`, { method: 'POST' })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(extractErrorMessage(data, '상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const resetPasswordMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/users/${userId}/reset-password`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '비밀번호 초기화 실패'))
      return data as { password: string }
    },
    onSuccess: (data) => {
      setError('')
      setResetPassword(data.password)
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>계정 작업</h2>
      {error && <p className={styles.error}>{error}</p>}
      <div className={styles.actionRow}>
        {user.profile.is_active ? (
          <button
            className={styles.btnDanger}
            onClick={() => {
              if (window.confirm('이 계정을 비활성화하시겠습니까? 로그인이 차단됩니다.')) {
                activationMutation.mutate('deactivate')
              }
            }}
            disabled={activationMutation.isPending}
          >
            계정 비활성화
          </button>
        ) : (
          <button
            className={styles.btnSecondary}
            onClick={() => activationMutation.mutate('activate')}
            disabled={activationMutation.isPending}
          >
            계정 활성화
          </button>
        )}
        <button
          className={styles.btnSecondary}
          onClick={() => {
            if (window.confirm('비밀번호를 초기화하시겠습니까? 새 비밀번호가 1회만 표시됩니다.')) {
              resetPasswordMutation.mutate()
            }
          }}
          disabled={resetPasswordMutation.isPending}
        >
          {resetPasswordMutation.isPending ? '초기화 중...' : '비밀번호 초기화'}
        </button>
      </div>

      {resetPassword !== null && (
        <PasswordModal
          title="비밀번호 초기화 완료"
          password={resetPassword}
          onClose={() => setResetPassword(null)}
        />
      )}
    </section>
  )
}
