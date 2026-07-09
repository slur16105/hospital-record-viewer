'use client'

// Story 7.2·7.3·7.4: 역할 상세 — ① 기본정보 ② 권한 조합 ③ 폼 빌더 + 미리보기(DynamicForm)
// 각 섹션은 데이터 로드 후에만 마운트되는 하위 컴포넌트로, 폼 상태를 props 초기값으로 가진다
// (effect 내 setState 금지 — react-hooks/set-state-in-effect).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import DynamicForm, { buildInitialValues } from '@/components/DynamicForm/DynamicForm'
import { extractErrorMessage } from '@/lib/api-error'
import { validateFieldValues } from '@/lib/field-validation'
import { useReferenceOptions } from '@/lib/reference-options'
import type { Permission, RoleDetail } from '@/types/rbac'
import type { RoleField } from '@/types/role-fields'
import FieldEditor, { type FieldEditorPayload } from './FieldEditor'
import styles from './RoleDetailClient.module.css'

type Tab = 'info' | 'permissions' | 'fields' | 'preview'

const TABS: { key: Tab; label: string }[] = [
  { key: 'info', label: '기본정보' },
  { key: 'permissions', label: '권한 조합' },
  { key: 'fields', label: '입력필드' },
  { key: 'preview', label: '미리보기' },
]

export default function RoleDetailClient({ roleId }: { roleId: string }) {
  const [tab, setTab] = useState<Tab>('info')

  const { data: role, isLoading } = useQuery<RoleDetail>({
    queryKey: ['roles', roleId],
    queryFn: async () => {
      const res = await fetch(`/api/roles/${roleId}`)
      if (!res.ok) throw new Error('역할 조회 실패')
      return res.json()
    },
  })

  const { data: catalog = [] } = useQuery<Permission[]>({
    queryKey: ['permissions'],
    queryFn: async () => {
      const res = await fetch('/api/permissions')
      if (!res.ok) throw new Error('권한 카탈로그 조회 실패')
      return res.json()
    },
  })

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>
  if (!role) return <p className={styles.loading}>역할을 찾을 수 없습니다.</p>

  return (
    <div className={styles.container}>
      <div className={styles.breadcrumb}>
        <Link href="/roles" className={styles.backLink}>
          ← 역할 목록
        </Link>
      </div>

      <h1 className={styles.title}>
        {role.name}
        {role.is_system && <span className={styles.systemBadge}>시스템</span>}
        <span className={role.is_active ? styles.active : styles.inactive}>
          {role.is_active ? '활성' : '비활성'}
        </span>
      </h1>

      <div className={styles.tabs} role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            className={tab === t.key ? styles.tabActive : styles.tab}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'info' && <InfoSection roleId={roleId} role={role} />}
      {tab === 'permissions' && (
        <PermissionsSection roleId={roleId} role={role} catalog={catalog} />
      )}
      {tab === 'fields' && <FieldsSection roleId={roleId} fields={role.fields} />}
      {tab === 'preview' && <PreviewSection fields={role.fields} />}
    </div>
  )
}

// ── ① 기본정보 ─────────────────────────────────────────────

