import { NextRequest, NextResponse } from 'next/server'
import { getAccessToken } from '@/lib/supabase/token'

const FASTAPI_URL = process.env.FASTAPI_URL

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  if (!FASTAPI_URL) return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  const token = await getAccessToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { patientId } = await params
  const url = new URL(request.url)
  const page = url.searchParams.get('page') ?? '1'
  const pageSize = url.searchParams.get('page_size') ?? '20'

  try {
    // patientId = 환자의 user_id — 백엔드 목록 필터는 patient_user_id 기준 (00013)
    const res = await fetch(
      `${FASTAPI_URL}/api/medical-records?patient_user_id=${patientId}&page=${page}&page_size=${pageSize}`,
      { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }
    )
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 })
  }
}
