// 인증 전용 프록시 (Story 9.1, AD-6).
// 여기서는 "누구인지(세션)"만 판정한다 — "무엇을 할 수 있는지(인가)"는
// 백엔드가 permissions로 판정하고 403을 반환한다. 역할별 경로 매칭은 제거됨.

import { createServerClient } from '@supabase/ssr'
import { type NextRequest, NextResponse } from 'next/server'

// 비로그인으로 접근 가능한 경로 (비밀번호 재설정은 전 사용자 대상 — FR-1b)
const PUBLIC_PATHS = ['/login', '/forgot-password', '/reset-password']

export async function proxy(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value))
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const path = request.nextUrl.pathname
  const isPublicPath = PUBLIC_PATHS.some((p) => path === p || path.startsWith(`${p}/`))

  // 비인증 사용자가 보호 경로 접근 → /login으로 리다이렉트
  // 세션 쿠키가 있으면 만료된 세션, 없으면 미로그인
  if (!user && !isPublicPath) {
    const loginUrl = new URL('/login', request.url)
    const hasAuthCookie = request.cookies
      .getAll()
      .some((c) => c.name.startsWith('sb-') && c.name.endsWith('-auth-token'))
    if (hasAuthCookie) loginUrl.searchParams.set('expired', '1')
    return redirectWithCookies(loginUrl, supabaseResponse)
  }

  if (user) {
    const { data: profile } = await supabase
      .from('user_profiles')
      .select('must_change_password')
      .eq('user_id', user.id)
      .single()

    // 임시 비밀번호 상태: /change-password 외 모든 경로 차단
    if (profile?.must_change_password === true && path !== '/change-password') {
      return redirectWithCookies(new URL('/change-password', request.url), supabaseResponse)
    }

    // 로그인 상태로 /login·/forgot-password 접근 → 홈(권한 기반 랜딩)으로
    if (path === '/login' || path === '/forgot-password') {
      return redirectWithCookies(new URL('/', request.url), supabaseResponse)
    }
  }

  return supabaseResponse
}

function redirectWithCookies(url: URL, supabaseResponse: NextResponse): NextResponse {
  const redirectResponse = NextResponse.redirect(url)
  supabaseResponse.cookies.getAll().forEach((cookie) => {
    redirectResponse.cookies.set(cookie.name, cookie.value)
  })
  return redirectResponse
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
}
