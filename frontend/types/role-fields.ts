// role_fields 테이블(supabase/migrations/00010_rbac_core_schema.sql) 대응 타입.
// AD-12: DynamicForm(단일 동적 폼 렌더러)과 field-validation이 공유하는 정의.

export type FieldType =
  | 'text'
  | 'number'
  | 'date'
  | 'boolean'
  | 'phone'
  | 'email'
  | 'select'
  | 'multiselect'
  | 'reference'
  | 'json'

/** validation JSONB — 프론트(즉시 피드백)·백엔드(강제)가 같은 어휘를 해석한다 (AD-12) */
export interface FieldValidation {
  min_length?: number
  max_length?: number
  pattern?: string
  min?: number
  max?: number
}

/** options JSONB — select/multiselect: choices, reference: table/label_column */
export interface FieldOptions {
  /** select·multiselect 선택지. 문자열 또는 {value,label} 형태 모두 허용 */
  choices?: (string | { value: string; label: string })[]
  /** reference 대상 테이블 (조회는 부모 컴포넌트가 BFF 경유로 수행) */
  table?: string
  label_column?: string
}

export interface RoleField {
  id?: string
  role_id?: string
  field_key: string
  label: string
  field_type: FieldType
  is_required: boolean
  is_unique: boolean
  is_searchable: boolean
  sort_order: number
  default_value: string | null
  placeholder: string | null
  help_text: string | null
  validation: FieldValidation | null
  options: FieldOptions | null
  is_active: boolean
}

/** reference 타입 select 선택지 — 부모가 조회해 DynamicForm에 주입 */
export interface ReferenceOption {
  value: string
  label: string
}
