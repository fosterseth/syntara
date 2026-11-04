from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.node_output_schema_entry import NodeOutputSchemaEntry


T = TypeVar("T", bound="WorkflowVersionReadNodeOutputSchemas")


@_attrs_define
class WorkflowVersionReadNodeOutputSchemas:
    """Read-only output schemas derived from configured form nodes, keyed by actual node ID."""

    additional_properties: dict[str, NodeOutputSchemaEntry] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop.to_dict()

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.node_output_schema_entry import NodeOutputSchemaEntry

        d = dict(src_dict)
        workflow_version_read_node_output_schemas = cls()

        additional_properties = {}
        for prop_name, prop_dict in d.items():
            additional_property = NodeOutputSchemaEntry.from_dict(prop_dict)

            additional_properties[prop_name] = additional_property

        workflow_version_read_node_output_schemas.additional_properties = additional_properties
        return workflow_version_read_node_output_schemas

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> NodeOutputSchemaEntry:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: NodeOutputSchemaEntry) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
