from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.workflow_output_schema_node_outputs_type_0 import WorkflowOutputSchemaNodeOutputsType0
    from ..models.workflow_output_schema_node_parameters import WorkflowOutputSchemaNodeParameters


T = TypeVar("T", bound="WorkflowOutputSchemaNode")


@_attrs_define
class WorkflowOutputSchemaNode:
    """Bounded partial node configuration used for stateless output schema resolution.

    Attributes:
        id (str):
        type_ (str):
        parameters (WorkflowOutputSchemaNodeParameters | Unset): Incomplete node parameters are accepted so findings can
            be returned per node.
        outputs (None | Unset | WorkflowOutputSchemaNodeOutputsType0): Optional output extraction mapping.
    """

    id: str
    type_: str
    parameters: WorkflowOutputSchemaNodeParameters | Unset = UNSET
    outputs: None | Unset | WorkflowOutputSchemaNodeOutputsType0 = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.workflow_output_schema_node_outputs_type_0 import WorkflowOutputSchemaNodeOutputsType0

        id = self.id

        type_ = self.type_

        parameters: dict[str, Any] | Unset = UNSET
        if not isinstance(self.parameters, Unset):
            parameters = self.parameters.to_dict()

        outputs: dict[str, Any] | None | Unset
        if isinstance(self.outputs, Unset):
            outputs = UNSET
        elif isinstance(self.outputs, WorkflowOutputSchemaNodeOutputsType0):
            outputs = self.outputs.to_dict()
        else:
            outputs = self.outputs

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "id": id,
                "type": type_,
            }
        )
        if parameters is not UNSET:
            field_dict["parameters"] = parameters
        if outputs is not UNSET:
            field_dict["outputs"] = outputs

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.workflow_output_schema_node_outputs_type_0 import WorkflowOutputSchemaNodeOutputsType0
        from ..models.workflow_output_schema_node_parameters import WorkflowOutputSchemaNodeParameters

        d = dict(src_dict)
        id = d.pop("id")

        type_ = d.pop("type")

        _parameters = d.pop("parameters", UNSET)
        parameters: WorkflowOutputSchemaNodeParameters | Unset
        if isinstance(_parameters, Unset):
            parameters = UNSET
        else:
            parameters = WorkflowOutputSchemaNodeParameters.from_dict(_parameters)

        def _parse_outputs(data: object) -> None | Unset | WorkflowOutputSchemaNodeOutputsType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                outputs_type_0 = WorkflowOutputSchemaNodeOutputsType0.from_dict(data)

                return outputs_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | WorkflowOutputSchemaNodeOutputsType0, data)

        outputs = _parse_outputs(d.pop("outputs", UNSET))

        workflow_output_schema_node = cls(
            id=id,
            type_=type_,
            parameters=parameters,
            outputs=outputs,
        )

        return workflow_output_schema_node
