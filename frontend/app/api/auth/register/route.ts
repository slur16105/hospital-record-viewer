import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'

const PASSWORD_REGEX = /^(?=.*[a-zA-Z])(?=.*[0-9]).{8,}$/

function createAdminClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  )
}

export async function POST(request: NextRequest) {
  const body = await request.json()
  const { email, password, name, birth_date, phone } = body

  if (!email || !password || !name || !birth_date || !phone) {
    return NextResponse.json({ error: '필수 항목이 누락되었습니다' }, { status: 400 })
  }

  if (!PASSWORD_REGEX.test(password)) {
    return NextResponse.json(
      { error: '비밀번호는 8자 이상, 영문+숫자 조합이어야 합니다' },
      { status: 400 }
    )
  }

  const supabase = createAdminClient()

  const { data, error } = await supabase.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  })

  if (error) {
    const msg = error.message.toLowerCase()
    if (msg.includes('already registered') || msg.includes('already been registered') || msg.includes('duplicate')) {
      return NextResponse.json({ error: '이미 가입된 이메일입니다' }, { status: 409 })
    }
    return NextResponse.json({ error: error.message }, { status: 400 })
  }

  const userId = data.user.id

  const { error: profileError } = await supabase
    .from('user_profiles')
    .insert({ user_id: userId, role: 'patient', name })

  if (profileError) {
    await supabase.auth.admin.deleteUser(userId)
    return NextResponse.json({ error: profileError.message }, { status: 500 })
  }

  const { error: patientError } = await supabase
    .from('patients')
    .insert({ user_id: userId, birth_date, phone })

  if (patientError) {
    await supabase.auth.admin.deleteUser(userId)
    return NextResponse.json({ error: patientError.message }, { status: 500 })
  }

  return NextResponse.json({ ok: true }, { status: 201 })
}
