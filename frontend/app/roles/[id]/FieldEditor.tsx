'use client'

// Story 7.4: role_fields 13개 속성 편집 폼.
// validation·options는 field_type에 따라 구조화된 입력으로 편집한다.

import { useState } from 'react'
import type {
  FieldOptions,
  FieldType,
  FieldValidation,
  RoleField,
} from '@/types/role-fields'
import styles from './FieldEditor.module.css'

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: 'text', label: '텍스트' },
  { value: 'number', label: '숫자' },
  { value: 'date', label: '날짜' },
  { value: 'boolean', label: '예/아니오' },
  { value: 'phone', label: '전화번호' },
  { value: 'email', label: '이메일' },
  { value: 'select', label: '단일 선택' },
  { value: 'multiselect', label: '다중 선택' },
  { value: 'reference', label: '참조(테이블)' },
  { value: 'json', label: 'JSON' },
]

const TEXTUAL_TYPES: FieldType[] = ['text', 'phone', 'email', 'json']

interface Choice {
  value: string
  label: string
}

export interface FieldEditorPayload {
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

interface FieldEditorProps {
  /** 수정 모드면 기존 필드, 추가 모드면 undefined */
  initial?: RoleField
  onSubmit: (payload: FieldEditorPayload) => void
  onCancel: () => void
  isPending: boolean
}

function toChoices(field?: RoleField): Choice[] {
  const choices = field?.options?.choices ?? []
  return choices.map((c) => (typeof c === 'string' ? { value: c, label: c } : { ...c }))
}

function numOrEmpty(value: number | undefined): string {
  return value === undefined ? '' : String(value)
}

export default function FieldEditor({ initial, onSubmit, onCancel, isPending }: FieldEditorProps) {
  const [fieldKey, setFieldKey] = useState(initial?.field_key ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [fieldType, setFieldType] = useState<FieldType>(initial?.field_type ?? 'text')
  const [isRequired, setIsRequired] = useState(initial?.is_required ?? false)
  const [isUnique, setIsUnique] = useState(initial?.is_unique ?? false)
  const [isSearchable, setIsSearchable] = useState(initial?.is_searchable ?? false)
  const [sortOrder, setSortOrder] = useState(String(initial?.sort_order ?? 0))
  const [defaultValue, setDefaultValue] = useState(initial?.default_value ?? '')
  const [placeholder, setPlaceholder] = useState(initial?.placeholder ?? '')
  const [helpText, setHelpText] = useState(initial?.help_text ?? '')
  const [isActive, setIsActive] = useState(initial?.is_active ?? true)

  // validation (구조화)
  const [minLength, setMinLength] = useState(numOrEmpty(initial?.validation?.min_length))
  const [maxLength, setMaxLength] = useState(numOrEmpty(initial?.validation?.max_length))
  const [pattern, setPattern] = useState(initial?.validation?.pattern ?? '')
  const [min, setMin] = useState(numOrEmpty(initial?.validation?.min))
  const [max, setMax] = useState(numOrEmpty(initial?.validation?.max))

  // options (구조화)
  const [choices, setChoices] = useState<Choice[]>(toChoices(initial))
  const [refTable, setRefTable] = useState(initial?.options?.table ?? '')
  const [refLabelColumn, setRefLabelColumn] = useState(initial?.options?.label_column ?? '')

  const [formError, setFormError] = useState('')

  const isEdit = initial !== undefined
  const isSelectType = fieldType === 'select' || fieldType === 'multiselect'
  const showLengthRules = TEXTUAL_TYPES.includes(fieldType)
  const showRangeRules = fieldType === 'number'

  function buildValidation(): FieldValidation | null {
    const v: FieldValidation = {}
    if (showLengthRules) {
      if (minLength !== '') v.min_length = Number(minLength)
      if (maxLength !== '') v.max_length = Number(maxLength)
      if (pattern.trim() !== '') v.pattern = pattern.trim()
    }
    if (showRangeRules) {
      if (min !== '') v.min = Number(min)
      if (max !== '') v.max = Number(max)
    }
    return Object.keys(v).length > 0 ? v : null
  }

  function buildOptions(): FieldOptions | null {
    if (isSelectType) {
      const cleaned = choices
        .map((c) => ({ value: c.value.trim(), label: c.label.trim() || c.value.trim() }))
        .filter((c) => c.value !== '')
      return cleaned.length > 0 ? { choices: cleaned } : null
    }
    if (fieldType === 'reference') {
      if (refTable.trim() === '') return null
      const options: FieldOptions = { table: refTable.trim() }
      if (refLabelColumn.trim() !== '') options.label_column = refLabelColumn.trim()
      return options
    }
    return null
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!fieldKey.trim()) return setFormError('필드 키를 입력해 주세요.')
    if (!/^[a-z][a-z0-9_]*$/.test(fieldKey.trim())) {
      return setFormError('필드 키는 영문 소문자로 시작하고 소문자·숫자·밑줄만 사용할 수 있습니다.')
    }
    if (!label.trim()) return setFormError('라벨을 입력해 주세요.')
    if (isSelectType && choices.every((c) => c.value.trim() === '')) {
      return setFormError('선택 타입은 선택지를 1개 이상 입력해야 합니다.')
    }
    if (fieldType === 'reference' && refTable.trim() === '') {
      return setFormError('참조 타입은 대상 테이블을 입력해야 합니다.')
    }
    if (pattern.trim() !== '') {
      try {
        new RegExp(pattern.trim())
      } catch {
        return setFormError('pattern이 올바른 정규식이 아닙니다.')
      }
    }
    setFormError('')

    onSubmit({
      field_key: fieldKey.trim(),
      label: label.trim(),
      field_type: fieldType,
      is_required: isRequired,
      is_unique: isUnique,
      is_searchable: isSearchable,
      sort_order: sortOrder === '' ? 0 : Number(sortOrder),
      default_value: defaultValue.trim() === '' ? null : defaultValue.trim(),
      placeholder: placeholder.trim() === '' ? null : placeholder.trim(),
      help_text: helpText.trim() === '' ? null : helpText.trim(),
      validation: buildValidation(),
      options: buildOptions(),
      is_active: isActive,
    })
  }

  function updateChoice(index: number, key: keyof Choice, value: string) {
    setChoices((prev) => prev.map((c, i) => (i === index ? { ...c, [key]: value } : c)))
  }

  return (
    <form onSubmit={handleSubmit} className={styles.editor}>
      <h3 className={styles.editorTitle}>{isEdit ? `필드 수정: ${initial.field_key}` : '새 필드 추가'}</h3>

      <div className={styles.grid}>
        <label className={styles.fieldLabel}>
          필드 키 *
          <input
            className={styles.input}
            value={fieldKey}
            onChange={(e) => setFieldKey(e.target.value)}
            placeholder="예: license_number"
            disabled={isEdit || isPending}
          />
        </label>
        <label className={styles.fieldLabel}>
          라벨 *
          <input
            className={styles.input}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="예: 면허번호"
            disabled={isPending}
          />
        </label>
        <label className={styles.fieldLabel}>
          타입 *
          <select
            className={styles.select}
            value={fieldType}
            onChange={(e) => setFieldType(e.target.value as FieldType)}
            disabled={isEdit || isPending}
          >
            {FIELD_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label} ({t.value})
              </option>
            ))}
          </select>
        </label>
        <label className={styles.fieldLabel}>
          정렬 순서
          <input
            className={styles.input}
            type="number"
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value)}
            disabled={isPending}
          />
        </label>
        <label className={styles.fieldLabel}>
          기본값
          <input
            className={styles.input}
            value={defaultValue}
            onChange={(e) => setDefaultValue(e.target.value)}
            placeholder={fieldType === 'boolean' ? 'true 또는 false' : ''}
            disabled={isPending}
          />
        </label>
        <label className={styles.fieldLabel}>
          플레이스홀더
          <input
            className={styles.input}
            value={placeholder}
            onChange={(e) => setPlaceholder(e.target.value)}
            disabled={isPending}
          />
        </label>
        <label className={styles.fieldLabelFull}>
          도움말
          <input
            className={styles.input}
            value={helpText}
            onChange={(e) => setHelpText(e.target.value)}
            disabled={isPending}
          />
        </label>
      </div>

      <div className={styles.flagRow}>
        <label className={styles.flag}>
          <input
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
            disabled={isPending}
          />
          필수
        </label>
        <label className={styles.flag}>
          <input
            type="checkbox"
            checked={isUnique}
            onChange={(e) => setIsUnique(e.target.checked)}
            disabled={isPending}
          />
          고유값
        </label>
        <label className={styles.flag}>
          <input
            type="checkbox"
            checked={isSearchable}
            onChange={(e) => setIsSearchable(e.target.checked)}
            disabled={isPending}
          />
          검색 대상
        </label>
        <label className={styles.flag}>
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            disabled={isPending}
          />
          활성
        </label>
      </div>

      {(showLengthRules || showRangeRules) && (
        <fieldset className={styles.subSection}>
          <legend className={styles.subLegend}>검증 규칙</legend>
          <div className={styles.grid}>
            {showLengthRules && (
              <>
                <label className={styles.fieldLabel}>
                  최소 길이
                  <input
                    className={styles.input}
                    type="number"
                    min={0}
                    value={minLength}
                    onChange={(e) => setMinLength(e.target.value)}
                    disabled={isPending}
                  />
                </label>
                <label className={styles.fieldLabel}>
                  최대 길이
                  <input
                    className={styles.input}
                    type="number"
                    min={0}
                    value={maxLength}
                    onChange={(e) => setMaxLength(e.target.value)}
                    disabled={isPending}
                  />
                </label>
                <label className={styles.fieldLabelFull}>
                  패턴(정규식)
                  <input
                    className={styles.input}
                    value={pattern}
                    onChange={(e) => setPattern(e.target.value)}
                    placeholder="예: ^[A-Z]{2}-\d{4}$"
                    disabled={isPending}
                  />
                </label>
              </>
            )}
            {showRangeRules && (
              <>
                <label className={styles.fieldLabel}>
                  최솟값
                  <input
                    className={styles.input}
                    type="number"
                    value={min}
                    onChange={(e) => setMin(e.target.value)}
                    disabled={isPending}
                  />
                </label>
                <label className={styles.fieldLabel}>
                  최댓값
                  <input
                    className={styles.input}
                    type="number"
                    value={max}
                    onChange={(e) => setMax(e.target.value)}
                    disabled={isPending}
                  />
                </label>
              </>
            )}
          </div>
        </fieldset>
      )}

      {isSelectType && (
        <fieldset className={styles.subSection}>
          <legend className={styles.subLegend}>선택지</legend>
          {choices.map((choice, index) => (
            <div key={index} className={styles.choiceRow}>
              <input
                className={styles.input}
                value={choice.value}
                onChange={(e) => updateChoice(index, 'value', e.target.value)}
                placeholder="값"
                disabled={isPending}
              />
              <input
                className={styles.input}
                value={choice.label}
                onChange={(e) => updateChoice(index, 'label', e.target.value)}
                placeholder="표시 이름 (비우면 값과 동일)"
                disabled={isPending}
              />
              <button
                type="button"
                className={styles.btnSmall}
                onClick={() => setChoices((prev) => prev.filter((_, i) => i !== index))}
                disabled={isPending}
              >
                삭제
              </button>
            </div>
          ))}
          <button
            type="button"
            className={styles.btnSmall}
            onClick={() => setChoices((prev) => [...prev, { value: '', label: '' }])}
            disabled={isPending}
          >
            + 선택지 추가
          </button>
        </fieldset>
      )}

      {fieldType === 'reference' && (
        <fieldset className={styles.subSection}>
          <legend className={styles.subLegend}>참조 설정</legend>
          <div className={styles.grid}>
            <label className={styles.fieldLabel}>
              대상 테이블 *
              <input
                className={styles.input}
                value={refTable}
                onChange={(e) => setRefTable(e.target.value)}
                placeholder="예: departments"
                disabled={isPending}
              />
            </label>
            <label className={styles.fieldLabel}>
              라벨 컬럼
              <input
                className={styles.input}
                value={refLabelColumn}
                onChange={(e) => setRefLabelColumn(e.target.value)}
                placeholder="기본: name"
                disabled={isPending}
              />
            </label>
          </div>
        </fieldset>
      )}

      {formError && <p className={styles.error}>{formError}</p>}

      <div className={styles.actionRow}>
        <button type="submit" className={styles.btnPrimary} disabled={isPending}>
          {isPending ? '저장 중...' : isEdit ? '필드 저장' : '필드 추가'}
        </button>
        <button type="button" className={styles.btnCancel} onClick={onCancel} disabled={isPending}>
          취소
        </button>
      </div>
    </form>
  )
}
