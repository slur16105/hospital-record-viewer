import type { Metadata } from 'next'
import QueryProvider from '@/providers/QueryProvider'
import '@/styles/globals.css'

export const metadata: Metadata = {
  title: 'Hospital Record Viewer',
  description: '병원 진료기록 조회 시스템',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="ko">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  )
}
