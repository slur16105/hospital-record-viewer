'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import styles from './DepartmentsClient.module.css'

interface Department {
  id: string
  name: string
  is_active: boolean
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

export default function DepartmentsClient() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [editId, setEditId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [error, setError] = useState('')

  const { data: departments = [], isLoading, error: listError } = useQuery<Department[]>({
    queryKey: ['departments'],
    queryFn: async () => {
      const res = await fetch('/api/departments')
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('목록 조회 실패')
      return res.json()
    },
    retry: false,
  })

  const createMutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await fetch('/api/departments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '생성 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
      setNewName('')
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const updateNameMutation = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      const res = await fetch(`/api/departments/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '수정 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
      setEditId(null)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const res = await fetch(`/api/departments/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setError('')
    createMutation.mutate(newName.trim())
  }

  function handleEditStart(dept: Department) {
    if (updateNameMutation.isPending || toggleActiveMutation.isPending) return
    setEditId(dept.id)
    setEditName(dept.name)
    setError('')
  }

  function handleEditSave(dept: Department) {
    if (!editName.trim()) return
    setError('')
    updateNameMutation.mutate({ id: dept.id, name: editName.trim() })
  }

  function handleToggleActive(dept: Department) {
    setError('')
    toggleActiveMutation.mutate({ id: dept.id, is_active: !dept.is_active })
  }

  const isBusy = updateNameMutation.isPending || toggleActiveMutation.isPending

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>

  if ((listError as (Error & { status?: number }) | null)?.status === 403) {
    return <ForbiddenNotice message="진료과목 관리 권한이 없습니다." />
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>진료과목 관리</h1>

      <form onSubmit={handleCreate} className={styles.createForm}>
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          placeholder="새 진료과목 이름"
          maxLength={50}
          className={styles.input}
          disabled={createMutation.isPending}
        />
        <button type="submit" className={styles.button} disabled={createMutation.isPending}>
          {createMutation.isPending ? '등록 중...' : '+ 등록'}
        </button>
      </form>

      {error && <p className={styles.error}>{error}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>진료과목명</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {departments.map((dept) => (
            <tr key={dept.id} className={styles.tr}>
              <td className={styles.td}>
                {editId === dept.id ? (
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    maxLength={50}
                    className={styles.input}
                    disabled={updateNameMutation.isPending}
                  />
                ) : (
                  dept.name
                )}
              </td>
              <td className={styles.td}>
                <span className={dept.is_active ? styles.active : styles.inactive}>
                  {dept.is_active ? '활성' : '비활성'}
                </span>
              </td>
              <td className={styles.td}>
                {editId === dept.id ? (
                  <>
                    <button
                      onClick={() => handleEditSave(dept)}
                      className={styles.btnSave}
                      disabled={updateNameMutation.isPending}
                    >
                      저장
                    </button>
                    <button
                      onClick={() => setEditId(null)}
                      className={styles.btnCancel}
                      disabled={updateNameMutation.isPending}
                    >
                      취소
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleEditStart(dept)}
                      className={styles.btnEdit}
                      disabled={isBusy}
                    >
                      수정
                    </button>
                    <button
                      onClick={() => handleToggleActive(dept)}
                      className={styles.btnToggle}
                      disabled={isBusy}
                    >
                      {dept.is_active ? '비활성화' : '활성화'}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {departments.length === 0 && (
        <p className={styles.empty}>등록된 진료과목이 없습니다.</p>
      )}
    </div>
  )
}
