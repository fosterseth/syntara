"""Service layer for form prompt operations.

Minimal internal-facing implementation for workflow engine integration.
AAP-91889 will extend with full filtering/sorting/enrichment.
"""

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from syntara.core.models import User

from syntara.audit.dispatcher import AuditEventDispatcher
from syntara.forms.audit.form_prompt import FormPromptSubmittedEvent
from syntara.forms.exceptions import (
    FormPromptAlreadyRequestedError,
    FormPromptAlreadyRespondedError,
    FormPromptCancelledError,
    FormPromptExpiredError,
    FormPromptNotFoundError,
)
from syntara.forms.models.api_models import (
    TERMINAL_PROMPT_STATUSES,
    BatchFormPromptRequest,
    BatchUpdateResponse,
    BatchUpdateResult,
    FormPromptCreateRequest,
    FormPromptStatus,
    FormPromptSummary,
    can_transition,
)
from syntara.forms.models.form_prompt import FormPrompt, FormPromptListResponse
from syntara.forms.models.form_prompt_responders import FormPromptResponderGroup, FormPromptResponderUser
from syntara.forms.validators.submission import validate_form_submission
from syntara.workflows.exceptions import ExecutionNotFoundError
from syntara.workflows.models.execution import Execution

logger = structlog.stdlib.get_logger(__name__)


