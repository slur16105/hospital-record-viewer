'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import styles from './RoomsClient.module.css'

interface Department {
  id: string
  name: string
  is_active: boolean
}

interface Room {
  id: string
  room_number: string
  department_id: string
  department_name: string
  is_active: boolean
}

function extractErrorMessage(data: { detail?: unknown }, fallback: string): string {
  if (!data.detail) return fallback
  if (Array.isArray(data.detail)) {
    return data.detail.map((e: { msg?: string }) => e.msg ?? '').join(', ') || fallback
  }
  return String(data.detail)
}

export default function RoomsClient() {
  const queryClient = useQueryClient()
  const [newRoomNumber, setNewRoomNumber] = useState('')
  const [newDeptId, setNewDeptId] = useState('')
  const [formError, setFormError] = useState('')
  const [editId, setEditId] = useState<string | null>(null)
  const [editRoomNumber, setEditRoomNumber] = useState('')
  const [editDeptId, setEditDeptId] = useState('')
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

  const { data: rooms = [], isLoading } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: async () => {
      const res = await fetch('/api/rooms')
      if (!res.ok) throw new Error('목록 조회 실패')
      return res.json()
    },
  })

  const createMutation = useMutation({
    mutationFn: async ({ room_number, department_id }: { room_number: string; department_id: string }) => {
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_number, department_id }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '생성 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rooms'] })
      setNewRoomNumber('')
      setNewDeptId('')
      setFormError('')
    },
    onError: (err: Error) => setFormError(err.message),
  })

  const updateNameMutation = useMutation({
    mutationFn: async ({ id, room_number, department_id }: { id: string; room_number: string; department_id: string }) => {
      const res = await fetch(`/api/rooms/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room_number, department_id }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '수정 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rooms'] })
      setEditId(null)
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) => {
      const res = await fetch(`/api/rooms/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(extractErrorMessage(data, '상태 변경 실패'))
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rooms'] })
      setError('')
    },
    onError: (err: Error) => setError(err.message),
  })

  function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    if (!newRoomNumber.trim()) { setFormError('진료실 번호는 필수 항목입니다'); return }
    if (!newDeptId) { setFormError('소속 진료과목은 필수 항목입니다'); return }
    createMutation.mutate({ room_number: newRoomNumber.trim(), department_id: newDeptId })
  }

  function handleEditStart(room: Room) {
    if (updateNameMutation.isPending || toggleActiveMutation.isPending) return
    setEditId(room.id)
    setEditRoomNumber(room.room_number)
    setEditDeptId(room.department_id)
    setError('')
  }

  function handleEditSave(room: Room) {
    if (!editRoomNumber.trim()) return
    setError('')
    updateNameMutation.mutate({ id: room.id, room_number: editRoomNumber.trim(), department_id: editDeptId })
  }

  function handleToggleActive(room: Room) {
    setError('')
    toggleActiveMutation.mutate({ id: room.id, is_active: !room.is_active })
  }

  const isBusy = updateNameMutation.isPending || toggleActiveMutation.isPending

  if (isLoading) return <p className={styles.loading}>로딩 중...</p>

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>진료실 관리</h1>

      <form onSubmit={handleCreate} className={styles.createForm}>
        <input
          value={newRoomNumber}
          onChange={(e) => setNewRoomNumber(e.target.value)}
          placeholder="진료실 번호 (예: 101)"
          maxLength={20}
          className={styles.input}
          disabled={createMutation.isPending}
        />
        <select
          value={newDeptId}
          onChange={(e) => setNewDeptId(e.target.value)}
          className={styles.select}
          disabled={createMutation.isPending}
        >
          <option value="">진료과목 선택</option>
          {activeDepts.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <button type="submit" className={styles.button} disabled={createMutation.isPending}>
          {createMutation.isPending ? '등록 중...' : '+ 등록'}
        </button>
      </form>

      {formError && <p className={styles.error}>{formError}</p>}
      {error && <p className={styles.error}>{error}</p>}

      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>진료실 번호</th>
            <th className={styles.th}>소속 진료과목</th>
            <th className={styles.th}>상태</th>
            <th className={styles.th}>관리</th>
          </tr>
        </thead>
        <tbody>
          {rooms.map((room) => (
            <tr key={room.id} className={styles.tr}>
              <td className={styles.td}>
                {editId === room.id ? (
                  <input
                    value={editRoomNumber}
                    onChange={(e) => setEditRoomNumber(e.target.value)}
                    maxLength={20}
                    className={styles.input}
                    disabled={updateNameMutation.isPending}
                  />
                ) : (
                  room.room_number
                )}
              </td>
              <td className={styles.td}>
                {editId === room.id ? (
                  <select
                    value={editDeptId}
                    onChange={(e) => setEditDeptId(e.target.value)}
                    className={styles.select}
                    disabled={updateNameMutation.isPending}
                  >
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                ) : (
                  room.department_name
                )}
              </td>
              <td className={styles.td}>
                <span className={room.is_active ? styles.active : styles.inactive}>
                  {room.is_active ? '활성' : '비활성'}
                </span>
              </td>
              <td className={styles.td}>
                {editId === room.id ? (
                  <>
                    <button
                      onClick={() => handleEditSave(room)}
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
                      onClick={() => handleEditStart(room)}
                      className={styles.btnEdit}
                      disabled={isBusy}
                    >
                      수정
                    </button>
                    <button
                      onClick={() => handleToggleActive(room)}
                      className={styles.btnToggle}
                      disabled={isBusy}
                    >
                      {room.is_active ? '비활성화' : '활성화'}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {rooms.length === 0 && (
        <p className={styles.empty}>등록된 진료실이 없습니다.</p>
      )}
    </div>
  )
}
