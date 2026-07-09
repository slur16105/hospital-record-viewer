// 권한 없는 화면 직접 접근 시 안내 (Story 9.2).
// 백엔드가 403을 반환한 경우 각 화면이 이 공용 컴포넌트를 렌더링한다.

import Link from 'next/link'

export default function ForbiddenNotice({ message }: { message?: string }) {
  return (
    <div style={{ maxWidth: 480, margin: '4rem auto', textAlign: 'center' }}>
      <h1 style={{ fontSize: '1.25rem', marginBottom: '0.75rem' }}>접근 권한이 없습니다</h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>
        {message ?? '이 화면을 볼 수 있는 권한이 없습니다. 필요하다면 관리자에게 문의하세요.'}
      </p>
      <Link href="/" style={{ color: 'var(--color-text-link)' }}>
        홈으로 돌아가기
      </Link>
    </div>
  )
}
