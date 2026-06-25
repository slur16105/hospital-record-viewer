import { NextRequest, NextResponse } from 'next/server'
import { getAccessToken } from '@/lib/supabase/token'

const FASTAPI_URL = process.env.FASTAPI_URL

export async function GET() {
  if (!FASTAPI_URL) return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  const token = await getAccessToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  try {
    const res = await fetch(`${FASTAPI_URL}/api/departments`, {
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
    const res = await fetch(`${FASTAPI_URL}/api/departments`, {
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
