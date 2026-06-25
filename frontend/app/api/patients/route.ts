import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

const FASTAPI_URL = process.env.FASTAPI_URL

export async function GET() {
  if (!FASTAPI_URL) return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })

  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  try {
    const res = await fetch(`${FASTAPI_URL}/api/patients`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 })
  }
}
