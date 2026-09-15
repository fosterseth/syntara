"""Form field models — pure pydantic + stdlib for Temporal sandbox compatibility."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, field_validator, model_validator

from syntara.workflows.workflow_engine.models.workflow_definition import (
    _get_valid_timezones,
)

FIELD_NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_]*$"


class FormFieldBase(BaseModel):
    """Base class for all form field types."""

    model_config = ConfigDict(extra="forbid")

    value_name: str = Field(pattern=FIELD_NAME_PATTERN, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    placeholder: str | None = None
    help_text: str | None = None
    required: bool = False


class TextField(FormFieldBase):
    """Text field."""

    type: Literal["text"]
    default: str | None = None


class TextAreaField(FormFieldBase):
    """Text area field."""

    type: Literal["textarea"]
    default: str | None = None


class MaskedTextField(FormFieldBase):
    """Masked text field."""

    type: Literal["masked_text"]
    default: str | None = None


class EmailField(FormFieldBase):
    """Email field."""

    type: Literal["email"]
    default: str | None = None


class NumberField(FormFieldBase):
    """Numeric field supporting int or float."""

    type: Literal["number"]
    default: float | int | None = None


class CheckboxField(FormFieldBase):
    """Boolean checkbox field."""

    type: Literal["checkbox"]
    default: bool = False


class DateField(FormFieldBase):
    """Date field."""

    type: Literal["date"]
    default: str | None = None


class StaticOption(BaseModel):
    """A single static option for dropdown or multi-select."""

    model_config = ConfigDict(extra="forbid")

    display_label: str = Field(min_length=1, max_length=200)
    value: str | float | bool


class StaticOptions(BaseModel):
    """Static option list for dropdown or multi-select."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["static"]
    values: list[StaticOption] = Field(min_length=1, max_length=500)


class DynamicOptions(BaseModel):
    """Dynamic option list resolved from upstream node output."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["dynamic"]
    expression: str
    label_key: str | None = None
    value_key: str | None = None


OptionsSource = Annotated[StaticOptions | DynamicOptions, Discriminator("source")]


class DropdownField(FormFieldBase):
    """Dropdown field."""

    type: Literal["dropdown"]
    options: OptionsSource
    default: str | float | bool | None = None


class MultiSelectField(FormFieldBase):
    """Multi-select field."""

    type: Literal["multi_select"]
    options: OptionsSource
    default: list[Any] | None = None


FormField = Annotated[
    TextField
    | TextAreaField
    | MaskedTextField
    | EmailField
    | NumberField
    | CheckboxField
    | DateField
    | DropdownField
    | MultiSelectField,
    Discriminator("type"),
]


class FormDefinition(BaseModel):
    """Complete form definition with fields and metadata."""

    model_config = ConfigDict(extra="forbid")

    fields: list[FormField] = Field(min_length=1, max_length=100)
    submit_label: str | None = Field(default=None, max_length=100)
    success_message: str | None = Field(default=None, max_length=1000)
    css_override: str | None = Field(default=None, max_length=4096)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str | None) -> str | None:
        """Validate timezone against pytz's database."""
        if v is None:
            return None
        valid_tzs = _get_valid_timezones()
        if v not in valid_tzs:
            msg = f"Invalid timezone: {v}. Must be a valid IANA timezone identifier."
            raise ValueError(msg)
        return v

    @field_validator("css_override")
    @classmethod
    def _screen_css(cls, css: str | None) -> str | None:
        """Screen CSS for XSS vectors and breakout patterns."""
        if css is None:
            return None

        # Check for dangerous patterns (case-insensitive)
        css_lower = css.lower()

        # HTML tag breakout
        if "<" in css:
            msg = "CSS override cannot contain '<' (HTML tag breakout risk)"
            raise ValueError(msg)

        # @import can load external resources
        if "@import" in css_lower:
            msg = "CSS override cannot contain '@import'"
            raise ValueError(msg)

        # IE-specific expression() allows arbitrary JavaScript
        if "expression(" in css_lower:
            msg = "CSS override cannot contain 'expression('"
            raise ValueError(msg)

        # url() with non-data: schemes can exfiltrate data
        # Allow data: URIs but reject http://, https://, // (protocol-relative)
        if "url(" in css_lower:
            # Extract everything between url( and )
            url_pattern = re.compile(r'url\s*\(\s*["\']?([^)"\'\s]+)', re.IGNORECASE)
            for match in url_pattern.finditer(css):
                url_value = match.group(1).strip()
                if not url_value.startswith("data:"):
                    msg = "CSS override url() must use data: URIs only (no external resources)"
                    raise ValueError(msg)

        return css

    @model_validator(mode="after")
    def _unique_names(self) -> FormDefinition:
        """Ensure all field names are unique."""
        names = [field.value_name for field in self.fields]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            msg = f"Duplicate field names are not allowed: {', '.join(sorted(duplicates))}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _default_in_static_options(self) -> FormDefinition:
        """Ensure static dropdown/multi-select defaults are in the option list."""
        for field in self.fields:
            if (
                isinstance(field, (DropdownField, MultiSelectField))
                and isinstance(field.options, StaticOptions)
                and field.default is not None
            ):
                valid_values = {opt.value for opt in field.options.values}

                # For multi-select, check each value in the list
                if isinstance(field, MultiSelectField):
                    if not isinstance(field.default, list):
                        continue  # Will be caught by type validation
                    invalid_defaults = [v for v in field.default if v not in valid_values]
                    if invalid_defaults:
                        msg = (
                            f"Field '{field.value_name}': default values {invalid_defaults} are not in the option list"
                        )
                        raise ValueError(msg)
                # For dropdown, check the single value
                elif field.default not in valid_values:
                    msg = f"Field '{field.value_name}': default value '{field.default}' is not in the option list"
                    raise ValueError(msg)
        return self
