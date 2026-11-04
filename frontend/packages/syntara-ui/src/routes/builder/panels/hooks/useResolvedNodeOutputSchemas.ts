import type { WorkflowAPI } from '@syntara/contracts'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'

import { workflowFetchClient } from '../../../../client'
import { useWorkflowStore } from '../../../../stores/useWorkflowStore'
import { selectActivities, selectTriggers } from '../../../../stores/workflowStoreSelectors'

type OutputSchemaNode = WorkflowAPI.components['schemas']['WorkflowOutputSchemaNode']
export type OutputSchemaEntry = WorkflowAPI.components['schemas']['NodeOutputSchemaEntry']
export type OutputSchemasResponse = WorkflowAPI.components['schemas']['WorkflowOutputSchemasResponse']

const OUTPUT_SCHEMA_QUERY_KEY = 'workflow-node-output-schemas'

type OutputSchemaNodeSource = {
  id: string
  type: string
  parameters?: unknown
  outputs?: unknown
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Build a stable resolver request from only form settings and mapping configuration. */
export function buildNodeOutputSchemaRequestNodes(activities: unknown, triggers: unknown): OutputSchemaNode[] {
  const nodeSources = [activities, triggers].flatMap((collection): OutputSchemaNodeSource[] => {
    if (!Array.isArray(collection)) return []
    return collection.flatMap((node): OutputSchemaNodeSource[] => {
      if (!isRecord(node) || typeof node.id !== 'string' || typeof node.type !== 'string') return []
      return [{ id: node.id, type: node.type, parameters: node.parameters, outputs: node.outputs }]
    })
  })

  return nodeSources
    .filter((node) => node.type === 'form_prompt' || node.type === 'form_trigger')
    .map((node): OutputSchemaNode => {
      const parameters = isRecord(node.parameters) ? node.parameters : {}
      const formDefinition = parameters.form_definition
      const outputs = isRecord(node.outputs)
        ? Object.fromEntries(
            Object.entries(node.outputs).filter((entry): entry is [string, string] => typeof entry[1] === 'string')
          )
        : undefined
      return {
        id: node.id,
        type: node.type,
        parameters: formDefinition === undefined ? {} : { form_definition: formDefinition },
        ...(outputs === undefined ? {} : { outputs }),
      }
    })
    .sort((left, right) => left.id.localeCompare(right.id))
}

export function nodeOutputSchemasQueryKey(nodes: OutputSchemaNode[]) {
  return [OUTPUT_SCHEMA_QUERY_KEY, nodes] as const
}

/** Resolve the current local form drafts in one deduplicated, cancelable query. */
export function useResolvedNodeOutputSchemas() {
  const activities = useWorkflowStore(selectActivities)
  const triggers = useWorkflowStore(selectTriggers)
  const nodes = useMemo(() => buildNodeOutputSchemaRequestNodes(activities, triggers), [activities, triggers])

  const query = useQuery({
    queryKey: nodeOutputSchemasQueryKey(nodes),
    enabled: nodes.length > 0,
    staleTime: 30_000,
    queryFn: async ({ signal }): Promise<OutputSchemasResponse> => {
      const { data, error } = await workflowFetchClient.POST('/workflows/output-schemas', {
        body: { nodes },
        signal,
      })
      if (error) throw error
      if (!data) throw new Error('The output schema resolver returned no data.')
      return data
    },
  })

  return {
    nodes,
    nodeOutputSchemas: query.data?.node_output_schemas ?? {},
    isPending: nodes.length > 0 && query.isPending,
    error: query.error,
    retry: query.refetch,
  }
}
