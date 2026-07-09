'use client'

// 로그인 후 랜딩 (Story 9.1): /api/me permissions를 보고
// 첫 허용 메뉴(MENU_ITEMS 순서 기준)로 리다이렉트한다.
// 비로그인 접근은 proxy.ts가 /login으로 보낸다.

import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { MENU_ITEMS } from '@/lib/menu'
import { usePermissions } from '@/lib/permissions'

export default function Home() {
  const router = useRouter()
  const { hasAny, isLoading, isError } = usePermissions()

  const target = MENU_ITEMS.find((item) => hasAny(...item.permissions))?.href ?? null

  useEffect(() => {
    if (isLoading) return
    if (isError) {
      router.replace('/login')
      return
    }
    if (target) router.replace(target)
  }, [isLoading, isError, target, router])

  if (!isLoading && !isError && !target) {
    return (
      <p style={{ textAlign: 'center', marginTop: '4rem', color: 'var(--color-text-muted)' }}>
        접근 가능한 메뉴가 없습니다. 관리자에게 문의하세요.
      </p>
    )
  }

  return <p style={{ textAlign: 'center', marginTop: '4rem', color: 'var(--color-text-muted)' }}>이동 중...</p>
}
