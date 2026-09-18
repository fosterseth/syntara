"""Shared utility for building previous-step context in workflow nodes.

Used by both approval and form_prompt nodes to construct the previous_step
context for workflow_context payloads.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from syntara.workflows.utils.namespace_resolver import NamespaceResolver
    from syntara.workflows.workflow_engine.graph import WorkflowGraph


def get_previous_step_context(
    node_id: str,
    graph: "WorkflowGraph",
    skipped_nodes: set[str],
    resolver: "NamespaceResolver",
) -> dict[str, Any] | None:
    """Build previous_step context for an approval or form_prompt request.

    Finds the predecessor node in the graph and returns its ID, name, type,
    and output for inclusion in workflow_context.

    Args:
        node_id: The current node's ID
        graph: The workflow graph
        skipped_nodes: Set of node IDs that were skipped
        resolver: Namespace resolver for looking up predecessor output

    Returns:
        Dictionary with id, name, type, and output keys, or None if no predecessor

    """
    predecessors = graph.get_predecessors(node_id)
    if not predecessors:
        return None
    prev_id = predecessors[0]
    prev_node = graph.get_node(prev_id)
    if prev_id in skipped_nodes:
        previous_output: dict[str, Any] | None = {"status": "skipped"}
    else:
        try:
            previous_output = resolver.get_namespace(prev_id)
        except KeyError:
            previous_output = None
    return {
        "id": prev_node.id,
        "name": prev_node.name or prev_node.id,
        "type": prev_node.type,
        "output": previous_output,
    }
