"""Integration test for form_prompt node signal completion.

Tests the workflow-level handling of form_prompt signals using Temporal's
test environment. Verifies that form submission signals are correctly
received and routed through the workflow.
"""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
import yaml
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from syntara.workflows.workflow_engine.activities.manual_trigger import manual_trigger
from syntara.workflows.workflow_engine.activities.runtime_settings_activity import fetch_workflow_runtime_settings
from syntara.workflows.workflow_engine.dynamic_workflow import OrchestratorWorkflow
from syntara.workflows.workflow_engine.models.workflow_definition import ActivityName


@activity.defn(name=ActivityName.SCRIPT)
async def _test_script_activity(
    resolved_parameters: dict[str, Any],
    outputs: dict[str, str] | None = None,
    **kwargs: object,
) -> dict[str, Any]:
    return {"output": {"status": "completed"}}


def _create_form_prompt_workflow_yaml() -> dict[str, Any]:
    """Create workflow with form_prompt for signal testing."""
    workflow_yaml = """
schema_version: "2.0.0"
name: form-prompt-signal-test
description: Integration test for form_prompt signal completion
triggers:
- id: trigger_manual
  type: manual_trigger
nodes:
- id: form1
  type: form_prompt
  parameters:
    name: Test Form
    response_window: 300
    form_definition:
      fields:
      - name: email
        type: string
- id: process_step
  type: script
  parameters:
    language: python
    code: "print('processing')"
edges:
- from: trigger_manual
  to: form1
- from: form1
  to: process_step
  from_port: submitted
"""
    result: dict[str, Any] = yaml.safe_load(workflow_yaml)
    return result


