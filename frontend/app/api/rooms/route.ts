import { createClient } from '@/lib/supabase/server'
import { NextRequest, NextResponse } from 'next/server'

const FASTAPI_URL = process.env.FASTAPI_URL

async function getAccessToken(): Promise<string | null> {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? null
}

export async function GET() {
  if (!FASTAPI_URL) return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  const token = await getAccessToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  try {
    const res = await fetch(`${FASTAPI_URL}/api/rooms`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 })
  }
}

export async function POST(request: NextRequest) {
  if (!FASTAPI_URL) return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  const token = await getAccessToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await request.json()
  try {
    const res = await fetch(`${FASTAPI_URL}/api/rooms`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 })
  }
}
