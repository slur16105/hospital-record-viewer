'use client'

// 권한 기반 공용 레이아웃 (Story 9.2).
// 역할별 RoleLayout을 대체한다 — /api/me permissions로 메뉴 노출을 결정하고
// 접근 인가 자체는 백엔드가 판정한다 (AD-6).

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { MENU_ITEMS } from '@/lib/menu'
import { usePermissions } from '@/lib/permissions'
import styles from './AppLayout.module.css'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { me, hasAny, isLoading } = usePermissions()
  const [loggingOut, setLoggingOut] = useState(false)

  const visibleMenu = MENU_ITEMS.filter((item) => hasAny(...item.permissions))

  async function handleLogout() {
    setLoggingOut(true)
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <nav className={styles.nav}>
          {!isLoading &&
            visibleMenu.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={
                  pathname === item.href || pathname.startsWith(`${item.href}/`)
                    ? `${styles.navLink} ${styles.navLinkActive}`
                    : styles.navLink
                }
              >
                {item.label}
              </Link>
            ))}
        </nav>
        <div className={styles.right}>
          {me && (
            <span className={styles.userName}>
              {me.profile?.name ?? me.user.email}
              {me.primary_role && ` (${me.primary_role.name})`}
            </span>
          )}
          <button
            onClick={handleLogout}
            disabled={loggingOut}
            className={styles.logoutButton}
          >
            {loggingOut ? '로그아웃 중...' : '로그아웃'}
          </button>
        </div>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  )
}
