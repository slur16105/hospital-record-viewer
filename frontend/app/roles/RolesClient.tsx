'use client'

// Story 7.2: 역할 관리 화면 — 목록·생성·삭제(불가 사유 표시)

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import { extractErrorMessage } from '@/lib/api-error'
import type { RoleSummary } from '@/types/rbac'
import styles from './RolesClient.module.css'

function deleteDisabledReason(role: RoleSummary): string | null {
  if (role.is_system) return '시스템 역할은 삭제할 수 없습니다.'
  if (role.user_count > 0) return '사용자가 있는 역할은 삭제할 수 없습니다. 먼저 사용자의 역할을 변경하세요.'
  return null
}

export default function RolesClient() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [error, setError] = useState('')

  const { data: roles = [], isLoading } = useQuery<RoleSummary[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const res = await fetch('/api/roles')
      if (!res.ok) throw new Error('역할 목록 조회 실패')
      return res.json()
    },
  })

  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; description: string }) => {
      const res = await fetch('/api/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '역할 생성 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setNewName('')
      setNewDescription('')
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/roles/${id}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        if (res.status === 409) {
          throw new Error(extractErrorMessage(data, '사용자가 있는 역할은 삭제할 수 없습니다.'))
        }
        if (res.status === 403) {
          throw new Error(extractErrorMessage(data, '시스템 역할은 삭제할 수 없습니다.'))
        }
        throw new Error(extractErrorMessage(data, '역할 삭제 실패'))
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setError('')
    createMutation.mutate({ name: newName.trim(), description: newDescription.trim() })
  }

  function handleDelete(role: RoleSummary) {
    if (!window.confirm(`'${role.name}' 역할을 삭제하시겠습니까?`)) return
    setError('')
    deleteMutation.mutate(role.id)
  }

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>역할 관리</h1>

      <form onSubmit={handleCreate} className={styles.createForm}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="새 역할 이름"
          maxLength={50}
          className={styles.input}
          disabled={createMutation.isPending}
        />
        <input
          value={newDescription}
          onChange={(e) => setNewDescription(e.target.value)}
          placeholder="설명 (선택)"
          maxLength={200}
          className={styles.inputWide}
          disabled={createMutation.isPending}
        />
        <button type="submit" className={styles.button} disabled={createMutation.isPending}>
          {createMutation.isPending ? '생성 중...' : '+ 역할 생성'}
        </button>
      </form>

      {error && <p className={styles.error}>{error}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>이름</th>
            <th className={styles.th}>설명</th>
            <th className={styles.th}>사용자 수</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {roles.map((role) => {
            const reason = deleteDisabledReason(role)
            return (
              <tr key={role.id} className={styles.tr}>
                <td className={styles.td}>
                  <Link href={`/roles/${role.id}`} className={styles.roleLink}>
                    {role.name}
                  </Link>
                  {role.is_system && <span className={styles.systemBadge}>시스템</span>}
                </td>
                <td className={styles.td}>{role.description || '-'}</td>
                <td className={styles.td}>{role.user_count}</td>
                <td className={styles.td}>
                  <span className={role.is_active ? styles.active : styles.inactive}>
                    {role.is_active ? '활성' : '비활성'}
                  </span>
                </td>
                <td className={styles.td}>
                  <Link href={`/roles/${role.id}`} className={styles.btnEdit}>
                    상세
                  </Link>
                  <button
                    onClick={() => handleDelete(role)}
                    className={styles.btnDelete}
                    disabled={reason !== null || deleteMutation.isPending}
                    title={reason ?? '역할 삭제'}
                  >
                    삭제
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {roles.length === 0 && <p className={styles.empty}>등록된 역할이 없습니다.</p>}
    </div>
  )
}
