import { getNodeOutputSchema, type OutputFieldDef } from '@syntara/contracts'

export type JsonSchemaObject = Record<string, unknown>

export type SchemaPreviewNode = {
  name: string
  label: string
  typeLabel: string
  description?: string
  path: string[]
  children?: SchemaPreviewNode[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function schemaTypeNames(schema: Record<string, unknown>): string[] {
  const rawType = schema.type
  if (typeof rawType === 'string') return [rawType]
  if (Array.isArray(rawType)) return rawType.filter((entry): entry is string => typeof entry === 'string')

  for (const unionName of ['anyOf', 'oneOf']) {
    const branches = schema[unionName]
    if (Array.isArray(branches)) {
      return [...new Set(branches.flatMap((branch) => (isRecord(branch) ? schemaTypeNames(branch) : [])))]
    }
  }

  return []
}

function schemaTypeLabel(schema: Record<string, unknown>): string {
  const types = schemaTypeNames(schema)
  if (types.includes('array')) {
    const items = isRecord(schema.items) ? schemaTypeLabel(schema.items) : 'unknown'
    return `array<${items}>`
  }

  return types.length > 0 ? types.join(' | ') : 'unknown'
}

function schemaProperties(schema: Record<string, unknown>): Record<string, unknown> | null {
  return isRecord(schema.properties) ? schema.properties : null
}

function buildSchemaNodes(properties: Record<string, unknown>, parentPath: string[] = []): SchemaPreviewNode[] {
  return Object.entries(properties).flatMap(([name, rawSchema]) => {
    if (!isRecord(rawSchema)) return []
    const path = [...parentPath, name]
    const childrenProperties = schemaProperties(rawSchema)
    const children = childrenProperties ? buildSchemaNodes(childrenProperties, path) : undefined
    const node: SchemaPreviewNode = {
      name,
      label: typeof rawSchema.title === 'string' ? rawSchema.title : name,
      typeLabel: schemaTypeLabel(rawSchema),
      ...(typeof rawSchema.description === 'string' ? { description: rawSchema.description } : {}),
      path,
      ...(children && children.length > 0 ? { children } : {}),
    }
    return [node]
  })
}

/** Convert an inline JSON Schema object into an expression-preview tree. `$ref` is never fetched. */
export function jsonSchemaToPreviewNodes(schema: unknown): SchemaPreviewNode[] {
  if (!isRecord(schema)) return []
  const properties = schemaProperties(schema)
  return properties ? buildSchemaNodes(properties) : []
}

/** Adapt the legacy flat node-output contract to the same renderer. */
export function outputFieldsToPreviewNodes(fields: OutputFieldDef[]): SchemaPreviewNode[] {
  return fields.map((field) => ({
    name: field.name,
    label: field.name,
    typeLabel: field.type,
    ...(field.description ? { description: field.description } : {}),
    path: [field.name],
  }))
}

/** Preserve mapped output paths while a detailed backend schema is unavailable. */
export function buildMappedOutputFallbackSchema(
  nodeType: string,
  outputs: Record<string, string> | undefined
): JsonSchemaObject | undefined {
  if (outputs === undefined || (nodeType !== 'form_prompt' && nodeType !== 'form_trigger')) return undefined

  const mappedProperties = Object.fromEntries(Object.keys(outputs).map((name) => [name, {}]))
  if (nodeType === 'form_trigger') {
    return {
      type: 'object',
      properties: {
        response_data: {
          type: 'object',
          properties: mappedProperties,
          additionalProperties: false,
        },
      },
      additionalProperties: false,
    }
  }

  const statusField = getNodeOutputSchema(nodeType)?.find((field) => field.name === 'status')
  return {
    type: 'object',
    properties: {
      ...(statusField ? { status: { type: statusField.type, description: statusField.description } } : {}),
      ...Object.fromEntries(Object.entries(mappedProperties).filter(([name]) => name !== 'status')),
    },
    additionalProperties: false,
  }
}

function placeholderForSchema(schema: Record<string, unknown>): unknown {
  const properties = schemaProperties(schema)
  if (properties) {
    return Object.fromEntries(
      Object.entries(properties).flatMap(([key, childSchema]) =>
        isRecord(childSchema) ? [[key, placeholderForSchema(childSchema)]] : []
      )
    )
  }

  const types = schemaTypeNames(schema)
  if (types.includes('null')) return null
  if (types.includes('array')) return []
  if (types.includes('boolean')) return false
  if (types.includes('number') || types.includes('integer')) return 0
  if (types.includes('object')) return {}
  if (types.includes('string')) return ''
  return null
}

/** Build a safe mock skeleton without reading form defaults or sample answers. */
export function buildJsonSchemaMockSkeleton(schema: unknown): string {
  if (!isRecord(schema)) return '{}'
  const properties = schemaProperties(schema)
  if (!properties) return '{}'
  const skeleton = Object.fromEntries(
    Object.entries(properties).flatMap(([key, propertySchema]) =>
      isRecord(propertySchema) ? [[key, placeholderForSchema(propertySchema)]] : []
    )
  )
  return JSON.stringify(skeleton, null, 2)
}
