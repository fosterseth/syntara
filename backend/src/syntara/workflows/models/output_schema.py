"""API models for workflow node output schema resolution."""

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BeforeValidator, ConfigDict, Field, model_validator
from sqlmodel import SQLModel

from syntara.core.constants import JsonbLimits
from syntara.core.jsonb_limits import validate_jsonb_size
from syntara.workflows.models.validation_finding import ValidationFinding

_NODE_ID_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
_MAX_OUTPUT_MAPPING_ITEMS = 100
_MAX_OUTPUT_MAPPING_KEY_LENGTH = 128
_MAX_OUTPUT_MAPPING_EXPRESSION_LENGTH = 2048
_MAX_NODE_PARAMETERS_BYTES = 262_144


def _validate_node_parameters(value: dict[str, Any]) -> dict[str, Any]:
    """Keep each caller-supplied node envelope bounded while allowing partial configs."""
    return validate_jsonb_size(value, field_name="parameters", max_bytes=_MAX_NODE_PARAMETERS_BYTES)


NodeParameters = Annotated[dict[str, Any], BeforeValidator(_validate_node_parameters)]


class WorkflowOutputSchemaNode(SQLModel):
    """Bounded node envelope accepted by stateless schema resolution."""

    id: str = Field(min_length=1, max_length=128, pattern=_NODE_ID_PATTERN)
    type: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    parameters: NodeParameters = Field(default_factory=dict)
    outputs: dict[str, str] | None = Field(default=None, max_length=_MAX_OUTPUT_MAPPING_ITEMS)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")  # type: ignore[assignment]

    @model_validator(mode="after")
    def validate_output_mapping(self) -> "WorkflowOutputSchemaNode":
        """Bound expression sizes because output mappings are supplied by the caller."""
        if self.outputs is not None and any(
            len(key) > _MAX_OUTPUT_MAPPING_KEY_LENGTH or len(expression) > _MAX_OUTPUT_MAPPING_EXPRESSION_LENGTH
            for key, expression in self.outputs.items()
        ):
            msg = "Output mapping keys must be at most 128 characters and expressions at most 2048 characters"
            raise ValueError(msg)
        return self


class NodeOutputSchemaEntry(SQLModel):
    """Resolution status, optional JSON Schema, and safe structured findings."""

    status: Literal["available", "invalid", "unsupported"]
    output_schema: dict[str, Any] | None = None
    findings: list[ValidationFinding] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")  # type: ignore[assignment]

    @model_validator(mode="after")
    def validate_status_fields(self) -> "NodeOutputSchemaEntry":
        """Keep the result shape unambiguous for both saved and draft responses."""
        if self.status == "available":
            if self.output_schema is None or self.findings:
                msg = "Available output schemas require a schema and cannot include findings"
                raise ValueError(msg)
        elif self.output_schema is not None or not self.findings:
            msg = "Invalid or unsupported output schemas require findings and cannot include a schema"
            raise ValueError(msg)
        return self


class WorkflowOutputSchemasRequest(SQLModel):
    """Request body for resolving output schemas from current unsaved node drafts."""

    nodes: list[WorkflowOutputSchemaNode] = Field(max_length=JsonbLimits.MAX_WORKFLOW_NODES)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")  # type: ignore[assignment]

    @model_validator(mode="after")
    def reject_duplicate_node_ids(self) -> "WorkflowOutputSchemasRequest":
        """Reject duplicate IDs so each result maps to exactly one node."""
        ids = [node.id for node in self.nodes]
        duplicates = sorted({node_id for node_id in ids if ids.count(node_id) > 1})
        if duplicates:
            msg = f"Node IDs must be unique: {', '.join(duplicates)}"
            raise ValueError(msg)
        return self


class WorkflowOutputSchemasResponse(SQLModel):
    """Map of actual node IDs to output schema resolution results."""

    node_output_schemas: dict[str, NodeOutputSchemaEntry]

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")  # type: ignore[assignment]