@pytest.mark.integration
@pytest.mark.asyncio
class TestFormPromptSignalIntegration:
    """Integration tests for form_prompt node signal completion."""

    async def test_form_submission_signal_completes_workflow(self, temporal_env: WorkflowEnvironment) -> None:
        """Signaling form submission completes the form_prompt and continues workflow."""
        task_queue = "form-prompt-signal-queue"

        # Note: We're using a real form_prompt activity here, not a test mock
        # because we need to test the actual signal handling
        from syntara.workflows.workflow_engine.activities.form_prompt_activity import create_form_prompt_activity
        from syntara.workflows.workflow_engine.services.temporal_execution_service import TemporalExecutionService

        async with Worker(
            temporal_env.client,
            task_queue=task_queue,
            workflows=[OrchestratorWorkflow],
            activities=[
                manual_trigger,
                create_form_prompt_activity,
                _test_script_activity,
                fetch_workflow_runtime_settings,
            ],
        ):
            execution_service = TemporalExecutionService(
                temporal_client=temporal_env.client,
                task_queue=task_queue,
            )

            workflow_def = _create_form_prompt_workflow_yaml()
            result = await execution_service.start_workflow(
                workflow_definition=workflow_def,
                project_id="00000000-0000-0000-0000-000000000001",
                trigger_inputs={},
            )

            handle = temporal_env.client.get_workflow_handle(result.temporal_workflow_id)
            await asyncio.sleep(0.1)

            # Signal the form_prompt node with submission
            await handle.signal(
                "complete_activity",
                {
                    "activity_id": "form1",
                    "output": {
                        "outcome": "submitted",
                        "response_data": {"email": "test@example.com"},
                        "responded_by": str(uuid4()),
                        "responded_at": "2026-04-10T12:00:00Z",
                        "prompt_id": str(uuid4()),
                    },
                },
            )

            # Wait for workflow to complete
            await asyncio.sleep(0.1)
            wf_result = await handle.result()

            # Verify form output was captured
            assert "form1" in wf_result
            assert wf_result["form1"]["output"]["outcome"] == "submitted"
            assert wf_result["form1"]["output"]["response_data"]["email"] == "test@example.com"

            # Verify process_step executed
            assert "process_step" in wf_result

    async def test_signaled_expiry_with_fallback_routes_to_fallback(self, temporal_env: WorkflowEnvironment) -> None:
        """Signaled expiry routes to fallback port when fallback_behavior=fallback."""
        task_queue = "form-prompt-signal-expire-queue"

        workflow_yaml = """
schema_version: "2.0.0"
name: form-prompt-signal-expire-test
triggers:
- id: trigger_manual
  type: manual_trigger
nodes:
- id: form1
  type: form_prompt
  parameters:
    name: Test Form
    response_window: 300
    fallback_behavior: fallback
    form_definition: {}
- id: submitted_step
  type: script
  parameters:
    language: python
    code: "print('submitted')"
- id: fallback_step
  type: script
  parameters:
    language: python
    code: "print('expired')"
edges:
- from: trigger_manual
  to: form1
- from: form1
  to: submitted_step
  from_port: submitted
- from: form1
  to: fallback_step
  from_port: fallback
"""
        workflow_def: dict[str, Any] = yaml.safe_load(workflow_yaml)

        from syntara.workflows.workflow_engine.activities.form_prompt_activity import create_form_prompt_activity
        from syntara.workflows.workflow_engine.services.temporal_execution_service import TemporalExecutionService

        async with Worker(
            temporal_env.client,
            task_queue=task_queue,
            workflows=[OrchestratorWorkflow],
            activities=[
                manual_trigger,
                create_form_prompt_activity,
                _test_script_activity,
                fetch_workflow_runtime_settings,
            ],
        ):
            execution_service = TemporalExecutionService(
                temporal_client=temporal_env.client,
                task_queue=task_queue,
            )

            result = await execution_service.start_workflow(
                workflow_definition=workflow_def,
                project_id="00000000-0000-0000-0000-000000000001",
                trigger_inputs={},
            )

            handle = temporal_env.client.get_workflow_handle(result.temporal_workflow_id)
            await asyncio.sleep(0.1)

            # Signal expiry
            await handle.signal(
                "complete_activity",
                {
                    "activity_id": "form1",
                    "output": {
                        "outcome": "expired",
                        "response_data": None,
                        "responded_by": "system",
                        "responded_at": "2026-04-10T12:00:00Z",
                    },
                },
            )

            # Wait for workflow to complete
            await asyncio.sleep(0.1)
            wf_result = await handle.result()

            # Verify routed to fallback
            assert wf_result["form1"]["output"]["outcome"] == "expired"
            assert "fallback_step" in wf_result
            assert "submitted_step" not in wf_result

    async def test_signaled_cancellation_with_fail_raises(self, temporal_env: WorkflowEnvironment) -> None:
        """Signaled cancellation with fallback_behavior=fail raises ApplicationError."""
        task_queue = "form-prompt-signal-cancel-queue"

        workflow_yaml = """
schema_version: "2.0.0"
name: form-prompt-signal-cancel-test
triggers:
- id: trigger_manual
  type: manual_trigger
nodes:
- id: form1
  type: form_prompt
  parameters:
    name: Test Form
    response_window: 300
    fallback_behavior: fail
    form_definition: {}
- id: next_step
  type: script
  parameters:
    language: python
    code: "print('next')"
edges:
- from: trigger_manual
  to: form1
- from: form1
  to: next_step
  from_port: submitted
"""
        workflow_def: dict[str, Any] = yaml.safe_load(workflow_yaml)

        from syntara.workflows.workflow_engine.activities.form_prompt_activity import create_form_prompt_activity
        from syntara.workflows.workflow_engine.services.temporal_execution_service import TemporalExecutionService

        async with Worker(
            temporal_env.client,
            task_queue=task_queue,
            workflows=[OrchestratorWorkflow],
            activities=[
                manual_trigger,
                create_form_prompt_activity,
                _test_script_activity,
                fetch_workflow_runtime_settings,
            ],
        ):
            execution_service = TemporalExecutionService(
                temporal_client=temporal_env.client,
                task_queue=task_queue,
            )

            result = await execution_service.start_workflow(
                workflow_definition=workflow_def,
                project_id="00000000-0000-0000-0000-000000000001",
                trigger_inputs={},
            )

            handle = temporal_env.client.get_workflow_handle(result.temporal_workflow_id)
            await asyncio.sleep(0.1)

            # Signal cancellation
            await handle.signal(
                "complete_activity",
                {
                    "activity_id": "form1",
                    "output": {
                        "outcome": "cancelled",
                        "response_data": None,
                        "responded_by": "admin",
                        "responded_at": "2026-04-10T12:00:00Z",
                    },
                },
            )

            # Wait for workflow to fail
            await asyncio.sleep(0.1)
            desc = await handle.describe()
            assert desc.status.name == "FAILED"
