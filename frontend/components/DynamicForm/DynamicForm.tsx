'use client'

// AD-12: role_fields 정의를 렌더링하는 유일한 동적 폼 렌더러.
// field_type 추가는 이 컴포넌트(+백엔드 검증기)에만 손댄다.
// reference 선택지는 부모가 BFF 경유로 조회해 referenceOptions로 주입한다 — 이 컴포넌트는 fetch하지 않는다.

import type { ReactNode } from 'react'
import type { ReferenceOption, RoleField } from '@/types/role-fields'
import styles from './DynamicForm.module.css'

interface DynamicFormProps {
  fields: RoleField[]
  values: Record<string, unknown>
  onChange: (fieldKey: string, value: unknown) => void
  errors?: Record<string, string>
  disabled?: boolean
  /** reference 타입 필드의 선택지 — { field_key: [{value,label}] } */
  referenceOptions?: Record<string, ReferenceOption[]>
}

/** default_value(TEXT)를 field_type에 맞는 초기값으로 해석해 초기 values를 만든다 */
export function buildInitialValues(fields: RoleField[]): Record<string, unknown> {
  const values: Record<string, unknown> = {}
  for (const field of fields) {
    if (!field.is_active || field.default_value === null || field.default_value === undefined) {
      continue
    }
    switch (field.field_type) {
      case 'boolean':
        values[field.field_key] = field.default_value === 'true'
        break
      case 'number': {
        const num = Number(field.default_value)
        if (!Number.isNaN(num)) values[field.field_key] = num
        break
      }
      case 'multiselect': {
        try {
          const parsed = JSON.parse(field.default_value)
          if (Array.isArray(parsed)) values[field.field_key] = parsed
        } catch {
          // 파싱 불가한 기본값은 무시
        }
        break
      }
      default:
        values[field.field_key] = field.default_value
    }
  }
  return values
}

function normalizeChoices(field: RoleField): ReferenceOption[] {
  const choices = field.options?.choices ?? []
  return choices.map((choice) =>
    typeof choice === 'string' ? { value: choice, label: choice } : choice
  )
}

export default function DynamicForm({
  fields,
  values,
  onChange,
  errors = {},
  disabled = false,
  referenceOptions = {},
}: DynamicFormProps) {
  const activeFields = fields
    .filter((field) => field.is_active)
    .sort((a, b) => a.sort_order - b.sort_order)

  function renderInput(field: RoleField): ReactNode {
    const key = field.field_key
    const value = values[key]
    const hasError = Boolean(errors[key])
    const inputClass = hasError ? `${styles.input} ${styles.inputError}` : styles.input
    const selectClass = hasError ? `${styles.select} ${styles.inputError}` : styles.select

    switch (field.field_type) {
      case 'text':
      case 'phone':
      case 'email':
        return (
          <input
            id={`df-${key}`}
            type={field.field_type === 'email' ? 'email' : field.field_type === 'phone' ? 'tel' : 'text'}
            className={inputClass}
            value={typeof value === 'string' ? value : ''}
            placeholder={field.placeholder ?? undefined}
            disabled={disabled}
            onChange={(e) => onChange(key, e.target.value)}
          />
        )
      case 'number':
        return (
          <input
            id={`df-${key}`}
            type="number"
            className={inputClass}
            value={value === undefined || value === null ? '' : String(value)}
            placeholder={field.placeholder ?? undefined}
            disabled={disabled}
            onChange={(e) => onChange(key, e.target.value === '' ? '' : Number(e.target.value))}
          />
        )
      case 'date':
        return (
          <input
            id={`df-${key}`}
            type="date"
            className={inputClass}
            value={typeof value === 'string' ? value : ''}
            disabled={disabled}
            onChange={(e) => onChange(key, e.target.value)}
          />
        )
      case 'boolean':
        return (
          <label className={styles.checkboxRow}>
            <input
              id={`df-${key}`}
              type="checkbox"
              className={styles.checkbox}
              checked={value === true}
              disabled={disabled}
              onChange={(e) => onChange(key, e.target.checked)}
            />
            <span className={styles.checkboxLabel}>{field.placeholder ?? field.label}</span>
          </label>
        )
      case 'select': {
        const choices = normalizeChoices(field)
        return (
          <select
            id={`df-${key}`}
            className={selectClass}
            value={typeof value === 'string' ? value : ''}
            disabled={disabled}
            onChange={(e) => onChange(key, e.target.value)}
          >
            <option value="">{field.placeholder ?? '선택하세요'}</option>
            {choices.map((choice) => (
              <option key={choice.value} value={choice.value}>
                {choice.label}
              </option>
            ))}
          </select>
        )
      }
      case 'multiselect': {
        const choices = normalizeChoices(field)
        const selected = Array.isArray(value) ? (value as string[]) : []
        return (
          <div className={styles.checkboxGroup} role="group" aria-labelledby={`df-label-${key}`}>
            {choices.map((choice) => (
              <label key={choice.value} className={styles.checkboxRow}>
                <input
                  type="checkbox"
                  className={styles.checkbox}
                  checked={selected.includes(choice.value)}
                  disabled={disabled}
                  onChange={(e) =>
                    onChange(
                      key,
                      e.target.checked
                        ? [...selected, choice.value]
                        : selected.filter((v) => v !== choice.value)
                    )
                  }
                />
                <span className={styles.checkboxLabel}>{choice.label}</span>
              </label>
            ))}
            {choices.length === 0 && <span className={styles.emptyOptions}>선택지가 없습니다.</span>}
          </div>
        )
      }
      case 'reference': {
        const refs = referenceOptions[key] ?? []
        return (
          <select
            id={`df-${key}`}
            className={selectClass}
            value={typeof value === 'string' ? value : ''}
            disabled={disabled}
            onChange={(e) => onChange(key, e.target.value)}
          >
            <option value="">{field.placeholder ?? '선택하세요'}</option>
            {refs.map((ref) => (
              <option key={ref.value} value={ref.value}>
                {ref.label}
              </option>
            ))}
          </select>
        )
      }
      case 'json':
        return (
          <textarea
            id={`df-${key}`}
            className={hasError ? `${styles.textarea} ${styles.inputError}` : styles.textarea}
            value={typeof value === 'string' ? value : value === undefined || value === null ? '' : JSON.stringify(value, null, 2)}
            placeholder={field.placeholder ?? '{ }'}
            disabled={disabled}
            rows={4}
            onChange={(e) => onChange(key, e.target.value)}
          />
        )
    }
  }

  return (
    <div className={styles.form}>
      {activeFields.map((field) => (
        <div key={field.field_key} className={styles.field}>
          <label
            id={`df-label-${field.field_key}`}
            htmlFor={`df-${field.field_key}`}
            className={styles.label}
          >
            {field.label}
            {field.is_required && (
              <span className={styles.required} aria-hidden="true">
                *
              </span>
            )}
          </label>
          {renderInput(field)}
          {field.help_text && <p className={styles.helpText}>{field.help_text}</p>}
          {errors[field.field_key] && (
            <p className={styles.errorText} role="alert">
              {errors[field.field_key]}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
