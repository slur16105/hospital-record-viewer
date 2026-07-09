'use client'

// 임시 비밀번호 / 초기화된 비밀번호 1회 표시 모달 (Story 8.2·8.1).
// 닫으면 다시 볼 수 없다는 안내와 복사 버튼을 제공한다.

import { useState } from 'react'
import styles from './PasswordModal.module.css'

interface PasswordModalProps {
  title: string
  password: string
  onClose: () => void
}

export default function PasswordModal({ title, password, onClose }: PasswordModalProps) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-label={title}>
      <div className={styles.modal}>
        <h2 className={styles.title}>{title}</h2>
        <p className={styles.warning}>
          이 비밀번호는 지금 한 번만 표시됩니다. 닫기 전에 복사해 전달하세요.
        </p>
        <div className={styles.passwordRow}>
          <code className={styles.password}>{password}</code>
          <button className={styles.btnCopy} onClick={handleCopy}>
            {copied ? '복사됨!' : '복사'}
          </button>
        </div>
        <button className={styles.btnClose} onClick={onClose}>
          확인 후 닫기
        </button>
      </div>
    </div>
  )
}
