import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { NextRequest, NextResponse } from 'next/server'

const PASSWORD_REGEX = /^(?=.*[a-zA-Z])(?=.*[0-9]).{8,}$/

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  const { password } = body

  if (!password || !PASSWORD_REGEX.test(password)) {
    return NextResponse.json(
      { error: '비밀번호는 8자 이상, 영문+숫자 조합이어야 합니다' },
      { status: 400 }
    )
  }

  const cookieStore = await cookies()
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        },
      },
    }
  )

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  if (userError || !user) {
    return NextResponse.json({ error: '인증이 필요합니다' }, { status: 401 })
  }

  const { error: updateError } = await supabase.auth.updateUser({ password })
  if (updateError) {
    return NextResponse.json(
      { error: '비밀번호 변경에 실패했습니다' },
      { status: 500 }
    )
  }

  const { error: profileError } = await supabase
    .from('user_profiles')
    .update({ must_change_password: false })
    .eq('user_id', user.id)

  if (profileError) {
    return NextResponse.json(
      { error: '프로필 업데이트에 실패했습니다' },
      { status: 500 }
    )
  }

  return NextResponse.json({ success: true })
}
