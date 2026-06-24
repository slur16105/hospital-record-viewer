'use client'

import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './RoleLayout.module.css'

interface Props {
  roleName: string
  children: React.ReactNode
}

export default function RoleLayout({ roleName, children }: Props) {
  const router = useRouter()
  const [loggingOut, setLoggingOut] = useState(false)

  async function handleLogout() {
    setLoggingOut(true)
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <span className={styles.roleName}>{roleName}</span>
        <button
          onClick={handleLogout}
          disabled={loggingOut}
          className={styles.logoutButton}
        >
          {loggingOut ? '로그아웃 중...' : '로그아웃'}
        </button>
      </header>
      <main className={styles.content}>{children}</main>
    </div>
  )
}
