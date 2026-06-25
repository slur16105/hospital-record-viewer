import { cookies } from 'next/headers'

/**
 * 쿠키에서 access_token을 직접 파싱해 반환한다.
 *
 * getUser()(Supabase Auth 서버 네트워크 왕복)를 호출하지 않고, @supabase/ssr이
 * 저장한 인증 쿠키(`sb-<ref>-auth-token`)를 직접 읽어 access_token만 추출한다.
 * 토큰 유효성(서명·만료·audience)은 이 토큰을 받는 FastAPI 백엔드가
 * SUPABASE_JWT_SECRET으로 검증하므로, 프론트엔드에서 추가 검증 왕복은 불필요하다.
 *
 * 참고: getSession()은 서버 컨텍스트에서 선행 getUser() 없이는 세션을 안정적으로
 * 복원하지 못하므로 사용하지 않는다. 쿠키 직접 파싱이 결정적이고 네트워크 비용이 없다.
 */
export async function getAccessToken(): Promise<string | null> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  if (!supabaseUrl) return null

  // 프로젝트 ref 추출: https://<ref>.supabase.co
  const ref = new URL(supabaseUrl).hostname.split('.')[0]
  const cookieName = `sb-${ref}-auth-token`

  const cookieStore = await cookies()

  // 단일 쿠키 또는 청크(.0, .1, ...) 형태를 모두 처리
  let raw = cookieStore.get(cookieName)?.value
  if (raw === undefined) {
    const chunks: string[] = []
    for (let i = 0; ; i++) {
      const chunk = cookieStore.get(`${cookieName}.${i}`)?.value
      if (chunk === undefined) break
      chunks.push(chunk)
    }
    if (chunks.length === 0) return null
    raw = chunks.join('')
  }

  // @supabase/ssr은 값 앞에 'base64-' 접두사를 붙이고 base64url로 인코딩한다
  try {
    const json = raw.startsWith('base64-')
      ? Buffer.from(raw.slice('base64-'.length), 'base64url').toString('utf-8')
      : decodeURIComponent(raw)
    const session = JSON.parse(json)
    return session?.access_token ?? null
  } catch {
    return null
  }
}
