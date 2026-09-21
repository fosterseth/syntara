import { FormFieldTypeEnum } from './formFieldTypeEnum'
import type { FormDefinition, FormField, FormSubmissionData, FormSubmissionInput } from './formTypes'
import {
  FormDataValidationError,
  FormDefinitionValidationError,
  type FormFieldValidationError,
} from './formValidationErrors'

const MISSING = Symbol('missing')

type Coercer = (raw: unknown) => string | number | boolean | Array<string | number | boolean>

function isEmptyValue(value: unknown): boolean {
  return value === '' || value === null || value === undefined || (Array.isArray(value) && value.length === 0)
}

function coerceString(raw: unknown): string {
  if (typeof raw !== 'string') {
    throw new TypeError(`Must be a string, got ${typeof raw}`)
  }
  return raw
}

function coerceEmail(raw: unknown): string {
  const value = coerceString(raw)
  const at = value.lastIndexOf('@')
  if (at <= 0 || at === value.length - 1) {
    throw new Error('Must be a valid email address')
  }
  const local = value.slice(0, at)
  const domain = value.slice(at + 1).toLowerCase()
  const normalized = `${local}@${domain}`
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) {
    throw new Error('Must be a valid email address')
  }
  return normalized
}

function coerceNumber(raw: unknown): number {
  if (typeof raw === 'boolean') {
    throw new TypeError('Boolean values are not accepted as numbers')
  }
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) {
      throw new Error('Infinite and NaN values are not accepted')
    }
    return raw
  }
  if (typeof raw === 'string') {
    const parsed = Number(raw)
    if (!Number.isFinite(parsed)) {
      throw new Error('Must be a valid number string')
    }
    return parsed
  }
  throw new TypeError(`Must be a number, got ${typeof raw}`)
}

function coerceCheckbox(raw: unknown): boolean {
  if (typeof raw === 'boolean') {
    return raw
  }
  if (typeof raw === 'number' && (raw === 0 || raw === 1)) {
    return Boolean(raw)
  }
  if (typeof raw === 'string') {
    const lower = raw.toLowerCase()
    if (['true', 'on', 'yes', '1'].includes(lower)) {
      return true
    }
    if (['false', 'off', 'no', '0'].includes(lower)) {
      return false
    }
    throw new Error('Must be a boolean value (true/false, yes/no, on/off, 1/0)')
  }
  throw new TypeError(`Must be a boolean, got ${typeof raw}`)
}

function coerceDate(raw: unknown): string {
  if (typeof raw !== 'string') {
    throw new TypeError(`Must be a date string, got ${typeof raw}`)
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!match) {
    throw new Error('Must be a valid ISO 8601 date (YYYY-MM-DD)')
  }
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new Error('Must be a valid ISO 8601 date (YYYY-MM-DD)')
  }
  return `${match[1]}-${match[2]}-${match[3]}`
}

function coerceOptionScalar(raw: unknown): string | number | boolean {
  if (typeof raw === 'string' || typeof raw === 'number' || typeof raw === 'boolean') {
    return raw
  }
  throw new TypeError(`Must be a string, number, or boolean, got ${typeof raw}`)
}

function coerceDropdown(raw: unknown): string | number | boolean {
  if (Array.isArray(raw)) {
    throw new TypeError('Dropdown expects a single value, not a list')
  }
  if (typeof raw === 'object' && raw !== null) {
    throw new TypeError('Dropdown expects a scalar value, not a dict')
  }
  return coerceOptionScalar(raw)
}

function coerceMultiSelect(raw: unknown): Array<string | number | boolean> {
  if (Array.isArray(raw)) {
    return raw.map((item) => coerceOptionScalar(item))
  }
  if (typeof raw === 'object' && raw !== null) {
    throw new TypeError('Multi-select expects a list or scalar, not a dict')
  }
  return [coerceOptionScalar(raw)]
}

const COERCERS: Record<FormField['type'], Coercer> = {
  [FormFieldTypeEnum.TEXT]: coerceString,
  [FormFieldTypeEnum.TEXTAREA]: coerceString,
  [FormFieldTypeEnum.MASKED_TEXT]: coerceString,
  [FormFieldTypeEnum.EMAIL]: coerceEmail,
  [FormFieldTypeEnum.NUMBER]: coerceNumber,
  [FormFieldTypeEnum.CHECKBOX]: coerceCheckbox,
  [FormFieldTypeEnum.DATE]: coerceDate,
  [FormFieldTypeEnum.DROPDOWN]: coerceDropdown,
  [FormFieldTypeEnum.MULTI_SELECT]: coerceMultiSelect,
}

function coerceField(field: FormField, raw: unknown): string | number | boolean | Array<string | number | boolean> {
  return COERCERS[field.type](raw)
}

type SelectFormField = Extract<FormField, { type: 'dropdown' }> | Extract<FormField, { type: 'multi_select' }>

type SelectFormFieldWithStaticOptions = SelectFormField & {
  options: Extract<SelectFormField['options'], { source: 'static' }>
}

function isStaticOptions(field: FormField): field is SelectFormFieldWithStaticOptions {
  if (field.type !== FormFieldTypeEnum.DROPDOWN && field.type !== FormFieldTypeEnum.MULTI_SELECT) {
    return false
  }
  return field.options.source === 'static'
}