function InfoSection({ roleId, role }: { roleId: string; role: RoleDetail }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState(role.name)
  const [description, setDescription] = useState(role.description ?? '')
  const [isActive, setIsActive] = useState(role.is_active)
  const [error, setError] = useState('')

  const infoLocked = role.is_system

  const updateInfoMutation = useMutation({
    mutationFn: async (payload: { name: string; description: string; is_active: boolean }) => {
      const res = await fetch(`/api/roles/${roleId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '기본정보 저장 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  return (
    <section className={styles.section}>
      {infoLocked && (
        <p className={styles.lockedNotice}>
          시스템 역할은 기본정보를 수정할 수 없습니다. (편집 잠금)
        </p>
      )}
      {error && <p className={styles.error}>{error}</p>}
      <form
        className={styles.infoForm}
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim()) return
          setError('')
          updateInfoMutation.mutate({
            name: name.trim(),
            description: description.trim(),
            is_active: isActive,
          })
        }}
      >
        <label className={styles.fieldLabel}>
          이름
          <input
            className={styles.input}
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            disabled={infoLocked || updateInfoMutation.isPending}
          />
        </label>
        <label className={styles.fieldLabel}>
          설명
          <input
            className={styles.input}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={200}
            disabled={infoLocked || updateInfoMutation.isPending}
          />
        </label>
        <label className={styles.flag}>
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            disabled={infoLocked || updateInfoMutation.isPending}
          />
          활성
        </label>
        <div>
          <button
            type="submit"
            className={styles.btnPrimary}
            disabled={infoLocked || updateInfoMutation.isPending}
          >
            {updateInfoMutation.isPending ? '저장 중...' : '기본정보 저장'}
          </button>
        </div>
      </form>
      <p className={styles.meta}>사용자 수: {role.user_count}명</p>
    </section>
  )
}

// ── ② 권한 조합 ────────────────────────────────────────────

function PermissionsSection({
  roleId,
  role,
  catalog,
}: {
  roleId: string
  role: RoleDetail
  catalog: Permission[]
}) {
  const queryClient = useQueryClient()
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(role.permissions.map((p) => p.id))
  )
  const [error, setError] = useState('')

  const savePermissionsMutation = useMutation({
    mutationFn: async (permissionIds: string[]) => {
      const res = await fetch(`/api/roles/${roleId}/permissions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ permission_ids: permissionIds }),
      })
      const data = await res.json().catch(() => null)
      if (!res.ok) throw new Error(extractErrorMessage(data, '권한 저장 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      queryClient.invalidateQueries({ queryKey: ['me'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const categories = Array.from(new Set(catalog.map((p) => p.category))).sort()

  function toggleCategory(category: string, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev)
      catalog
        .filter((p) => p.category === category)
        .forEach((p) => (checked ? next.add(p.id) : next.delete(p.id)))
      return next
    })
  }

  return (
    <section className={styles.section}>
      {error && <p className={styles.error}>{error}</p>}
      {categories.length === 0 && <p className={styles.empty}>권한 카탈로그가 비어 있습니다.</p>}
      {categories.map((category) => {
        const perms = catalog.filter((p) => p.category === category)
        const allChecked = perms.every((p) => selected.has(p.id))
        return (
          <div key={category} className={styles.permCategory}>
            <label className={styles.permCategoryHeader}>
              <input
                type="checkbox"
                checked={allChecked}
                onChange={(e) => toggleCategory(category, e.target.checked)}
                disabled={savePermissionsMutation.isPending}
              />
              <span className={styles.permCategoryName}>{category}</span>
            </label>
            <div className={styles.permList}>
              {perms.map((perm) => (
                <label key={perm.id} className={styles.permItem}>
                  <input
                    type="checkbox"
                    checked={selected.has(perm.id)}
                    onChange={(e) =>
                      setSelected((prev) => {
                        const next = new Set(prev)
                        if (e.target.checked) next.add(perm.id)
                        else next.delete(perm.id)
                        return next
                      })
                    }
                    disabled={savePermissionsMutation.isPending}
                  />
                  <span>{perm.name}</span>
                  <code className={styles.permCode}>{perm.code}</code>
                </label>
              ))}
            </div>
          </div>
        )
      })}
      <button
        className={styles.btnPrimary}
        onClick={() => {
          setError('')
          savePermissionsMutation.mutate(Array.from(selected))
        }}
        disabled={savePermissionsMutation.isPending || catalog.length === 0}
      >
        {savePermissionsMutation.isPending ? '저장 중...' : '권한 저장'}
      </button>
    </section>
  )
}

// ── ③ 폼 빌더 ─────────────────────────────────────────────

