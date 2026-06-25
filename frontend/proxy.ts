import { createServerClient } from '@supabase/ssr'
import { type NextRequest, NextResponse } from 'next/server'

const ROLE_HOME: Record<string, string> = {
  admin: '/admin',
  doctor: '/doctor',
  patient: '/patient',
}

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
  const isProtectedPath =
    path.startsWith('/admin') ||
    path.startsWith('/doctor') ||
    path.startsWith('/patient') ||
    path === '/change-password'
  const isAuthPath = path === '/login' || path === '/forgot-password'

  // /register 접근 차단 (관리자만 계정 생성)
  if (path.startsWith('/register')) {
    return NextResponse.rewrite(new URL('/not-found', request.url))
  }

  // 비인증 사용자가 보호 경로 접근 → /login으로 리다이렉트
  // 세션 쿠키가 있으면 만료된 세션, 없으면 미로그인
  if (!user && isProtectedPath) {
    const loginUrl = new URL('/login', request.url)
    const hasAuthCookie = request.cookies.getAll().some(
      (c) => c.name.startsWith('sb-') && c.name.endsWith('-auth-token')
    )
    if (hasAuthCookie) loginUrl.searchParams.set('expired', '1')
    return redirectWithCookies(loginUrl, supabaseResponse)
  }

  if (user) {
    const { data: profile } = await supabase
      .from('user_profiles')
      .select('role, must_change_password')
      .eq('user_id', user.id)
      .single()

    const role = profile?.role as 'admin' | 'doctor' | 'patient' | null
    const mustChangePw = profile?.must_change_password === true

    // 로그인된 사용자가 /login 또는 /register 접근 → 역할 홈으로 리다이렉트
    if (isAuthPath && role && ROLE_HOME[role]) {
      return redirectWithCookies(new URL(ROLE_HOME[role], request.url), supabaseResponse)
    }

    // 비의사 역할이 /change-password 접근 → 역할 홈으로 리다이렉트
    if (path === '/change-password' && role !== 'doctor') {
      const home = ROLE_HOME[role as string] ?? '/'
      return redirectWithCookies(new URL(home, request.url), supabaseResponse)
    }

    // doctor + must_change_password=true: /change-password 외 모든 경로 차단
    if (role === 'doctor' && mustChangePw && path !== '/change-password') {
      return redirectWithCookies(new URL('/change-password', request.url), supabaseResponse)
    }

    // 역할 불일치 시 → 자신의 역할 홈으로 리다이렉트
    if (role && ROLE_HOME[role]) {
      const wrongRole =
        (path.startsWith('/admin') && role !== 'admin') ||
        (path.startsWith('/doctor') && role !== 'doctor') ||
        (path.startsWith('/patient') && role !== 'patient')

      if (wrongRole) {
        return redirectWithCookies(new URL(ROLE_HOME[role], request.url), supabaseResponse)
      }
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
