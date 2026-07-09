'use client'

// Story 8.2: 계정 발급·초대 — 역할 선택 → role_fields 동적 폼(DynamicForm) → 발급.
// 전달 방식: 초대 이메일(기본) / 임시 비밀번호(1회 표시 모달).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useMemo, useState } from 'react'
import DynamicForm, { buildInitialValues } from '@/components/DynamicForm/DynamicForm'
import { extractErrorMessage, extractFieldErrors } from '@/lib/api-error'
import { validateFieldValues } from '@/lib/field-validation'
import { useReferenceOptions } from '@/lib/reference-options'
import { useRoleFields } from '@/lib/use-role-fields'
import type { RoleSummary } from '@/types/rbac'
import PasswordModal from '../PasswordModal'
import styles from './UserCreateClient.module.css'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function UserCreateClient() {
  const router = useRouter()
  const queryClient = useQueryClient()

  const [email, setEmail] = useState('')
  const [userName, setUserName] = useState('')
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [primaryRoleId, setPrimaryRoleId] = useState('')
  const [delivery, setDelivery] = useState<'invite' | 'temp_password'>('invite')
  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState('')
  const [issuedPassword, setIssuedPassword] = useState<string | null>(null)

  const { data: roles = [] } = useQuery<RoleSummary[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const res = await fetch('/api/roles')
      if (!res.ok) throw new Error('역할 목록 조회 실패')
      return res.json()
    },
  })

  const { fields, isLoading: fieldsLoading } = useRoleFields(selectedRoleIds)
  const referenceOptions = useReferenceOptions(fields)

  // 필드 기본값 + 입력값을 렌더 시점에 병합 (입력한 값이 우선)
  const mergedValues = useMemo(
    () => ({ ...buildInitialValues(fields), ...fieldValues }),
    [fields, fieldValues]
  )

  function toggleRole(roleId: string, checked: boolean) {
    setSelectedRoleIds((prev) => {
      const next = checked ? [...prev, roleId] : prev.filter((id) => id !== roleId)
      // 기본 역할이 선택 해제되면 남은 첫 역할을 기본으로
      if (!next.includes(primaryRoleId)) setPrimaryRoleId(next[0] ?? '')
      if (checked && next.length === 1) setPrimaryRoleId(roleId)
      return next
    })
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/api/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email.trim(),
          name: userName.trim(),
          role_ids: selectedRoleIds,
          primary_role_id: primaryRoleId,
          field_values: mergedValues,
          delivery,
        }),
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
        throw new Error(extractErrorMessage(data, '계정 발급 실패'))
      }
      return data as { password?: string }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setFormError('')
      if (data.password) {
        setIssuedPassword(data.password)
      } else {
        router.push('/users')
      }
    },
    onError: (err: Error) => setFormError(err.message),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFieldErrors({})
    if (!EMAIL_PATTERN.test(email.trim())) return setFormError('올바른 이메일을 입력해 주세요.')
    if (!userName.trim()) return setFormError('이름을 입력해 주세요.')
    if (selectedRoleIds.length === 0) return setFormError('역할을 1개 이상 선택해 주세요.')
    if (!primaryRoleId) return setFormError('기본 역할을 지정해 주세요.')

    const errors = validateFieldValues(fields, mergedValues)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return setFormError('입력값을 확인해 주세요.')
    }
    setFormError('')
    createMutation.mutate()
  }

  return (
    <div className={styles.container}>
      <div className={styles.breadcrumb}>
        <Link href="/users" className={styles.backLink}>
          ← 사용자 목록
        </Link>
      </div>
      <h1 className={styles.title}>계정 발급</h1>

      <form onSubmit={handleSubmit} className={styles.form}>
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>계정 정보</h2>
          <label className={styles.fieldLabel}>
            이메일 *
            <input
              type="email"
              className={styles.input}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@hospital.test"
              disabled={createMutation.isPending}
            />
          </label>
          <label className={styles.fieldLabel}>
            이름 *
            <input
              className={styles.input}
              value={userName}
              onChange={(e) => setUserName(e.target.value)}
              maxLength={50}
              disabled={createMutation.isPending}
            />
          </label>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>역할 선택 *</h2>
          <p className={styles.hint}>체크로 역할을 부여하고, 라디오로 기본 역할을 지정합니다.</p>
          <div className={styles.roleList}>
            {roles
              .filter((role) => role.is_active)
              .map((role) => {
                const checked = selectedRoleIds.includes(role.id)
                return (
                  <div key={role.id} className={styles.roleRow}>
                    <label className={styles.roleCheck}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => toggleRole(role.id, e.target.checked)}
                        disabled={createMutation.isPending}
                      />
                      <span className={styles.roleName}>{role.name}</span>
                      {role.description && (
                        <span className={styles.roleDesc}>{role.description}</span>
                      )}
                    </label>
                    <label className={styles.primaryRadio}>
                      <input
                        type="radio"
                        name="primary-role"
                        checked={primaryRoleId === role.id}
                        onChange={() => setPrimaryRoleId(role.id)}
                        disabled={!checked || createMutation.isPending}
                      />
                      기본
                    </label>
                  </div>
                )
              })}
          </div>
        </section>

        {selectedRoleIds.length > 0 && (
          <section className={styles.section}>
            <h2 className={styles.sectionTitle}>역할별 입력 항목</h2>
            {fieldsLoading ? (
              <p className={styles.hint}>필드 정의를 불러오는 중...</p>
            ) : fields.filter((f) => f.is_active).length === 0 ? (
              <p className={styles.hint}>선택한 역할에 정의된 입력 항목이 없습니다.</p>
            ) : (
              <DynamicForm
                fields={fields}
                values={mergedValues}
                onChange={(key, value) => setFieldValues((prev) => ({ ...prev, [key]: value }))}
                errors={fieldErrors}
                disabled={createMutation.isPending}
                referenceOptions={referenceOptions}
              />
            )}
          </section>
        )}

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>전달 방식</h2>
          <label className={styles.deliveryRow}>
            <input
              type="radio"
              name="delivery"
              checked={delivery === 'invite'}
              onChange={() => setDelivery('invite')}
              disabled={createMutation.isPending}
            />
            초대 이메일 (기본) — 사용자가 이메일 링크로 비밀번호를 설정합니다.
          </label>
          <label className={styles.deliveryRow}>
            <input
              type="radio"
              name="delivery"
              checked={delivery === 'temp_password'}
              onChange={() => setDelivery('temp_password')}
              disabled={createMutation.isPending}
            />
            임시 비밀번호 — 발급 직후 1회만 표시되며, 첫 로그인 시 변경이 강제됩니다.
          </label>
        </section>

        {formError && <p className={styles.error}>{formError}</p>}

        <button type="submit" className={styles.btnPrimary} disabled={createMutation.isPending}>
          {createMutation.isPending ? '발급 중...' : '계정 발급'}
        </button>
      </form>

      {issuedPassword !== null && (
        <PasswordModal
          title="임시 비밀번호 발급 완료"
          password={issuedPassword}
          onClose={() => {
            setIssuedPassword(null)
            router.push('/users')
          }}
        />
      )}
    </div>
  )
}
