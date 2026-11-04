import { Content, ContentVariants, Label, TreeView, type TreeViewDataItem } from '@patternfly/react-core'
import { RhUiInformationIcon } from '@patternfly/react-icons'
import type { OutputFieldDef } from '@syntara/contracts'
import { useCallback, useMemo } from 'react'

import { canvasNodeIdForExpression, tryBuildExpression } from '../../../../utils/expressions/templateBuilder'
import { CopyExpressionAction, DraggableTreeLeaf } from '../components/DraggableTreeLeaf'
import { DRAG_TYPE_FIELD, type FieldDragData } from '../utils/dragTypes'
import { toTreeItemId } from '../utils/treeHelpers'
import { getTypeLabel } from '../utils/typeLabels'
import {
  jsonSchemaToPreviewNodes,
  outputFieldsToPreviewNodes,
  type SchemaPreviewNode,
} from '../utils/schemaToPreviewFields'

import styles from './InputSchemaPreview.module.css'

export type InputSchemaPreviewProps = {
  fields?: OutputFieldDef[]
  outputSchema?: unknown
  nodeId: string
}

type PreviewFieldProps = {
  field: SchemaPreviewNode
  nodeId: string
}

function displayTypeLabel(typeLabel: string): string {
  if (typeLabel === 'unknown') return getTypeLabel(typeLabel)
  if (typeLabel.includes('|') || typeLabel.startsWith('array<')) return typeLabel
  return getTypeLabel(typeLabel)
}

function PreviewField({ field, nodeId }: Readonly<PreviewFieldProps>) {
  const expression = useMemo(() => tryBuildExpression({ nodeId, fieldPath: field.path }), [nodeId, field.path])

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      if (!expression) {
        e.preventDefault()
        return
      }
      const data: FieldDragData = {
        type: DRAG_TYPE_FIELD,
        nodeId,
        fieldPath: field.path,
      }
      e.dataTransfer.setData('application/json', JSON.stringify(data))
      e.dataTransfer.setData('text/plain', expression)
      e.dataTransfer.effectAllowed = 'copy'
    },
    [nodeId, field.path, expression]
  )

  return (
    <DraggableTreeLeaf
      label={`${displayTypeLabel(field.typeLabel)} ${field.label}`}
      secondaryText={field.description}
      draggable={expression != null}
      onDragStart={handleDragStart}
    />
  )
}

function buildTreeItems(fields: SchemaPreviewNode[], nodeId: string): TreeViewDataItem[] {
  return fields.map((field) => {
    const id = toTreeItemId([nodeId, ...field.path])
    if (field.children?.length) {
      return {
        id,
        name: (
          <Label isCompact color="grey">
            {displayTypeLabel(field.typeLabel)} {field.label}
          </Label>
        ),
        defaultExpanded: true,
        hasBadge: false,
        children: buildTreeItems(field.children, nodeId),
      }
    }

    const expression = tryBuildExpression({ nodeId, fieldPath: field.path })
    return {
      id,
      name: <PreviewField field={field} nodeId={nodeId} />,
      ...(expression ? { action: <CopyExpressionAction expressionText={expression} /> } : {}),
      hasBadge: false,
    }
  })
}

function getSchemaDescription(schema: unknown): string | null {
  if (typeof schema !== 'object' || schema === null || Array.isArray(schema)) return null
  const description = 'description' in schema ? schema.description : undefined
  return typeof description === 'string' ? description : null
}

export function InputSchemaPreview({ fields = [], outputSchema, nodeId }: Readonly<InputSchemaPreviewProps>) {
  const expressionNodeId = canvasNodeIdForExpression(nodeId)
  const previewNodes = useMemo(
    () => (outputSchema ? jsonSchemaToPreviewNodes(outputSchema) : outputFieldsToPreviewNodes(fields)),
    [fields, outputSchema]
  )
  const treeData = useMemo(() => buildTreeItems(previewNodes, expressionNodeId), [previewNodes, expressionNodeId])
  const schemaDescription = getSchemaDescription(outputSchema)

  if (treeData.length === 0) {
    return null
  }

  return (
    <div className={styles.previewContainer}>
      <Content component={ContentVariants.small} className={styles.previewHeader}>
        <RhUiInformationIcon /> Expected output fields (run step to see actual values)
      </Content>
      {schemaDescription && (
        <Content component={ContentVariants.small} className={styles.schemaDescription}>
          {schemaDescription}
        </Content>
      )}
      <TreeView data={treeData} aria-label="Schema preview" />
    </div>
  )
}
