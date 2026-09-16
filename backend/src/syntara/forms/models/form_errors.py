"""Form field error model for validation results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormFieldError:
    """A single form field validation error.

    Carries structured per-field error information for client-side rendering.
    """

    field: str  # Field name from the descriptor
    label: str  # Display label from the descriptor
    # Error code: "required" | "type" | "invalid_format" | "unknown_field"
    #           | "not_in_options" | "must_be_checked"
    # "type" is the wrong Python type; "invalid_format" is the right type with
    # bad content (e.g. a string that is not a valid email address).
    code: str
    message: str  # User-facing error message
