import Link from 'next/link'

export default function AdminPage() {
  return (
    <main style={{ maxWidth: 600, margin: '2rem auto', padding: '0 1rem' }}>
      <h1>관리자 대시보드</h1>
      <nav>
        <ul style={{ listStyle: 'none', padding: 0, marginTop: '1rem' }}>
          <li style={{ marginBottom: '0.5rem' }}>
            <Link href="/admin/departments">진료과목 관리</Link>
          </li>
          <li style={{ marginBottom: '0.5rem' }}>
            <Link href="/admin/rooms">진료실 관리</Link>
          </li>
          <li style={{ marginBottom: '0.5rem' }}>
            <Link href="/admin/doctors">의사 계정 관리</Link>
          </li>
        </ul>
      </nav>
    </main>
  )
}
