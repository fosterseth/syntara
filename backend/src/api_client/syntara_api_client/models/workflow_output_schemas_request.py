from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.workflow_output_schema_node import WorkflowOutputSchemaNode


T = TypeVar("T", bound="WorkflowOutputSchemasRequest")


@_attrs_define
class WorkflowOutputSchemasRequest:
    """
    Attributes:
        nodes (list[WorkflowOutputSchemaNode]):
    """

    nodes: list[WorkflowOutputSchemaNode]

    def to_dict(self) -> dict[str, Any]:
        nodes = []
        for nodes_item_data in self.nodes:
            nodes_item = nodes_item_data.to_dict()
            nodes.append(nodes_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "nodes": nodes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.workflow_output_schema_node import WorkflowOutputSchemaNode

        d = dict(src_dict)
        nodes = []
        _nodes = d.pop("nodes")
        for nodes_item_data in _nodes:
            nodes_item = WorkflowOutputSchemaNode.from_dict(nodes_item_data)

            nodes.append(nodes_item)

        workflow_output_schemas_request = cls(
            nodes=nodes,
        )

        return workflow_output_schemas_request
