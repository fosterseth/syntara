import { Alert, Button, Flex, FlexItem, Label, Stack, StackItem } from '@patternfly/react-core'
import { RhUiCloseIcon } from '@patternfly/react-icons'
import { getNodeOutputSchema, TriggerTypeEnum } from '@syntara/contracts'

import type { UpstreamNodeInfo } from './hooks/useUpstreamNodes'
import type { OutputSchemaEntry } from './hooks/useResolvedNodeOutputSchemas'
import { InputEmptyState } from './InputEmptyState'
import { getTriggerInputSchemaFields } from './utils/triggerSchemaUtils'
import { buildMappedOutputFallbackSchema } from './utils/schemaToPreviewFields'
import { InputJsonView } from './views/InputJsonView'
import { InputSchemaPreview } from './views/InputSchemaPreview'
import { InputSchemaView } from './views/InputSchemaView'
import { InputTableView } from './views/InputTableView'
import type { PanelView } from './ViewToggle'

const TRIGGER_TYPES: ReadonlySet<string> = new Set([
  TriggerTypeEnum.MANUAL_TRIGGER,
  TriggerTypeEnum.SCHEDULED,
  TriggerTypeEnum.EVENT,
  TriggerTypeEnum.WEBHOOK_TRIGGER,
  TriggerTypeEnum.EDA_TRIGGER,
  TriggerTypeEnum.FORM_TRIGGER,
])

export type InputNodeContentProps = {
  upstreamNode: UpstreamNodeInfo
  hasData: boolean
  mergedExecutionData: Record<string, Record<string, unknown>> | null
  triggers: { id: string; parameters?: Record<string, unknown> }[] | undefined
  activeView: PanelView
  searchTerm: string
  onRunPreviousSteps?: () => void
  workflowId?: string | null
  outputSchemaEntry?: OutputSchemaEntry
  isResolvingOutputSchema?: boolean
  outputSchemaError?: unknown
  onRetryOutputSchema?: () => void
}

export function InputNodeContent({
  upstreamNode,
  hasData,
  mergedExecutionData,
  triggers,
  activeView,
  searchTerm,
  onRunPreviousSteps,
  workflowId,
  outputSchemaEntry,
  isResolvingOutputSchema = false,
  outputSchemaError,
  onRetryOutputSchema,
}: Readonly<InputNodeContentProps>) {
  const nodeData = hasData ? (mergedExecutionData?.[upstreamNode.id] ?? null) : null
  const expressionNodeId = TRIGGER_TYPES.has(upstreamNode.type) ? 'trigger' : upstreamNode.id

  if (!nodeData) {
    const schema = getNodeOutputSchema(upstreamNode.type)
    const effectiveSchema = schema ?? getTriggerInputSchemaFields(upstreamNode.id, triggers)
    const resolvedOutputSchema = outputSchemaEntry?.status === 'available' ? outputSchemaEntry.output_schema : undefined
    const mappedFallbackSchema = buildMappedOutputFallbackSchema(upstreamNode.type, upstreamNode.outputs)
    const previewSchema = resolvedOutputSchema ?? mappedFallbackSchema
    if (!effectiveSchema && !previewSchema) {
      const supportsInputSchema =
        upstreamNode.type === TriggerTypeEnum.MANUAL_TRIGGER ||
        upstreamNode.type === TriggerTypeEnum.WEBHOOK_TRIGGER ||
        upstreamNode.type === TriggerTypeEnum.EDA_TRIGGER
      return <InputEmptyState variant={supportsInputSchema ? 'no-trigger-schema' : 'connected-not-run'} />
    }
    return (
      <Stack hasGutter>
        {Boolean(outputSchemaError) && (
          <StackItem>
            <Alert variant="danger" isInline title="Unable to resolve form output fields">
              Showing generic output fields.{' '}
              {onRetryOutputSchema && (
                <Button variant="link" onClick={onRetryOutputSchema} isInline>
                  Retry
                </Button>
              )}
            </Alert>
          </StackItem>
        )}
        {!outputSchemaError && isResolvingOutputSchema && !resolvedOutputSchema && (
          <StackItem>
            <Alert variant="info" isInline isPlain title="Resolving form output fields" />
          </StackItem>
        )}
        {outputSchemaEntry?.status === 'invalid' && (
          <StackItem>
            <Alert variant="warning" isInline title="Form output fields are unavailable">
              Showing generic output fields. {outputSchemaEntry.findings[0]?.message}
            </Alert>
          </StackItem>
        )}
        {onRunPreviousSteps && workflowId && (
          <StackItem>
            <Alert variant="info" isInline isPlain title="Expected input fields">
              <Button variant="link" onClick={onRunPreviousSteps} isInline>
                Run previous steps
              </Button>{' '}
              to see actual values
            </Alert>
          </StackItem>
        )}
        <StackItem>
          <InputSchemaPreview
            fields={previewSchema ? undefined : (effectiveSchema ?? undefined)}
            outputSchema={previewSchema}
            nodeId={expressionNodeId}
          />
        </StackItem>
      </Stack>
    )
  }

  switch (activeView) {
    case 'schema':
      return <InputSchemaView data={nodeData} nodeId={expressionNodeId} searchTerm={searchTerm} />
    case 'table':
      return <InputTableView data={nodeData} searchTerm={searchTerm} />
    case 'json':
      return <InputJsonView data={nodeData} />
    default: {
      const _exhaustive: never = activeView
      return _exhaustive
    }
  }
}

export type InputPanelNodeSectionProps = {
  upstreamNode: UpstreamNodeInfo
  hasPinnedMock: boolean
  handleUnpinSingle: (nodeId: string) => void
  children: React.ReactNode
}

export function InputPanelNodeSection({
  upstreamNode,
  hasPinnedMock,
  handleUnpinSingle,
  children,
}: Readonly<InputPanelNodeSectionProps>) {
  return (
    <Flex direction={{ default: 'column' }} spaceItems={{ default: 'spaceItemsSm' }}>
      {hasPinnedMock && (
        <FlexItem>
          <Flex alignItems={{ default: 'alignItemsCenter' }}>
            <FlexItem>
              <Label color="grey" isCompact>
                Mock data pinned
              </Label>
            </FlexItem>
            <FlexItem>
              <Button variant="link" isDanger onClick={() => handleUnpinSingle(upstreamNode.id)}>
                <RhUiCloseIcon /> Unpin data
              </Button>
            </FlexItem>
          </Flex>
        </FlexItem>
      )}
      <FlexItem>{children}</FlexItem>
    </Flex>
  )
}