function FieldsSection({ roleId, fields }: { roleId: string; fields: RoleField[] }) {
  const queryClient = useQueryClient()
  const [editorMode, setEditorMode] = useState<'closed' | 'create' | 'edit'>('closed')
  const [editingField, setEditingField] = useState<RoleField | undefined>(undefined)
  const [error, setError] = useState('')

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['roles'] })
    queryClient.invalidateQueries({ queryKey: ['role-fields'] })
  }

  const saveFieldMutation = useMutation({
    mutationFn: async (payload: FieldEditorPayload) => {
      const isEdit = editorMode === 'edit' && editingField?.id
      const url = isEdit
        ? `/api/roles/${roleId}/fields/${editingField.id}`
        : `/api/roles/${roleId}/fields`
      const res = await fetch(url, {
        method: isEdit ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '필드 저장 실패'))
      return data
    },
    onSuccess: () => {
      invalidate()
      setEditorMode('closed')
      setEditingField(undefined)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const toggleFieldMutation = useMutation({
    mutationFn: async (field: RoleField) => {
      const res = await fetch(`/api/roles/${roleId}/fields/${field.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !field.is_active }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '필드 상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      invalidate()
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const sortedFields = [...fields].sort((a, b) => a.sort_order - b.sort_order)
  const isBusy = saveFieldMutation.isPending || toggleFieldMutation.isPending

  return (
    <section className={styles.section}>
      {error && <p className={styles.error}>{error}</p>}
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>순서</th>
            <th className={styles.th}>라벨</th>
            <th className={styles.th}>키</th>
            <th className={styles.th}>타입</th>
            <th className={styles.th}>필수</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {sortedFields.map((field) => (
            <tr key={field.field_key} className={styles.tr}>
              <td className={styles.td}>{field.sort_order}</td>
              <td className={styles.td}>{field.label}</td>
              <td className={styles.td}>
                <code>{field.field_key}</code>
              </td>
              <td className={styles.td}>{field.field_type}</td>
              <td className={styles.td}>{field.is_required ? '필수' : '-'}</td>
              <td className={styles.td}>
                <span className={field.is_active ? styles.active : styles.inactive}>
                  {field.is_active ? '활성' : '비활성'}
                </span>
              </td>
              <td className={styles.td}>
                <button
                  className={styles.btnSmall}
                  onClick={() => {
                    setEditingField(field)
                    setEditorMode('edit')
                    setError('')
                  }}
                  disabled={isBusy}
                >
                  수정
                </button>
                <button
                  className={styles.btnSmall}
                  onClick={() => {
                    setError('')
                    toggleFieldMutation.mutate(field)
                  }}
                  disabled={isBusy}
                >
                  {field.is_active ? '비활성화' : '활성화'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {sortedFields.length === 0 && <p className={styles.empty}>정의된 입력필드가 없습니다.</p>}

      {editorMode === 'closed' ? (
        <button
          className={styles.btnPrimary}
          onClick={() => {
            setEditingField(undefined)
            setEditorMode('create')
            setError('')
          }}
        >
          + 필드 추가
        </button>
      ) : (
        <FieldEditor
          key={editorMode === 'edit' ? editingField?.id : 'create'}
          initial={editorMode === 'edit' ? editingField : undefined}
          onSubmit={(payload) => saveFieldMutation.mutate(payload)}
          onCancel={() => {
            setEditorMode('closed')
            setEditingField(undefined)
          }}
          isPending={saveFieldMutation.isPending}
        />
      )}
    </section>
  )
}

// ── 미리보기 (DynamicForm 즉시 렌더) ───────────────────────

function PreviewSection({ fields }: { fields: RoleField[] }) {
  const [values, setValues] = useState<Record<string, unknown>>(() => buildInitialValues(fields))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const referenceOptions = useReferenceOptions(fields)

  return (
    <section className={styles.section}>
      <p className={styles.previewNotice}>
        이 역할의 활성 필드가 실제 계정 발급 화면과 동일하게 렌더링됩니다.
      </p>
      <DynamicForm
        fields={fields}
        values={values}
        onChange={(key, value) => setValues((prev) => ({ ...prev, [key]: value }))}
        errors={errors}
        referenceOptions={referenceOptions}
      />
      {fields.filter((f) => f.is_active).length === 0 && (
        <p className={styles.empty}>미리볼 활성 필드가 없습니다.</p>
      )}
      <div className={styles.previewActions}>
        <button
          className={styles.btnPrimary}
          onClick={() => setErrors(validateFieldValues(fields, values))}
        >
          입력값 검증
        </button>
        <button
          className={styles.btnSmall}
          onClick={() => {
            setValues(buildInitialValues(fields))
            setErrors({})
          }}
        >
          초기화
        </button>
      </div>
    </section>
  )
}
