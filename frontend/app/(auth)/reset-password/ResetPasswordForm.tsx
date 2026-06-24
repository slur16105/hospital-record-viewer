'use client'

import { createClient } from '@/lib/supabase/client'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './ResetPasswordForm.module.css'

const PASSWORD_REGEX = /^(?=.*[a-zA-Z])(?=.*[0-9]).{8,}$/

export default function ResetPasswordForm() {
  const router = useRouter()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (!PASSWORD_REGEX.test(password)) {
      setError('비밀번호는 8자 이상, 영문+숫자 조합이어야 합니다')
      return
    }
    if (password !== confirmPassword) {
      setError('비밀번호가 일치하지 않습니다')
      return
    }

    setLoading(true)
    const supabase = createClient()
    const { error: sbError } = await supabase.auth.updateUser({ password })

    if (sbError) {
      setError('비밀번호 변경에 실패했습니다. 재설정 링크가 만료되었을 수 있습니다.')
      setLoading(false)
      return
    }

    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>새 비밀번호 설정</h1>
        <p className={styles.subtitle}>새로운 비밀번호를 입력해 주세요</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              새 비밀번호
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
              placeholder="8자 이상, 영문+숫자 조합"
              required
              disabled={loading}
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="confirmPassword" className={styles.label}>
              비밀번호 확인
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={styles.input}
              placeholder="비밀번호를 다시 입력하세요"
              required
              disabled={loading}
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button type="submit" className={styles.button} disabled={loading}>
            {loading ? '변경 중...' : '변경 완료'}
          </button>
        </form>
      </div>
    </div>
  )
}