class FormPromptService:
    """Service for managing form prompts.

    Minimal service covering workflow engine needs:
    - create: atomically create form_prompts row + responder junctions
    - list_by_execution: fetch prompts for an execution
    - batch_update_status: update prompt statuses (expire/cancel)
    - submit: validate and persist form submission, send workflow signal
    """

    def __init__(
        self,
        session: AsyncSession,
        user: "User | None" = None,
    ) -> None:
        """Initialize service with database session.

        Args:
            session: SQLAlchemy async session
            user: Current authenticated user (optional for workflow-internal operations)

        """
        self.session = session
        self.user = user

    async def _validate_execution_reference(self, execution_id: UUID, project_id: UUID) -> None:
        """Validate that the execution exists and belongs to the expected project.

        Raises:
            ExecutionNotFoundError: If the execution does not exist
            ValueError: If the execution's project_id does not match

        """
        from syntara.workflows.exceptions import ExecutionNotFoundError  # noqa: PLC0415
        from syntara.workflows.models.execution import Execution  # noqa: PLC0415

        execution = await self.session.get(Execution, execution_id)
        if execution is None:
            raise ExecutionNotFoundError(execution_id)
        if execution.project_id != project_id:
            msg = f"project_id {project_id} does not match execution's project {execution.project_id}"
            raise ValueError(msg)

    async def create(self, request: FormPromptCreateRequest) -> FormPromptSummary:
        """Create a new form prompt.

        Args:
            request: Form prompt creation request

        Returns:
            Created form prompt summary

        Raises:
            FormPromptAlreadyRequestedError: If a prompt for this already exists

        """
        # Check for duplicate
        existing = await self._get_form_prompt(
            request.execution_id,
            request.prompt_node_id,
            request.loop_iteration_path,
        )
        if existing is not None:
            raise FormPromptAlreadyRequestedError(
                request.execution_id, request.prompt_node_id, request.loop_iteration_path
            )

        project_id = request.project_id
        execution_id = request.execution_id
        execution = await self.session.get(Execution, execution_id)
        if execution is None:
            raise ExecutionNotFoundError(execution_id)
        if execution.project_id != project_id:
            msg = f"project_id {project_id} does not match execution's project {execution.project_id}"
            raise ValueError(msg)

        # Create the prompt
        form_prompt = FormPrompt(
            execution_id=request.execution_id,
            project_id=request.project_id,
            prompt_node_id=request.prompt_node_id,
            name=request.name,
            message=request.message,
            loop_iteration_path=request.loop_iteration_path,
            temporal_activity_id=request.temporal_activity_id,
            timeout_at=request.timeout_at,
            form_definition=request.form_definition,
            submit_label=request.submit_label,
            success_message=request.success_message,
            timezone=request.timezone,
            css_override=request.css_override,
            status=FormPromptStatus.PENDING,
        )
        self.session.add(form_prompt)
        await self.session.flush()

        # Add responder junctions
        if request.responder_user_ids:
            for user_id in request.responder_user_ids:
                responder_user = FormPromptResponderUser(
                    form_prompt_id=form_prompt.id,
                    user_id=user_id,
                )
                self.session.add(responder_user)

        if request.responder_group_ids:
            for group_id in request.responder_group_ids:
                responder_group = FormPromptResponderGroup(
                    form_prompt_id=form_prompt.id,
                    group_id=group_id,
                )
                self.session.add(responder_group)

        await self.session.flush()

        logger.info(
            "Created form prompt",
            prompt_id=form_prompt.id,
            execution_id=request.execution_id,
            prompt_node_id=request.prompt_node_id,
        )

        # Return summary for internal workflow engine endpoints
        return FormPromptSummary.model_validate(form_prompt)

    async def list_by_execution(
        self,
        execution_id: UUID,
        status: FormPromptStatus | None = None,
    ) -> FormPromptListResponse:
        """Fetch form prompts for an execution, with optional status filter.

        Args:
            execution_id: Workflow execution ID
            status: Optional status filter

        Returns:
            Paginated response with form prompt summaries

        """
        query = select(FormPrompt).where(FormPrompt.execution_id == execution_id)  # type: ignore[arg-type]
        if status is not None:
            query = query.where(FormPrompt.status == status)  # type: ignore[arg-type]

        result = await self.session.execute(query)
        prompts = list(result.scalars().all())

        logger.debug(
            "Listed form prompts by execution",
            execution_id=execution_id,
            status=status.value if status else None,
            count=len(prompts),
        )

        # Convert to summaries and wrap in paginated response
        summaries = [FormPromptSummary.model_validate(p) for p in prompts]
        return FormPromptListResponse(resources=summaries, next=None, prev=None)

    async def batch_update_status(self, request: BatchFormPromptRequest) -> BatchUpdateResponse:
        """Batch update form prompt statuses.

        Enforces state transition rules via can_transition().
        Already-terminal prompts are skipped (idempotent).

        Args:
            request: Batch update request

        Returns:
            Typed batch update response with results and counts

        """
        results: list[BatchUpdateResult] = []
        success_count = 0
        failed_count = 0

        for update in request.updates:
            try:
                prompt = await self.session.get(FormPrompt, update.prompt_id)
                if prompt is None:
                    results.append(
                        BatchUpdateResult(
                            prompt_id=str(update.prompt_id),
                            success=False,
                            error="Form prompt not found",
                        )
                    )
                    failed_count += 1
                    continue

                # Check transition validity
                current_status = FormPromptStatus(prompt.status)
                target_status = FormPromptStatus(update.status.value)

                if not can_transition(current_status, target_status):
                    # Idempotent: if already at target status, treat as success
                    if current_status == target_status:
                        results.append(
                            BatchUpdateResult(
                                prompt_id=str(update.prompt_id),
                                success=True,
                                message=f"Already {target_status.value}",
                            )
                        )
                        success_count += 1
                    else:
                        results.append(
                            BatchUpdateResult(
                                prompt_id=str(update.prompt_id),
                                success=False,
                                error=f"Cannot transition from {current_status.value} to {target_status.value}",
                            )
                        )
                        failed_count += 1
                    continue

                # Update status
                prompt.status = target_status
                self.session.add(prompt)
                results.append(
                    BatchUpdateResult(
                        prompt_id=str(update.prompt_id),
                        success=True,
                    )
                )
                success_count += 1

            except Exception as e:
                logger.exception(
                    "Error updating form prompt status",
                    prompt_id=update.prompt_id,
                    error=str(e),
                )
                results.append(
                    BatchUpdateResult(
                        prompt_id=str(update.prompt_id),
                        success=False,
                        error=str(e),
                    )
                )
                failed_count += 1

        await self.session.flush()

        logger.info(
            "Batch updated form prompt statuses",
            total=len(request.updates),
            success=success_count,
            failed=failed_count,
        )

        return BatchUpdateResponse(
            results=results,
            total_success=success_count,
            total_failed=failed_count,
        )

    async def validate_submission(
        self,
        prompt_id: UUID,
        submitted_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate form submission data against prompt definition.

        Validates both prompt state (must be PENDING and not expired) and
        form data (required fields, types, options).

        Args:
            prompt_id: Form prompt ID
            submitted_data: Raw submitted form data

        Returns:
            Cleaned and coerced form data ready for workflow namespace

        Raises:
            FormPromptNotFoundError: If prompt does not exist
            FormPromptExpiredError: If prompt has expired
            FormPromptCancelledError: If prompt has been cancelled
            FormPromptAlreadyRespondedError: If prompt already has a response (SUBMITTED)
            FormDataValidationError: If form data fails validation (carries field errors)

        """
        # Fetch the prompt
        prompt = await self.session.get(FormPrompt, prompt_id)
        if prompt is None:
            raise FormPromptNotFoundError(prompt_id)

        # Check prompt state
        if prompt.status in TERMINAL_PROMPT_STATUSES:
            if prompt.status == FormPromptStatus.EXPIRED:
                raise FormPromptExpiredError(prompt_id, prompt.timeout_at)
            if prompt.status == FormPromptStatus.CANCELLED:
                raise FormPromptCancelledError(prompt_id)
            # SUBMITTED - will be caught by the already-responded check in submit endpoint

        # Check if prompt has timed out (even if status is still PENDING)
        if prompt.timeout_at is not None:
            now = datetime.now(UTC)
            if now > prompt.timeout_at:
                raise FormPromptExpiredError(prompt_id, prompt.timeout_at)

        # Validate form data against definition
        cleaned_data = validate_form_submission(prompt.form_definition, submitted_data)

        logger.info(
            "Validated form submission",
            prompt_id=prompt_id,
            field_count=len(cleaned_data),
        )

        return cleaned_data

    async def submit(
        self,
        prompt_id: UUID,
        submitted_data: dict[str, Any],
    ) -> FormPrompt:
        """Submit a response to a form prompt.

        Validates the submission, persists it to the database, and sends a signal
        to the workflow engine to resume the paused workflow.

        Args:
            prompt_id: Form prompt ID
            submitted_data: Raw submitted form data

        Returns:
            Updated form prompt with response data

        Raises:
            FormPromptNotFoundError: If prompt does not exist
            FormPromptExpiredError: If prompt has expired
            FormPromptCancelledError: If prompt has been cancelled
            FormPromptAlreadyRespondedError: If prompt already has a response
            FormDataValidationError: If form data fails validation

        """
        if self.user is None:
            msg = "User context required for form submission"
            raise ValueError(msg)

        # Validate submission (includes state checks and data validation)
        cleaned_data = await self.validate_submission(prompt_id, submitted_data)

        # Get the prompt again for the update (validate_submission already checked it exists)
        prompt = await self.session.get(FormPrompt, prompt_id)
        if prompt is None:
            raise FormPromptNotFoundError(prompt_id)

        responded_at = datetime.now(UTC)

        # SECURITY: Optimistic locking prevents TOCTOU race condition.
        # UPDATE with WHERE status=PENDING ensures only one concurrent submission succeeds.
        stmt = (
            sa_update(FormPrompt)
            .where(FormPrompt.id == prompt_id)  # type: ignore[arg-type]
            .where(FormPrompt.status == FormPromptStatus.PENDING)  # type: ignore[arg-type]
            .values(
                status=FormPromptStatus.SUBMITTED,
                response_data=cleaned_data,
                responded_by=self.user.id,
                responded_at=responded_at,
            )
        )
        result = await self.session.execute(stmt)
        rowcount = result.rowcount  # type: ignore[attr-defined]

        if rowcount == 0:
            # Prompt was submitted by another user between our check and this UPDATE
            await self.session.rollback()
            # Re-fetch to get current status for error message
            prompt = await self.session.get(FormPrompt, prompt_id)
            if prompt:
                raise FormPromptAlreadyRespondedError(prompt_id, prompt.status)
            raise FormPromptNotFoundError(prompt_id)

        await self.session.commit()

        # Refresh to get the updated state
        await self.session.refresh(prompt)

        # Calculate pause duration for telemetry (AC-9)
        submitted = responded_at.replace(tzinfo=None)
        created = prompt.created_at.replace(tzinfo=None)
        pause_duration_ms = int((submitted - created).total_seconds() * 1000)

        logger.info(
            "Form prompt submitted",
            prompt_id=prompt_id,
            execution_id=prompt.execution_id,
            responded_by=self.user.id,
            field_count=len(cleaned_data),
            pause_duration_ms=pause_duration_ms,
        )

        # Send signal to workflow engine (best-effort, never blocks the response)
        # Track signal delivery latency for telemetry (AC-10)
        signal_error: str | None = None
        signal_delivery_latency_ms: int | None = None
        try:
            from syntara.forms.clients.workflow_client import WorkflowApiClient  # noqa: PLC0415

            signal_start = time.perf_counter()
            async with WorkflowApiClient() as client:
                await client.send_form_signal(
                    execution_id=prompt.execution_id,
                    form_prompt_id=prompt.prompt_node_id,
                    form_response={
                        "outcome": "submitted",
                        "response_data": cleaned_data,
                        "responded_by": self.user.username,
                        "responded_at": responded_at.isoformat(),
                        "prompt_id": str(prompt_id),
                    },
                    temporal_activity_id=prompt.temporal_activity_id,
                )
            signal_delivery_latency_ms = int((time.perf_counter() - signal_start) * 1000)
        except Exception as e:  # noqa: BLE001
            signal_error = "Workflow signal delivery failed"
            logger.warning(
                "Failed to send form submission signal",
                prompt_id=prompt_id,
                execution_id=prompt.execution_id,
                error=str(e),
                exc_info=True,
            )

        # Emit audit event with telemetry data (AC-9, AC-10)
        AuditEventDispatcher.dispatch(
            FormPromptSubmittedEvent(
                prompt_id=prompt_id,
                execution_id=prompt.execution_id,
                prompt_node_id=prompt.prompt_node_id,
                submitted_by=self.user.id,
                submitted_at=responded_at,
                pause_duration_ms=pause_duration_ms,
                field_count=len(cleaned_data),
                outcome="submitted",
                signal_delivery_latency_ms=signal_delivery_latency_ms,
                principal_type=self.user.__dict__.get("__principal_type__"),
            )
        )

        # Store signal error for the response (not persisted to DB)
        if signal_error:
            # Note: This would need a FormPromptRead model with signal_delivery_error field
            # For now, just log it - the caller can check logs
            logger.error("Signal delivery failed", prompt_id=prompt_id, error=signal_error)

        return prompt

    async def _get_form_prompt(
        self,
        execution_id: UUID,
        prompt_node_id: str,
        loop_iteration_path: list[int],
    ) -> FormPrompt | None:
        """Get form prompt by unique key (execution_id, prompt_node_id, loop_iteration_path).

        Args:
            execution_id: Workflow execution ID
            prompt_node_id: Canvas node ID
            loop_iteration_path: Loop iteration path

        Returns:
            FormPrompt if found, None otherwise

        """
        query = (
            select(FormPrompt)
            .where(FormPrompt.execution_id == execution_id)  # type: ignore[arg-type]
            .where(FormPrompt.prompt_node_id == prompt_node_id)  # type: ignore[arg-type]
            .where(FormPrompt.loop_iteration_path == loop_iteration_path)  # type: ignore[arg-type]
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
