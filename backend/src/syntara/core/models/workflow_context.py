"""Shared workflow context models for approval and form_prompt nodes.

These models represent the workflow execution context passed to human-in-the-loop
gates (approval requests, form prompts) so users can make informed decisions.
"""

from typing import Any, ClassVar
from uuid import UUID

from pydantic import ConfigDict, Field
from sqlmodel import SQLModel


class ActivitySummary(SQLModel):
    """Activity summary for workflow context.

    Passed through from the workflow engine as-is. Contains at minimum
    ``id``, ``name``, ``type``, and usually ``config`` with the full
    activity parameters so users can see what the step will do.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True, extra="allow")  # type: ignore[assignment]

    id: str = Field(..., description="Activity ID from workflow definition")
    name: str = Field(..., description="Human-readable activity name")
    type: str = Field(..., description="Activity type (script, approval, agentic, etc.)")


class PreviousStepContext(SQLModel):
    """Previous Step Context for workflow execution.

    The activity that immediately preceded this node, including its output.
    Null if the node is the first activity in the workflow.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)  # type: ignore[assignment]

    id: str = Field(..., description="Activity ID from workflow definition")
    name: str = Field(..., description="Human-readable activity name")
    type: str = Field(..., description="Activity type (task, approval, parallel, etc.)")
    output: dict[str, Any] | None = Field(
        None, description="Output from the activity (structure varies per activity type)"
    )


class WorkflowContext(SQLModel):
    """Workflow Context for human-in-the-loop decision points.

    Essential context for users to make informed decisions at approval or
    form_prompt nodes. Contains workflow identification, inputs, and the
    output from the immediately preceding activity.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)  # type: ignore[assignment]

    workflow_id: UUID | None = Field(None, description="ID of the workflow")
    workflow_version: int | None = Field(None, description="Integer version number of the workflow version executed")
    workflow_name: str = Field(..., description="Name of the workflow")
    inputs: dict[str, Any] = Field(
        ..., description="Original workflow input parameters (structure varies per workflow)"
    )
    previous_step: PreviousStepContext | None = Field(None, description="Previous step context and output")
