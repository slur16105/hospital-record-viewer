'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './SearchClient.module.css'

interface PatientSearchItem {
  id: string
  user_id: string
  name: string
  birth_date: string
  phone: string
}

export default function SearchClient() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [queryName, setQueryName] = useState('')
  const [queryBirthDate, setQueryBirthDate] = useState('')

  const canSearch = name.trim() || birthDate

  const { data: patients = [], isLoading, error } = useQuery<PatientSearchItem[]>({
    queryKey: ['patient-search', queryName, queryBirthDate],
    queryFn: async () => {
      if (!queryName && !queryBirthDate) return []
      const params = new URLSearchParams()
      if (queryName) params.set('name', queryName)
      if (queryBirthDate) params.set('birth_date', queryBirthDate)
      const res = await fetch(`/api/doctor/patients/search?${params.toString()}`)
      if (!res.ok) throw new Error('검색 실패')
      return res.json()
    },
    enabled: submitted,
  })

  function handleSearch() {
    setQueryName(name.trim())
    setQueryBirthDate(birthDate)
    setSubmitted(true)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && canSearch) handleSearch()
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link href="/doctor" className={styles.back}>← 담당 환자 목록</Link>
        <h1 className={styles.title}>환자 검색</h1>
      </div>

      <div className={styles.filterRow}>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>이름</label>
          <input
            type="text"
            className={styles.filterInput}
            placeholder="환자 이름"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>생년월일</label>
          <input
            type="date"
            className={styles.filterInput}
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
          />
        </div>
        <button
          className={styles.btnSearch}
          onClick={handleSearch}
          disabled={!canSearch}
        >
          검색
        </button>
      </div>

      {!submitted && (
        <p className={styles.hint}>이름 또는 생년월일로 검색하세요.</p>
      )}

      {error && <p className={styles.error}>{(error as Error).message}</p>}

      {submitted && isLoading ? (
        <p className={styles.loading}>검색 중...</p>
      ) : submitted && patients.length === 0 ? (
        <p className={styles.empty}>검색 결과가 없습니다.</p>
      ) : submitted ? (
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>이름</th>
              <th className={styles.th}>생년월일</th>
              <th className={styles.th}>연락처</th>
            </tr>
          </thead>
          <tbody>
            {patients.map((p) => (
              <tr
                key={p.id}
                className={styles.tr}
                onClick={() => router.push(`/doctor/patients/${p.id}/records`)}
              >
                <td className={styles.td}>{p.name}</td>
                <td className={styles.td}>{p.birth_date}</td>
                <td className={styles.td}>{p.phone}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  )
}