function checkStaticOptionMembership(
  field: FormField,
  coerced: FormSubmissionData[string]
): FormFieldValidationError | null {
  if (!isStaticOptions(field)) {
    return null
  }

  const validValues = new Set(field.options.values.map((option) => option.value))

  if (field.type === FormFieldTypeEnum.MULTI_SELECT) {
    const values = coerced as Array<string | number | boolean>
    const invalid = values.filter((value) => !validValues.has(value))
    if (invalid.length > 0) {
      return {
        field: field.value_name,
        label: field.label,
        code: 'not_in_options',
        message: `Invalid selection(s): ${invalid.length} value(s) not in option list`,
      }
    }
    return null
  }

  if (!validValues.has(coerced as string | number | boolean)) {
    return {
      field: field.value_name,
      label: field.label,
      code: 'not_in_options',
      message: 'Selected value is not in the option list',
    }
  }
  return null
}

function fieldError(
  field: FormField,
  code: FormFieldValidationError['code'],
  message: string
): FormFieldValidationError {
  return { field: field.value_name, label: field.label, code, message }
}

type FieldSubmissionOutcome =
  | { status: 'omit' }
  | { status: 'invalid'; error: FormFieldValidationError }
  | { status: 'valid'; value: FormSubmissionData[string] }

function resolveSubmittedRaw(field: FormField, submitted: FormSubmissionInput): unknown {
  let raw: unknown = Object.hasOwn(submitted, field.value_name) ? submitted[field.value_name] : MISSING

  if (field.type !== FormFieldTypeEnum.CHECKBOX && raw !== MISSING && isEmptyValue(raw)) {
    raw = MISSING
  }

  if (raw === MISSING && field.default != null) {
    raw = field.default
  }

  return raw
}

function validateFieldSubmission(field: FormField, submitted: FormSubmissionInput): FieldSubmissionOutcome {
  const raw = resolveSubmittedRaw(field, submitted)

  if (raw === MISSING) {
    if (field.required) {
      return { status: 'invalid', error: fieldError(field, 'required', 'This field is required') }
    }
    return { status: 'omit' }
  }

  let coerced: FormSubmissionData[string]
  try {
    coerced = coerceField(field, raw)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid value'
    const isFormatError =
      field.type === FormFieldTypeEnum.EMAIL && error instanceof Error && !(error instanceof TypeError)
    return {
      status: 'invalid',
      error: fieldError(field, isFormatError ? 'invalid_format' : 'type', message),
    }
  }

  if (field.type === FormFieldTypeEnum.CHECKBOX && field.required && coerced === false) {
    return { status: 'invalid', error: fieldError(field, 'must_be_checked', 'This checkbox must be checked') }
  }

  const optionError = checkStaticOptionMembership(field, coerced)
  if (optionError) {
    return { status: 'invalid', error: optionError }
  }

  return { status: 'valid', value: coerced }
}

function unknownFieldErrors(form: FormDefinition, submitted: FormSubmissionInput): FormFieldValidationError[] {
  const knownNames = new Set(form.fields.map((f) => f.value_name))
  return Object.keys(submitted)
    .filter((key) => !knownNames.has(key))
    .map((key) => ({
      field: key,
      label: key,
      code: 'unknown_field' as const,
      message: 'Unknown field - not defined in form',
    }))
}

/**
 * Validate and coerce submitted form data against a parsed {@link FormDefinition}.
 * Mirrors backend `validate_form_submission` behavior for client-side checks.
 */
export function validateFormSubmission(form: FormDefinition, submitted: FormSubmissionInput): FormSubmissionData {
  const errors: FormFieldValidationError[] = []
  const cleaned: FormSubmissionData = {}

  for (const field of form.fields) {
    const outcome = validateFieldSubmission(field, submitted)
    if (outcome.status === 'invalid') {
      errors.push(outcome.error)
    } else if (outcome.status === 'valid') {
      cleaned[field.value_name] = outcome.value
    }
  }

  errors.push(...unknownFieldErrors(form, submitted))

  if (errors.length > 0) {
    throw new FormDataValidationError(errors)
  }

  return cleaned
}

/**
 * Validates that each field default can be coerced (builder / definition authoring).
 */
export function validateFormDefinitionDefaults(form: FormDefinition): void {
  const errors: FormFieldValidationError[] = []

  for (const field of form.fields) {
    if (field.type === FormFieldTypeEnum.CHECKBOX || field.default == null) {
      continue
    }
    try {
      coerceField(field, field.default)
    } catch (error) {
      const message =
        error instanceof Error
          ? `Default value is not valid for a '${field.type}' field: ${error.message}`
          : `Default value is not valid for a '${field.type}' field`
      errors.push(fieldError(field, 'invalid_default', message))
    }
  }

  if (errors.length > 0) {
    throw new FormDefinitionValidationError(errors)
  }
}

/** Validates defaults after structural parse. */
export function assertValidFormDefinition(form: FormDefinition): FormDefinition {
  validateFormDefinitionDefaults(form)
  return form
}
