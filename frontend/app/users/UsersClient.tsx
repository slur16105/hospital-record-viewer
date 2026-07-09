'use client'

// Story 8.1: 통합 사용자 관리 — 목록·검색(q)·역할 필터·활성 상태

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useState } from 'react'
import type { RoleSummary, UserSummary } from '@/types/rbac'
import styles from './UsersClient.module.css'

export default function UsersClient() {
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  const [roleId, setRoleId] = useState('')
  const [activeFilter, setActiveFilter] = useState('')

  const { data: roles = [] } = useQuery<RoleSummary[]>({
    queryKey: ['roles'],
    queryFn: async () => {
      const res = await fetch('/api/roles')
      if (!res.ok) throw new Error('역할 목록 조회 실패')
      return res.json()
    },
  })

  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (roleId) params.set('role_id', roleId)
  if (activeFilter) params.set('is_active', activeFilter)
  const queryString = params.toString()

  const { data: users = [], isLoading, isError } = useQuery<UserSummary[]>({
    queryKey: ['users', q, roleId, activeFilter],
    queryFn: async () => {
      const res = await fetch(`/api/users${queryString ? `?${queryString}` : ''}`)
      if (!res.ok) throw new Error('사용자 목록 조회 실패')
      return res.json()
    },
  })

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setQ(search.trim())
  }

  return (
    <div className={styles.container}>
      <div className={styles.headerRow}>
        <h1 className={styles.title}>사용자 관리</h1>
        <Link href="/users/new" className={styles.btnPrimary}>
          + 계정 발급
        </Link>
      </div>

      <form onSubmit={handleSearch} className={styles.filterRow}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="이름·이메일·검색 대상 필드 검색"
          className={styles.input}
        />
        <select
          value={roleId}
          onChange={(e) => setRoleId(e.target.value)}
          className={styles.select}
        >
          <option value="">전체 역할</option>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
          className={styles.select}
        >
          <option value="">전체 상태</option>
          <option value="true">활성</option>
          <option value="false">비활성</option>
        </select>
        <button type="submit" className={styles.btnSearch}>
          검색
        </button>
      </form>

      {isLoading && <p className={styles.loading}>로딩 중...</p>}
      {isError && <p className={styles.error}>사용자 목록을 불러오지 못했습니다.</p>}

      {!isLoading && !isError && (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>이름</th>
                <th className={styles.th}>이메일</th>
                <th className={styles.th}>역할</th>
                <th className={styles.th}>상태</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.user_id} className={styles.tr}>
                  <td className={styles.td}>
                    <Link href={`/users/${user.user_id}`} className={styles.userLink}>
                      {user.name}
                    </Link>
                  </td>
                  <td className={styles.td}>{user.email}</td>
                  <td className={styles.td}>
                    {user.roles.map((role) => (
                      <span
                        key={role.id}
                        className={role.is_primary ? styles.roleBadgePrimary : styles.roleBadge}
                        title={role.is_primary ? '기본 역할' : undefined}
                      >
                        {role.name}
                      </span>
                    ))}
                  </td>
                  <td className={styles.td}>
                    <span className={user.is_active ? styles.active : styles.inactive}>
                      {user.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <p className={styles.empty}>조건에 맞는 사용자가 없습니다.</p>}
        </>
      )}
    </div>
  )
}
