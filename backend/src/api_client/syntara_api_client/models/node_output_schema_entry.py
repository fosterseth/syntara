from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.node_output_schema_entry_status import NodeOutputSchemaEntryStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.node_output_schema_entry_output_schema_type_0 import NodeOutputSchemaEntryOutputSchemaType0
    from ..models.validation_finding import ValidationFinding


T = TypeVar("T", bound="NodeOutputSchemaEntry")


@_attrs_define
class NodeOutputSchemaEntry:
    """
    Attributes:
        status (NodeOutputSchemaEntryStatus):
        findings (list[ValidationFinding]):
        output_schema (NodeOutputSchemaEntryOutputSchemaType0 | None | Unset):
    """

    status: NodeOutputSchemaEntryStatus
    findings: list[ValidationFinding]
    output_schema: NodeOutputSchemaEntryOutputSchemaType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.node_output_schema_entry_output_schema_type_0 import NodeOutputSchemaEntryOutputSchemaType0

        status = self.status.value

        findings = []
        for findings_item_data in self.findings:
            findings_item = findings_item_data.to_dict()
            findings.append(findings_item)

        output_schema: dict[str, Any] | None | Unset
        if isinstance(self.output_schema, Unset):
            output_schema = UNSET
        elif isinstance(self.output_schema, NodeOutputSchemaEntryOutputSchemaType0):
            output_schema = self.output_schema.to_dict()
        else:
            output_schema = self.output_schema

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
                "findings": findings,
            }
        )
        if output_schema is not UNSET:
            field_dict["output_schema"] = output_schema

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.node_output_schema_entry_output_schema_type_0 import NodeOutputSchemaEntryOutputSchemaType0
        from ..models.validation_finding import ValidationFinding

        d = dict(src_dict)
        status = NodeOutputSchemaEntryStatus(d.pop("status"))

        findings = []
        _findings = d.pop("findings")
        for findings_item_data in _findings:
            findings_item = ValidationFinding.from_dict(findings_item_data)

            findings.append(findings_item)

        def _parse_output_schema(data: object) -> NodeOutputSchemaEntryOutputSchemaType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                output_schema_type_0 = NodeOutputSchemaEntryOutputSchemaType0.from_dict(data)

                return output_schema_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(NodeOutputSchemaEntryOutputSchemaType0 | None | Unset, data)

        output_schema = _parse_output_schema(d.pop("output_schema", UNSET))

        node_output_schema_entry = cls(
            status=status,
            findings=findings,
            output_schema=output_schema,
        )

        return node_output_schema_entry
