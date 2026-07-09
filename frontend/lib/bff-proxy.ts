// RBAC BFF 공용 프록시 헬퍼 (Epic 7·8).
// 기존 BFF 패턴(토큰 추출 → Bearer 프록시, 판정 없음)을 함수 하나로 축약한다.
// 인가 판정은 백엔드(FastAPI)가 담당하고, 여기서는 토큰 유무만 확인한다.

import { NextResponse } from 'next/server'
import { getAccessToken } from '@/lib/supabase/token'

interface ProxyOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  /** JSON 직렬화해 전달할 요청 본문 */
  body?: unknown
  /** 백엔드로 그대로 전달할 쿼리스트링 (예: request.nextUrl.searchParams) */
  searchParams?: URLSearchParams
}

/**
 * `${FASTAPI_URL}/api${path}`로 Bearer 토큰을 붙여 프록시하고
 * 백엔드 응답(JSON + status)을 그대로 반환한다.
 */
export async function proxyToBackend(
  path: string,
  { method = 'GET', body, searchParams }: ProxyOptions = {}
): Promise<NextResponse> {
  const fastapiUrl = process.env.FASTAPI_URL
  if (!fastapiUrl) {
    return NextResponse.json({ error: 'Server configuration error' }, { status: 500 })
  }

  const token = await getAccessToken()
  if (!token) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const query = searchParams && searchParams.size > 0 ? `?${searchParams.toString()}` : ''
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  try {
    const res = await fetch(`${fastapiUrl}/api${path}${query}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: 'no-store',
    })
    // 204 등 본문 없는 응답 대비 (null body status에는 본문을 실을 수 없다)
    if (res.status === 204 || res.status === 205 || res.status === 304) {
      return new NextResponse(null, { status: res.status })
    }
    const text = await res.text()
    const data = text ? JSON.parse(text) : null
    return NextResponse.json(data, { status: res.status })
  } catch {
    return NextResponse.json({ error: 'Failed to reach backend' }, { status: 502 })
  }
}
