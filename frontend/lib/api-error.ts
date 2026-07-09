// BFF 경유 FastAPI 오류 응답 해석 헬퍼 (RBAC 관리 화면 공용).
// detail이 문자열 / FastAPI validation 배열 / {field_key: 메시지} dict 세 형태를 처리한다.

export interface FieldErrorMap {
  [fieldKey: string]: string
}

/** 사람이 읽을 오류 메시지 추출 (detail이 dict면 값들을 이어붙임) */
export function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback
  const detail = (data as { detail?: unknown }).detail
  if (detail === undefined || detail === null) {
    const error = (data as { error?: unknown }).error
    return typeof error === 'string' ? error : fallback
  }
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (
      detail
        .map((e: { msg?: string }) => e.msg ?? '')
        .filter(Boolean)
        .join(', ') || fallback
    )
  }
  if (typeof detail === 'object') {
    return Object.values(detail as Record<string, unknown>).map(String).join(', ') || fallback
  }
  return fallback
}

/**
 * 서버 400 응답의 detail이 {field_key: 메시지} dict면 DynamicForm errors로 변환.
 * dict 형태가 아니면 null.
 */
export function extractFieldErrors(data: unknown): FieldErrorMap | null {
  if (!data || typeof data !== 'object') return null
  const detail = (data as { detail?: unknown }).detail
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null
  const entries = Object.entries(detail as Record<string, unknown>)
  if (entries.length === 0) return null
  if (!entries.every(([, v]) => typeof v === 'string')) return null
  return Object.fromEntries(entries) as FieldErrorMap
}
