'use client'

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import ForbiddenNotice from '@/components/ForbiddenNotice'
import styles from './AccessLogsClient.module.css'

interface AccessLog {
  id: string
  user_id: string
  accessor_name: string
  record_id: string | null
  patient_name: string
  action: string
  ip_address: string | null
  created_at: string
}

interface AccessLogPage {
  data: AccessLog[]
  total: number
  page: number
  page_size: number
}

// 알려진 액션만 한글 라벨 — 그 외 액션은 원문 문자열 그대로 표시 (enum 2종 가정 없음)
const ACTION_LABELS: Record<string, string> = {
  view_list: '목록 조회',
  view_detail: '상세 조회',
  role_change: '역할 변경',
}

const RESOURCE_TYPE_OPTIONS = [
  { value: '', label: '전체' },
  { value: 'medical_record', label: '진료기록' },
  { value: 'user', label: '사용자' },
]

function formatDatetime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export default function AccessLogsClient() {
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [resourceType, setResourceType] = useState('')
  const [appliedFrom, setAppliedFrom] = useState('')
  const [appliedTo, setAppliedTo] = useState('')
  const [appliedResourceType, setAppliedResourceType] = useState('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const queryKey = ['access-logs', appliedFrom, appliedTo, appliedResourceType, page]

  const { data, isLoading, error } = useQuery<AccessLogPage>({
    queryKey,
    queryFn: async () => {
      const params = new URLSearchParams()
      params.set('page', String(page))
      params.set('page_size', String(PAGE_SIZE))
      if (appliedFrom) params.set('from_date', appliedFrom)
      if (appliedTo) params.set('to_date', appliedTo)
      if (appliedResourceType) params.set('resource_type', appliedResourceType)
      const res = await fetch(`/api/access-logs?${params.toString()}`)
      if (res.status === 403) throw Object.assign(new Error('forbidden'), { status: 403 })
      if (!res.ok) throw new Error('접근 로그 조회 실패')
      return res.json()
    },
    retry: false,
  })

  const isForbidden = (error as (Error & { status?: number }) | null)?.status === 403

  const logs = data?.data ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function handleSearch() {
    setAppliedFrom(fromDate)
    setAppliedTo(toDate)
    setAppliedResourceType(resourceType)
    setPage(1)
  }

  function handleReset() {
    setFromDate('')
    setToDate('')
    setResourceType('')
    setAppliedFrom('')
    setAppliedTo('')
    setAppliedResourceType('')
    setPage(1)
  }

  if (isForbidden) {
    return <ForbiddenNotice message="접근 로그를 볼 수 있는 권한이 없습니다." />
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>접근 로그 조회</h1>

      <div className={styles.filterRow}>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>시작일</label>
          <input
            type="date"
            className={styles.filterInput}
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>종료일</label>
          <input
            type="date"
            className={styles.filterInput}
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
          />
        </div>
        <div className={styles.filterGroup}>
          <label className={styles.filterLabel}>대상 유형</label>
          <select
            className={styles.filterInput}
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
          >
            {RESOURCE_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <button className={styles.btnSearch} onClick={handleSearch}>
          조회
        </button>
        <button className={styles.btnReset} onClick={handleReset}>
          초기화
        </button>
      </div>

      {error && <p className={styles.error}>{(error as Error).message}</p>}

      {isLoading ? (
        <p className={styles.loading}>로딩 중...</p>
      ) : logs.length === 0 ? (
        <p className={styles.empty}>접근 로그가 없습니다.</p>
      ) : (
        <>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>일시</th>
                <th className={styles.th}>접근자</th>
                <th className={styles.th}>환자</th>
                <th className={styles.th}>액션</th>
                <th className={styles.th}>IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className={styles.tr}>
                  <td className={styles.td}>{formatDatetime(log.created_at)}</td>
                  <td className={styles.td}>{log.accessor_name || '-'}</td>
                  <td className={styles.td}>{log.patient_name || '-'}</td>
                  <td className={styles.td}>
                    <span className={styles.actionBadge}>
                      {ACTION_LABELS[log.action] ?? log.action}
                    </span>
                  </td>
                  <td className={styles.td}>{log.ip_address ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className={styles.pagination}>
            <button
              className={styles.btnPage}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              이전
            </button>
            <span className={styles.pageInfo}>
              {page} / {totalPages} (총 {total}건)
            </span>
            <button
              className={styles.btnPage}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              다음
            </button>
          </div>
        </>
      )}
    </div>
  )
}
