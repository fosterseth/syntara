"""Form field error model for validation results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormFieldError:
    """A single form field validation error.

    Carries structured per-field error information for client-side rendering.

    Codes produced on submission (validators/submission.py):

    - ``required`` - no value supplied for a required field
    - ``type`` - value is the wrong Python type
    - ``invalid_format`` - value is the right type but the content is bad,
      e.g. a string that is not a valid email address
    - ``not_in_options`` - value is absent from a static option list
    - ``must_be_checked`` - a required checkbox was not ticked
    - ``unknown_field`` - submitted key is not defined in the form

    Codes produced on definition (validators/definition.py):

    - ``invalid_default`` - a field default the submission coercer would reject

    Attributes:
        field: Field name from the descriptor
        label: Display label from the descriptor
        code: One of the codes above
        message: User-facing error message

    """

    field: str
    label: str
    code: str
    message: str
