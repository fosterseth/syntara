from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.workflow_output_schemas_response_node_output_schemas import (
        WorkflowOutputSchemasResponseNodeOutputSchemas,
    )


T = TypeVar("T", bound="WorkflowOutputSchemasResponse")


@_attrs_define
class WorkflowOutputSchemasResponse:
    """
    Attributes:
        node_output_schemas (WorkflowOutputSchemasResponseNodeOutputSchemas):
    """

    node_output_schemas: WorkflowOutputSchemasResponseNodeOutputSchemas

    def to_dict(self) -> dict[str, Any]:
        node_output_schemas = self.node_output_schemas.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "node_output_schemas": node_output_schemas,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.workflow_output_schemas_response_node_output_schemas import (
            WorkflowOutputSchemasResponseNodeOutputSchemas,
        )

        d = dict(src_dict)
        node_output_schemas = WorkflowOutputSchemasResponseNodeOutputSchemas.from_dict(d.pop("node_output_schemas"))

        workflow_output_schemas_response = cls(
            node_output_schemas=node_output_schemas,
        )

        return workflow_output_schemas_response
