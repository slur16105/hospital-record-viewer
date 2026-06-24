'use client'

import { createClient } from '@/lib/supabase/client'
import { useState } from 'react'
import styles from './ForgotPasswordForm.module.css'

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')

    const supabase = createClient()
    const redirectTo = `${window.location.origin}/api/auth/callback?next=/reset-password`
    const { error: sbError } = await supabase.auth.resetPasswordForEmail(email, { redirectTo })

    if (sbError) {
      setError('이메일 전송에 실패했습니다. 다시 시도해 주세요.')
      setLoading(false)
      return
    }

    setSubmitted(true)
  }

  if (submitted) {
    return (
      <div className={styles.container}>
        <div className={styles.card}>
          <h1 className={styles.title}>이메일 발송 완료</h1>
          <p className={styles.successMessage}>
            비밀번호 재설정 이메일을 발송했습니다. 이메일을 확인해 주세요.
          </p>
          <p className={styles.backLink}>
            <a href="/login">로그인으로 돌아가기</a>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>비밀번호 찾기</h1>
        <p className={styles.subtitle}>가입 시 사용한 이메일을 입력하세요</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>
              이메일
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={styles.input}
              placeholder="이메일을 입력하세요"
              required
              disabled={loading}
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button type="submit" className={styles.button} disabled={loading}>
            {loading ? '전송 중...' : '재설정 이메일 보내기'}
          </button>
        </form>

        <p className={styles.backLink}>
          <a href="/login">로그인으로 돌아가기</a>
        </p>
      </div>
    </div>
  )
}
