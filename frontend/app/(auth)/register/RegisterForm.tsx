'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import styles from './RegisterForm.module.css'

interface FormState {
  name: string
  birthDate: string
  email: string
  password: string
  phone: string
}

interface FormErrors {
  name?: string
  birthDate?: string
  email?: string
  password?: string
  phone?: string
  form?: string
}

const PASSWORD_REGEX = /^(?=.*[a-zA-Z])(?=.*[0-9]).{8,}$/

export default function RegisterForm() {
  const router = useRouter()
  const [form, setForm] = useState<FormState>({
    name: '',
    birthDate: '',
    email: '',
    password: '',
    phone: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  function setField(field: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  function validate(): boolean {
    const newErrors: FormErrors = {}
    if (!form.name.trim()) newErrors.name = '필수 항목입니다'
    if (!form.birthDate) newErrors.birthDate = '필수 항목입니다'
    if (!form.email.trim()) newErrors.email = '필수 항목입니다'
    if (!form.password) {
      newErrors.password = '필수 항목입니다'
    } else if (!PASSWORD_REGEX.test(form.password)) {
      newErrors.password = '비밀번호는 8자 이상, 영문+숫자 조합이어야 합니다'
    }
    if (!form.phone.trim()) newErrors.phone = '필수 항목입니다'
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return

    setLoading(true)
    setErrors({})

    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          name: form.name,
          birth_date: form.birthDate,
          phone: form.phone,
        }),
      })

      if (res.status === 201) {
        setSuccess(true)
        setTimeout(() => router.push('/login'), 1500)
      } else if (res.status === 409) {
        setErrors({ form: '이미 가입된 이메일입니다' })
      } else {
        const data = await res.json().catch(() => ({}))
        setErrors({ form: data.error ?? '회원가입에 실패했습니다. 다시 시도해주세요.' })
      }
    } catch {
      setErrors({ form: '네트워크 오류가 발생했습니다. 다시 시도해주세요.' })
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className={styles.container}>
        <div className={styles.card}>
          <p className={styles.successMessage}>가입이 완료되었습니다</p>
          <p className={styles.successSub}>로그인 화면으로 이동합니다...</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={styles.title}>환자 회원가입</h1>
        <p className={styles.subtitle}>병원 진료기록 조회 시스템</p>

        <form onSubmit={handleSubmit} className={styles.form} noValidate>
          <div className={styles.field}>
            <label htmlFor="name" className={styles.label}>이름</label>
            <input
              id="name"
              type="text"
              value={form.name}
              onChange={setField('name')}
              className={`${styles.input}${errors.name ? ` ${styles.inputError}` : ''}`}
              placeholder="이름을 입력하세요"
              disabled={loading}
              autoComplete="name"
            />
            {errors.name && <p className={styles.fieldError}>{errors.name}</p>}
          </div>

          <div className={styles.field}>
            <label htmlFor="birthDate" className={styles.label}>생년월일</label>
            <input
              id="birthDate"
              type="date"
              value={form.birthDate}
              onChange={setField('birthDate')}
              className={`${styles.input}${errors.birthDate ? ` ${styles.inputError}` : ''}`}
              disabled={loading}
            />
            {errors.birthDate && <p className={styles.fieldError}>{errors.birthDate}</p>}
          </div>

          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>이메일</label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={setField('email')}
              className={`${styles.input}${errors.email ? ` ${styles.inputError}` : ''}`}
              placeholder="이메일을 입력하세요"
              disabled={loading}
              autoComplete="email"
            />
            {errors.email && <p className={styles.fieldError}>{errors.email}</p>}
          </div>

          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>비밀번호</label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={setField('password')}
              className={`${styles.input}${errors.password ? ` ${styles.inputError}` : ''}`}
              placeholder="8자 이상, 영문+숫자 조합"
              disabled={loading}
              autoComplete="new-password"
            />
            {errors.password && <p className={styles.fieldError}>{errors.password}</p>}
          </div>

          <div className={styles.field}>
            <label htmlFor="phone" className={styles.label}>연락처</label>
            <input
              id="phone"
              type="tel"
              value={form.phone}
              onChange={setField('phone')}
              className={`${styles.input}${errors.phone ? ` ${styles.inputError}` : ''}`}
              placeholder="연락처를 입력하세요"
              disabled={loading}
              autoComplete="tel"
            />
            {errors.phone && <p className={styles.fieldError}>{errors.phone}</p>}
          </div>

          {errors.form && <p className={styles.error}>{errors.form}</p>}

          <button type="submit" className={styles.button} disabled={loading}>
            {loading ? '가입 중...' : '가입'}
          </button>
        </form>

        <p className={styles.loginLink}>
          이미 계정이 있으신가요?{' '}
          <a href="/login">로그인</a>
        </p>
      </div>
    </div>
  )
}
