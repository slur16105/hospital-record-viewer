'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import styles from './PatientsClient.module.css'

interface Patient {
  id: string
  user_id: string
  name: string
  email: string
  birth_date: string
  phone: string
  is_active: boolean
  created_at: string
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

export default function PatientsClient() {
  const queryClient = useQueryClient()
  const [editId, setEditId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editBirthDate, setEditBirthDate] = useState('')
  const [editPhone, setEditPhone] = useState('')
  const [error, setError] = useState('')

  const { data: patients = [], isLoading } = useQuery<Patient[]>({
    queryKey: ['patients-admin'],
    queryFn: async () => {
      const res = await fetch('/api/patients')
      if (!res.ok) throw new Error('목록 조회 실패')
      return res.json()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, ...payload }: { id: string; name: string; birth_date: string; phone: string }) => {
      const res = await fetch(`/api/patients/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '수정 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients-admin'] })
      setEditId(null)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const res = await fetch(`/api/patients/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients-admin'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleEditStart(p: Patient) {
    if (updateMutation.isPending || toggleActiveMutation.isPending) return
    setEditId(p.id)
    setEditName(p.name)
    setEditBirthDate(p.birth_date)
    setEditPhone(p.phone)
    setError('')
  }

  function handleEditSave(p: Patient) {
    if (!editName.trim() || !editPhone.trim()) return
    setError('')
    updateMutation.mutate({ id: p.id, name: editName.trim(), birth_date: editBirthDate, phone: editPhone.trim() })
  }

  const isBusy = updateMutation.isPending || toggleActiveMutation.isPending

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>환자 정보 관리</h1>

      {error && <p className={styles.error}>{error}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>이름</th>
            <th className={styles.th}>이메일</th>
            <th className={styles.th}>생년월일</th>
            <th className={styles.th}>연락처</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>가입일</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {patients.map((p) => (
            <tr key={p.id} className={styles.tr}>
              <td className={styles.td}>
                {editId === p.id
                  ? <input value={editName} onChange={(e) => setEditName(e.target.value)} maxLength={100} className={styles.inputSm} disabled={updateMutation.isPending} />
                  : p.name}
              </td>
              <td className={styles.td}>{p.email}</td>
              <td className={styles.td}>
                {editId === p.id
                  ? <input type="date" value={editBirthDate} onChange={(e) => setEditBirthDate(e.target.value)} className={styles.inputSm} disabled={updateMutation.isPending} />
                  : p.birth_date}
              </td>
              <td className={styles.td}>
                {editId === p.id
                  ? <input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} maxLength={20} className={styles.inputSm} disabled={updateMutation.isPending} />
                  : p.phone}
              </td>
              <td className={styles.td}>
                <span className={p.is_active ? styles.active : styles.inactive}>{p.is_active ? '활성' : '비활성'}</span>
              </td>
              <td className={styles.td}>{p.created_at ? p.created_at.slice(0, 10) : '-'}</td>
              <td className={styles.td}>
                {editId === p.id ? (
                  <>
                    <button onClick={() => handleEditSave(p)} className={styles.btnSave} disabled={updateMutation.isPending}>저장</button>
                    <button onClick={() => setEditId(null)} className={styles.btnCancel} disabled={updateMutation.isPending}>취소</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => handleEditStart(p)} className={styles.btnEdit} disabled={isBusy}>수정</button>
                    <button onClick={() => { setError(''); toggleActiveMutation.mutate({ id: p.id, is_active: !p.is_active }) }} className={styles.btnToggle} disabled={isBusy}>
                      {p.is_active ? '비활성화' : '활성화'}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {patients.length === 0 && <p className={styles.empty}>등록된 환자가 없습니다.</p>}
    </div>
  )
}
