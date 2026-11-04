"""Pure form-node output schema resolution for saved and unsaved workflows."""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from syntara.forms.exceptions import FormDefinitionError
from syntara.forms.models.form_fields import (
    CheckboxField,
    DateField,
    DropdownField,
    EmailField,
    FormPromptDefinition,
    FormTriggerDefinition,
    MaskedTextField,
    MultiSelectField,
    NumberField,
    ResolvedOptions,
    StaticOptions,
    TextAreaField,
    TextField,
)
from syntara.forms.validators.form_definition import validate_form_definition
from syntara.schemas import SCHEMA_DIR
from syntara.workflows.models.output_schema import (
    NodeOutputSchemaEntry,
    WorkflowOutputSchemaNode,
)
from syntara.workflows.models.validation_finding import (
    ValidationCategory,
    ValidationFinding,
    ValidationSeverity,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_FORM_PROMPT_TYPES = {"form_prompt", "form_trigger"}
_PURE_RESULT_PATH = re.compile(r"^result(?:\.([A-Za-z_][A-Za-z0-9_]*))*$")
_TEMPLATE_TOKEN = re.compile(r"\$\{[^{}]+\}")


@lru_cache(maxsize=2)
def _load_static_result_schema(node_type: str) -> dict[str, Any]:
    """Read and cache the repository-owned static output schema for a form node."""
    schema_file = {
        "form_prompt": "executors/form_prompt.schema.json",
        "form_trigger": "triggers/form.schema.json",
    }[node_type]
    path = SCHEMA_DIR / "workflows" / "v2" / schema_file
    content = json.loads(path.read_text(encoding="utf-8"))
    result_schema = content["resultSchema"]
    if node_type == "form_prompt":
        result_schema = next(branch for branch in result_schema["oneOf"] if branch.get("title") == "Completed Result")
    return result_schema


def _base_output_schema(node_type: str) -> dict[str, Any]:
    """Clone the static output schema so per-form enrichment cannot leak across nodes."""
    schema = copy.deepcopy(_load_static_result_schema(node_type))
    schema["$schema"] = _JSON_SCHEMA_DRAFT
    if node_type == "form_prompt":
        schema["description"] = (
            "Expected form-prompt output after a response. This schema describes available fields; "
            "answers may be absent after a failure, timeout, or cancellation."
        )
    else:
        schema["description"] = "Form-trigger output containing submitted values after normalization."
    return schema


def _append_description(schema: dict[str, Any], *parts: str | None) -> None:
    """Set a description from non-empty, safe authored help and normalization details."""
    description = " ".join(part.strip() for part in parts if part and part.strip())
    if description:
        schema["description"] = description


def _nullable_type(type_name: str, *, nullable: bool) -> str | list[str]:
    return [type_name, "null"] if nullable else type_name


def _scalar_option_types(*, nullable: bool) -> list[str]:
    types = ["string", "number", "boolean"]
    if nullable:
        types.append("null")
    return types


def _date_field_output_schema(field: DateField) -> dict[str, Any]:
    """Describe each date component combination after its submission coercion."""
    output: dict[str, Any] = {"type": "string"}
    if field.include_date:
        if field.include_time:
            if field.include_timezone:
                description = "Normalized as an ISO 8601 date-time string with a timezone offset."
                if field.required:
                    output["format"] = "date-time"
            else:
                description = "Normalized as a local ISO 8601 date-time string without an offset."
        else:
            description = "Normalized as an ISO 8601 date string."
            if field.required:
                output["format"] = "date"
    elif field.include_time:
        description = (
            "Normalized as an ISO 8601 time string with a standard timezone offset."
            if field.include_timezone
            else "Normalized as an ISO 8601 time string without a timezone offset."
        )
    else:
        description = "Normalized as an IANA timezone name."

    if not field.required:
        description = f"Optional empty date values normalize to an empty string. {description}"
    output["normalized_description"] = description
    return output


def _dropdown_output_schema(field: DropdownField) -> dict[str, Any]:
    nullable = not field.required
    if isinstance(field.options, StaticOptions):
        values: list[Any] = [option.value for option in field.options.values]
        if nullable:
            values.append(None)
        return {"type": _nullable_type("string", nullable=nullable), "enum": values}

    output: dict[str, Any] = {"type": _scalar_option_types(nullable=nullable)}
    if isinstance(field.options, ResolvedOptions):
        values = [option.value for option in field.options.values]
        if nullable:
            values.append(None)
        output["enum"] = values
    return output


def _multi_select_output_schema(field: MultiSelectField) -> dict[str, Any]:
    if isinstance(field.options, StaticOptions):
        item_schema: dict[str, Any] = {
            "type": "string",
            "enum": [option.value for option in field.options.values],
        }
    elif isinstance(field.options, ResolvedOptions):
        item_schema = {
            "type": ["string", "number", "boolean"],
            "enum": [option.value for option in field.options.values],
        }
    else:
        item_schema = {"type": ["string", "number", "boolean"]}
    return {"type": "array", "items": item_schema}


def _field_output_schema(field: Any) -> dict[str, Any]:  # noqa: ANN401
    """Describe the normalized workflow answer for one authored form field."""
    normalized_description: str | None = None
    if isinstance(field, DateField):
        output = _date_field_output_schema(field)
        normalized_description = output.pop("normalized_description")
    elif isinstance(field, (TextField, TextAreaField, MaskedTextField, EmailField)):
        # Email may normalize to an optional empty string, so avoid format constraints.
        output = {"type": "string"}
    elif isinstance(field, NumberField):
        output = {"type": _nullable_type("number", nullable=not field.required)}
    elif isinstance(field, CheckboxField):
        output = {"type": "boolean"}
    elif isinstance(field, DropdownField):
        output = _dropdown_output_schema(field)
    elif isinstance(field, MultiSelectField):
        output = _multi_select_output_schema(field)
    else:
        # A permissive schema is safer than deriving an inaccurate type if the
        # closed form-field union gains a new class.
        output = {}

    output["title"] = field.label
    _append_description(output, field.help_text, normalized_description)
    return output


def _configured_field_schemas(form_definition: Any) -> dict[str, dict[str, Any]]:  # noqa: ANN401
    return {field.value_name: _field_output_schema(field) for field in form_definition.fields}


def _response_data_schema(fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "description": "Submitted form field values keyed by value_name and normalized for workflow use.",
        "properties": fields,
        "additionalProperties": False,
    }


def _replace_response_data_schema(
    output_schema: dict[str, Any],
    fields: dict[str, dict[str, Any]],
) -> None:
    properties = output_schema.setdefault("properties", {})
    properties["response_data"] = _response_data_schema(fields)


def _schema_at_path(schema: dict[str, Any], path_parts: list[str]) -> dict[str, Any] | None:
    current = schema
    for part in path_parts:
        properties = current.get("properties")
        if not isinstance(properties, dict):
            return None
        next_schema = properties.get(part)
        if not isinstance(next_schema, dict):
            return None
        current = next_schema
    return current


def _mapped_value_schema(expression: str, source_schema: dict[str, Any]) -> dict[str, Any]:
    """Infer safe static metadata for one mapping without evaluating the expression."""
    trimmed = expression.strip()
    if trimmed.startswith("${") and trimmed.endswith("}") and trimmed.count("${") == 1:
        path_expression = trimmed[2:-1].strip()
        match = _PURE_RESULT_PATH.fullmatch(path_expression)
        if match:
            path_parts = [part for part in path_expression.removeprefix("result").split(".") if part]
            matched_schema = _schema_at_path(source_schema, path_parts)
            return copy.deepcopy(matched_schema) if matched_schema is not None else {}
    if _TEMPLATE_TOKEN.search(trimmed):
        return {"type": "string"}
    # Literal or helper expressions are not executed to resolve their value.
    return {}


def _mapped_output_schema(
    node: WorkflowOutputSchemaNode,
    base_schema: dict[str, Any],
    form_fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Apply output-mapping visibility to the schema while preserving runtime nesting."""
    if node.outputs is None:
        return base_schema

    if node.type == "form_trigger":
        # form_trigger applies its output mapping to the submitted values before
        # wrapping them under response_data.
        source_schema = {"type": "object", "properties": form_fields, "additionalProperties": False}
        mapped_fields = {
            output_name: _mapped_value_schema(expression, source_schema)
            for output_name, expression in node.outputs.items()
        }
        _replace_response_data_schema(base_schema, mapped_fields)
        return base_schema

    base_properties = base_schema.get("properties", {})
    status_schema = base_properties.get("status") if isinstance(base_properties, dict) else None
    mapped_properties = {
        output_name: _mapped_value_schema(expression, base_schema)
        for output_name, expression in node.outputs.items()
        if output_name != "status"
    }
    if isinstance(status_schema, dict):
        mapped_properties = {"status": copy.deepcopy(status_schema), **mapped_properties}
    return {
        "$schema": _JSON_SCHEMA_DRAFT,
        "type": "object",
        "description": "Form-prompt output after applying its configured output mapping.",
        "required": ["status"],
        "properties": mapped_properties,
        "additionalProperties": False,
    }


def _finding(
    node: WorkflowOutputSchemaNode,
    *,
    category: ValidationCategory,
    message: str,
    field_path: str | None = None,
    severity: ValidationSeverity = ValidationSeverity.error,
) -> ValidationFinding:
    return ValidationFinding(
        severity=severity,
        category=category,
        message=message,
        node_id=node.id,
        field_path=field_path,
    )


def _resolve_form_node(node: WorkflowOutputSchemaNode) -> NodeOutputSchemaEntry:
    if node.type not in _FORM_PROMPT_TYPES:
        return NodeOutputSchemaEntry(
            status="unsupported",
            findings=[
                _finding(
                    node,
                    category=ValidationCategory.schema_violation,
                    severity=ValidationSeverity.warning,
                    message=f"No output schema provider is available for node type '{node.type}'.",
                )
            ],
        )

    raw_form_definition = node.parameters.get("form_definition")
    category = (
        ValidationCategory.form_prompt_configuration
        if node.type == "form_prompt"
        else ValidationCategory.form_trigger_configuration
    )
    if raw_form_definition is None:
        return NodeOutputSchemaEntry(
            status="invalid",
            findings=[
                _finding(
                    node,
                    category=ValidationCategory.missing_field,
                    message="A form definition is required to resolve this node's output schema.",
                    field_path="parameters.form_definition",
                )
            ],
        )

    definition_model = FormPromptDefinition if node.type == "form_prompt" else FormTriggerDefinition
    try:
        form_definition = definition_model.model_validate(raw_form_definition)
        validate_form_definition(form_definition)
    except (ValidationError, FormDefinitionError, TypeError, ValueError):
        # Do not include Pydantic/coercion messages here: they can contain an
        # authored default value, which may be masked or otherwise sensitive.
        return NodeOutputSchemaEntry(
            status="invalid",
            findings=[
                _finding(
                    node,
                    category=category,
                    message="The authored form definition is invalid and its output schema could not be resolved.",
                    field_path="parameters.form_definition",
                )
            ],
        )

    fields = _configured_field_schemas(form_definition)
    output_schema = _base_output_schema(node.type)
    _replace_response_data_schema(output_schema, fields)
    output_schema = _mapped_output_schema(node, output_schema, fields)
    return NodeOutputSchemaEntry(status="available", output_schema=output_schema, findings=[])


def resolve_node_output_schemas(
    nodes: Iterable[WorkflowOutputSchemaNode],
) -> dict[str, NodeOutputSchemaEntry]:
    """Resolve supported node outputs without reading or mutating external state."""
    return {node.id: _resolve_form_node(node) for node in nodes}


def node_output_schemas_for_workflow_definition(
    workflow_definition: Mapping[str, Any],
) -> dict[str, NodeOutputSchemaEntry]:
    """Derive persisted form-node metadata from a stored workflow definition."""
    nodes: list[WorkflowOutputSchemaNode] = []
    result: dict[str, NodeOutputSchemaEntry] = {}
    for collection in ("triggers", "nodes"):
        raw_nodes = workflow_definition.get(collection, [])
        if not isinstance(raw_nodes, list):
            continue
        for raw_node in raw_nodes:
            if not isinstance(raw_node, dict) or raw_node.get("type") not in _FORM_PROMPT_TYPES:
                continue
            node_id = raw_node.get("id")
            if not isinstance(node_id, str) or not node_id:
                continue
            try:
                nodes.append(
                    WorkflowOutputSchemaNode.model_validate(
                        {
                            "id": node_id,
                            "type": raw_node.get("type"),
                            "parameters": raw_node.get("parameters", {}),
                            "outputs": raw_node.get("outputs"),
                        }
                    )
                )
            except (ValidationError, TypeError, ValueError):
                result[node_id] = NodeOutputSchemaEntry(
                    status="invalid",
                    findings=[
                        ValidationFinding(
                            severity=ValidationSeverity.error,
                            category=ValidationCategory.schema_violation,
                            message=(
                                "The saved node configuration is invalid and its output schema could not be resolved."
                            ),
                            node_id=node_id,
                            field_path="parameters.form_definition",
                        )
                    ],
                )
    result.update(resolve_node_output_schemas(nodes))
    return result
