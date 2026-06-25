'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import styles from './DoctorsClient.module.css'

interface Department {
  id: string
  name: string
  is_active: boolean
}

interface Doctor {
  id: string
  user_id: string
  name: string
  email: string
  department_id: string
  department_name: string
  license_number: string
  is_active: boolean
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

export default function DoctorsClient() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [formName, setFormName] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formDeptId, setFormDeptId] = useState('')
  const [formLicense, setFormLicense] = useState('')
  const [formError, setFormError] = useState('')
  const [tempPassword, setTempPassword] = useState<string | null>(null)
  const [editId, setEditId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editDeptId, setEditDeptId] = useState('')
  const [editLicense, setEditLicense] = useState('')
  const [error, setError] = useState('')

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ['departments'],
    queryFn: async () => {
      const res = await fetch('/api/departments')
      if (!res.ok) throw new Error('진료과목 목록 조회 실패')
      return res.json()
    },
  })
  const activeDepts = departments.filter((d) => d.is_active)

  const { data: doctors = [], isLoading } = useQuery<Doctor[]>({
    queryKey: ['doctors'],
    queryFn: async () => {
      const res = await fetch('/api/doctors')
      if (!res.ok) throw new Error('목록 조회 실패')
      return res.json()
    },
  })

  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; email: string; department_id: string; license_number: string }) => {
      const res = await fetch('/api/doctors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '생성 실패'))
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
      setTempPassword(data.temp_password)
      setShowForm(false)
      setFormName('')
      setFormEmail('')
      setFormDeptId('')
      setFormLicense('')
      setFormError('')
    },
    onError: (err: Error) => setFormError(err.message),
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, ...payload }: { id: string; name: string; department_id: string; license_number: string }) => {
      const res = await fetch(`/api/doctors/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '수정 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
      setEditId(null)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const res = await fetch(`/api/doctors/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const resetPasswordMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`/api/doctors/${id}/reset-password`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '비밀번호 초기화 실패'))
      return data
    },
    onSuccess: (data) => {
      setTempPassword(data.temp_password)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    if (!formName.trim()) { setFormError('이름은 필수 항목입니다'); return }
    if (!formEmail.trim()) { setFormError('이메일은 필수 항목입니다'); return }
    if (!formDeptId) { setFormError('소속 진료과목은 필수 항목입니다'); return }
    if (!formLicense.trim()) { setFormError('면허번호는 필수 항목입니다'); return }
    createMutation.mutate({ name: formName.trim(), email: formEmail.trim(), department_id: formDeptId, license_number: formLicense.trim() })
  }

  function handleEditStart(doc: Doctor) {
    setEditId(doc.id)
    setEditName(doc.name)
    setEditDeptId(doc.department_id)
    setEditLicense(doc.license_number)
    setError('')
  }

  function handleEditSave(doc: Doctor) {
    if (!editName.trim() || !editLicense.trim()) return
    setError('')
    updateMutation.mutate({ id: doc.id, name: editName.trim(), department_id: editDeptId, license_number: editLicense.trim() })
  }

  const isBusy = updateMutation.isPending || toggleActiveMutation.isPending || resetPasswordMutation.isPending

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>의사 계정 관리</h1>
        <button onClick={() => { setShowForm(!showForm); setFormError(''); setTempPassword(null) }} className={styles.button}>
          {showForm ? '닫기' : '+ 의사 등록'}
        </button>
      </div>

      {tempPassword && (
        <div className={styles.tempPasswordBox}>
          <p className={styles.tempPasswordLabel}>임시 비밀번호 (1회만 표시됩니다)</p>
          <code className={styles.tempPassword}>{tempPassword}</code>
          <button onClick={() => setTempPassword(null)} className={styles.btnClose}>확인</button>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className={styles.createForm}>
          <div className={styles.formRow}>
            <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="이름" maxLength={100} className={styles.input} disabled={createMutation.isPending} />
            <input value={formEmail} onChange={(e) => setFormEmail(e.target.value)} placeholder="이메일" type="email" className={styles.input} disabled={createMutation.isPending} />
          </div>
          <div className={styles.formRow}>
            <select value={formDeptId} onChange={(e) => setFormDeptId(e.target.value)} className={styles.select} disabled={createMutation.isPending}>
              <option value="">진료과목 선택</option>
              {activeDepts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <input value={formLicense} onChange={(e) => setFormLicense(e.target.value)} placeholder="면허번호" maxLength={50} className={styles.input} disabled={createMutation.isPending} />
          </div>
          {formError && <p className={styles.error}>{formError}</p>}
          <button type="submit" className={styles.button} disabled={createMutation.isPending}>
            {createMutation.isPending ? '등록 중...' : '저장'}
          </button>
        </form>
      )}

      {error && <p className={styles.error}>{error}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>이름</th>
            <th className={styles.th}>이메일</th>
            <th className={styles.th}>진료과목</th>
            <th className={styles.th}>면허번호</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {doctors.map((doc) => (
            <tr key={doc.id} className={styles.tr}>
              <td className={styles.td}>
                {editId === doc.id ? <input value={editName} onChange={(e) => setEditName(e.target.value)} maxLength={100} className={styles.inputSm} disabled={updateMutation.isPending} /> : doc.name}
              </td>
              <td className={styles.td}>{doc.email}</td>
              <td className={styles.td}>
                {editId === doc.id
                  ? <select value={editDeptId} onChange={(e) => setEditDeptId(e.target.value)} className={styles.selectSm} disabled={updateMutation.isPending}>
                      {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                    </select>
                  : doc.department_name}
              </td>
              <td className={styles.td}>
                {editId === doc.id ? <input value={editLicense} onChange={(e) => setEditLicense(e.target.value)} maxLength={50} className={styles.inputSm} disabled={updateMutation.isPending} /> : doc.license_number}
              </td>
              <td className={styles.td}>
                <span className={doc.is_active ? styles.active : styles.inactive}>{doc.is_active ? '활성' : '비활성'}</span>
              </td>
              <td className={styles.td}>
                {editId === doc.id ? (
                  <>
                    <button onClick={() => handleEditSave(doc)} className={styles.btnSave} disabled={updateMutation.isPending}>저장</button>
                    <button onClick={() => setEditId(null)} className={styles.btnCancel} disabled={updateMutation.isPending}>취소</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => handleEditStart(doc)} className={styles.btnEdit} disabled={isBusy}>수정</button>
                    <button onClick={() => toggleActiveMutation.mutate({ id: doc.id, is_active: !doc.is_active })} className={styles.btnToggle} disabled={isBusy}>
                      {doc.is_active ? '비활성화' : '활성화'}
                    </button>
                    <button onClick={() => resetPasswordMutation.mutate(doc.id)} className={styles.btnReset} disabled={isBusy}>비밀번호 초기화</button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {doctors.length === 0 && <p className={styles.empty}>등록된 의사가 없습니다.</p>}
    </div>
  )
}
