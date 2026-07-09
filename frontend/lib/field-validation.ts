// role_fields.validation JSON 규칙 해석기 (AD-12).
// 백엔드(backend/core/field_values.py)와 같은 규칙 어휘를 해석한다:
//   min_length / max_length / pattern / min / max + is_required + field_type 형식 검사.
// 프론트는 즉시 피드백용이며 강제는 백엔드가 담당한다 (AD-13).

import type { RoleField } from '@/types/role-fields'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_PATTERN = /^0\d{1,2}-?\d{3,4}-?\d{4}$/
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/

function isEmpty(value: unknown): boolean {
  if (value === undefined || value === null) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  return false
}

/** field_type별 형식 검사. 형식 위반 시 오류 메시지, 정상이면 null */
function validateFormat(field: RoleField, value: unknown): string | null {
  switch (field.field_type) {
    case 'number': {
      const num = typeof value === 'number' ? value : Number(value)
      if (Number.isNaN(num)) return '숫자를 입력해 주세요.'
      return null
    }
    case 'date': {
      const str = String(value)
      if (!DATE_PATTERN.test(str) || Number.isNaN(new Date(str).getTime())) {
        return '올바른 날짜 형식(YYYY-MM-DD)이 아닙니다.'
      }
      return null
    }
    case 'email':
      if (!EMAIL_PATTERN.test(String(value))) return '올바른 이메일 형식이 아닙니다.'
      return null
    case 'phone':
      if (!PHONE_PATTERN.test(String(value))) {
        return '올바른 전화번호 형식이 아닙니다. (예: 010-1234-5678)'
      }
      return null
    case 'multiselect':
      if (!Array.isArray(value)) return '항목을 선택해 주세요.'
      return null
    case 'json': {
      if (typeof value !== 'string') return null
      try {
        JSON.parse(value)
        return null
      } catch {
        return '올바른 JSON 형식이 아닙니다.'
      }
    }
    default:
      return null
  }
}

/** validation JSON 규칙(min_length/max_length/pattern/min/max) 검사 */
function validateRules(field: RoleField, value: unknown): string | null {
  const rules = field.validation
  if (!rules) return null

  const strValue = typeof value === 'string' ? value : String(value ?? '')

  if (rules.min_length !== undefined && strValue.length < rules.min_length) {
    return `최소 ${rules.min_length}자 이상 입력해 주세요.`
  }
  if (rules.max_length !== undefined && strValue.length > rules.max_length) {
    return `최대 ${rules.max_length}자까지 입력할 수 있습니다.`
  }
  if (rules.pattern !== undefined) {
    try {
      if (!new RegExp(rules.pattern).test(strValue)) {
        return '입력 형식이 올바르지 않습니다.'
      }
    } catch {
      // 잘못된 패턴 정의는 프론트에서 무시 (백엔드가 강제)
    }
  }
  if (rules.min !== undefined || rules.max !== undefined) {
    const num = typeof value === 'number' ? value : Number(value)
    if (!Number.isNaN(num)) {
      if (rules.min !== undefined && num < rules.min) {
        return `${rules.min} 이상의 값을 입력해 주세요.`
      }
      if (rules.max !== undefined && num > rules.max) {
        return `${rules.max} 이하의 값을 입력해 주세요.`
      }
    }
  }
  return null
}

/** 단일 필드 검증. 오류 메시지 또는 null */
export function validateFieldValue(field: RoleField, value: unknown): string | null {
  if (isEmpty(value)) {
    return field.is_required ? `${field.label}은(는) 필수 항목입니다.` : null
  }
  return validateFormat(field, value) ?? validateRules(field, value)
}

/**
 * 활성 필드 전체 검증 — { field_key: 한국어 오류 메시지 }.
 * 오류가 없으면 빈 객체를 반환한다.
 */
export function validateFieldValues(
  fields: RoleField[],
  values: Record<string, unknown>
): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const field of fields) {
    if (!field.is_active) continue
    const message = validateFieldValue(field, values[field.field_key])
    if (message) errors[field.field_key] = message
  }
  return errors
}
